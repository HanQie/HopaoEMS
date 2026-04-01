"""
agent.py
========
Agent 核心循環 — 使用 Ollama Function Calling 驅動的自主決策引擎。

流程：
  1. 接收用戶文字 → 構建 system prompt + tools schema
  2. 調用 Ollama chat(tools=...) → 模型自主決定調用哪個 Tool
  3. 執行 Tool → 將結果注入 messages → 再次調用模型
  4. 重複直到模型選擇直接回覆（無 tool_calls）或達到最大迭代次數

設計原則：
  - MAX_ITERATIONS = 5，防止無限迴路
  - 失敗降級：Tool 執行失敗時，錯誤訊息回饋給模型讓它決定下一步
  - 向後相容：回傳與舊 intent_dispatcher 相同的 dict 格式
"""

from __future__ import annotations

import json
import logging
from typing import Any

from .tools import TOOL_SCHEMAS, ToolContext, execute_tool

logger = logging.getLogger(__name__)

MAX_ITERATIONS = 5

# ---------------------------------------------------------------------------
# Agent System Prompt
# ---------------------------------------------------------------------------
AGENT_SYSTEM_PROMPT = """\
你是 HopaoEMS 工廠管理系統的 AI 助理，具備「架構感知 (Schema-Aware)」能力。

核心原則：
1. 請先詳閱提供的資料庫 Schema，瞭解有哪些資料表與欄位及其 NOT NULL 約束。
2. 嚴格採用 CQRS：所有查詢一律使用 `universal_query_engine`；所有狀態變更一律使用 `universal_data_entry`。
3. 若用戶要求新增或修改資料，請使用 `universal_data_entry` 並傳入 `action="upsert"`。
4. 若用戶要求刪除明確的資料，請使用 `universal_data_entry` 並傳入 `action="delete"` 與 `conditions`。
5. 【複合刪除或批量操作】（例如「刪除重複項」、「刪除某條件下的全部」）：請先使用 `universal_query_engine` 找出要刪除的具體 `id` 清單，再使用 `universal_data_entry` 傳入 `action="delete"` 與 `{"id": [對應的ID]}` 進行刪除，切勿因為不知道 ID 就直接放棄並詢問用戶。
5.1 若需求是樣品顏色校正資料的「重複去重」，例如「刪除重複原顏色」「同色只留一筆」，必須使用 `deduplicate_color_corrections`，禁止直接刪除 `sample_color_map` 全部資料。
6. 若用戶上傳了單據或圖片，需要 OCR/欄位擷取時請使用 `multimodal_processor` 並傳入 `action="extract"`；若要以圖找圖，請使用 `multimodal_processor` 並傳入 `action="search"`。
7. 若發現執行寫入時仍缺少關鍵必填資訊，請調用 `ask_user` 向用戶索取。
8. 【任務完成反饋】：當操作成功時，請自主生成『友善的成功反饋』，確保用戶清楚知道操作已完成。
9. 你可以在 `<think>...</think>` 中做內部規劃，用來拆解複合任務、決定查詢與寫入順序、或規劃多模態流程；最終對外回覆必須乾淨，工具參數必須精確。
"""


class AgentRunner:
    """
    Agent 執行器。每次 dispatch() 呼叫建立一個實例並執行 run()。
    """

    def __init__(
        self,
        processor,
        db_path: str,
        lang: str = "zh",
        username: str = "operator",
        image_bytes: bytes | None = None,
        history: list[dict[str, str]] | None = None,
        current_entity: dict[str, Any] | None = None,
        field_manifest: dict[str, Any] | None = None,
        conversation_id: str = "default",
    ):
        self.processor = processor
        self.ctx = ToolContext(
            db_path=db_path,
            lang=lang,
            username=username,
            conversation_id=conversation_id,
            processor=processor,
            image_bytes=image_bytes,
            current_entity=current_entity,
            field_manifest=field_manifest,
        )
        self.lang = lang
        self.has_image = image_bytes is not None
        self.history = history or []
        self.current_entity = current_entity or {}
        self.field_manifest = field_manifest or {}
        self.conversation_id = conversation_id
        self.accumulated_thinking = []
        self.tool_trace = []

    def run(self, user_text: str) -> dict[str, Any]:
        """
        執行 Agent 循環。回傳格式與舊 intent_dispatcher.dispatch() 相容：
        {
            "status": "ok" | "need_info" | "ready" | "partial_done" | "error",
            "intent": "query" | "stock_in" | "production_log" | "agent" | "unknown",
            "reply": "...",
            "thinking_process": "...",
            "params": {...}   // optional
        }
        """
        from .ai_service import get_db_schema
        schema_sql = get_db_schema(self.ctx.db_path)
        system_content = f"{AGENT_SYSTEM_PROMPT}\n\n【動態 Schema】\n```sql\n{schema_sql}\n```\n請根據以上 Schema 決定寫入時需要提供的最小欄位。\n"

        # 建立初始訊息列表
        messages = [
            {"role": "system", "content": system_content},
        ]

        # 注入歷史紀錄 (對應 Ollama role: user, assistant)
        for h in self.history:
            role = "user" if h.get("role") == "user" else "assistant"
            messages.append({"role": role, "content": h.get("text", "")})

        # 加入當前用戶輸入
        messages.append({"role": "user", "content": self._build_user_message(user_text)})

        last_tool_result = None
        detected_intent = "unknown"

        for iteration in range(MAX_ITERATIONS):
            logger.info(f"[Agent] 迭代 {iteration + 1}/{MAX_ITERATIONS}")

            try:
                response = self.processor.chat_with_tools(
                    messages=messages,
                    tools=TOOL_SCHEMAS,
                    max_tokens=2048,
                    temperature=0.4,
                )
            except Exception as e:
                logger.error(f"[Agent] Ollama 呼叫失敗: {e}", exc_info=True)
                return self._error_response(str(e))

            # 取得模型回應
            msg = response.message
            content = msg.content or ""
            tool_calls = msg.tool_calls

            # Fallback 處理：如果模型沒走 Ollama 的 native tool_calls，而是直接輸出了 JSON 文字
            if not tool_calls and ('"name"' in content and '"arguments"' in content):
                logger.warning(f"[Agent] Ollama 未解析出 tool_calls，嘗試從文字內容手動提取: {content[:100]}...")
                tool_calls = self._parse_raw_tool_calls(content)

            # 沒有 tool_calls → 模型選擇直接回覆
            if not tool_calls:
                logger.info(f"[Agent] 模型直接回覆（無 tool_calls）")
                # 提取並清理 <think> 標籤
                from .ai_service import _strip_think_tags, _extract_think_tags, summarize_reasoning_debug
                think_block = _extract_think_tags(content)
                if think_block:
                    self.accumulated_thinking.append(summarize_reasoning_debug(think_block))
                    
                cleaned = _strip_think_tags(content)
                
                # 如果有截取到一些標籤像 portun </tool_call>，做額外清理
                import re
                cleaned = re.sub(r'</?tool_call>', '', cleaned)
                
                return self._build_response(
                    status="ok",
                    intent=detected_intent,
                    reply=cleaned or self._fallback_text(),
                    params=last_tool_result,
                )

            # 有 tool_calls → 逐一執行
            # 將 assistant 的回覆（包含 tool_calls）加入 messages
            messages.append(msg)

            for tc in tool_calls:
                tool_name = tc.function.name
                tool_args = tc.function.arguments

                # 追蹤意圖
                detected_intent = self._infer_intent(tool_name, tool_args, detected_intent)

                logger.info(f"[Agent] 調用 Tool: {tool_name}")

                # 執行 Tool
                result = execute_tool(tool_name, tool_args, self.ctx)
                last_tool_result = result
                self.tool_trace.append({
                    "tool": tool_name,
                    "args": tool_args,
                    "result": result,
                })

                # 特殊處理：ask_user 直接回傳
                if tool_name == "ask_user":
                    question = result.get(
                        "question_zh" if self.lang == "zh" else "question_vi",
                        "",
                    )
                    return self._build_response(
                        status="need_info",
                        intent=detected_intent,
                        reply=question or self._fallback_text(),
                    )

                # 將 Tool 結果注入 messages
                messages.append({
                    "role": "tool",
                    "content": json.dumps(result, ensure_ascii=False, default=str),
                })

            # 特殊處理：partial_stock_in 或 stock_in_full 成功後
            if last_tool_result and last_tool_result.get("status") in ("created", "success", "already_exists"):
                tool_status = last_tool_result["status"]
                if tool_name in ("partial_stock_in", "stock_in_full"):
                    # 繼續循環讓模型生成自然語言回覆
                    continue

        # 達到最大迭代 → 回傳最後結果
        logger.warning(f"[Agent] 達到最大迭代次數 {MAX_ITERATIONS}")
        if last_tool_result:
            return self._build_response(
                status="ok",
                intent=detected_intent,
                reply=self._summarize_result(last_tool_result),
                params=last_tool_result,
            )
        return self._error_response("Agent 達到最大迭代次數但未產生回應。")

    # -------------------------------------------------------------------
    # 輔助方法
    # -------------------------------------------------------------------

    @staticmethod
    def _parse_raw_tool_calls(content: str) -> list[Any]:
        """當 Ollama SDK 無法解析時，嘗試用正則從文字中提取 tool call JSON。"""
        import json
        import logging
        
        class MockFunction:
            def __init__(self, name, arguments):
                self.name = name
                self.arguments = arguments
                
        class MockToolCall:
            def __init__(self, function):
                self.function = function
                
        parsed_calls = []
        content = content.strip()
        start = content.find('{')
        end = content.rfind('}')
        if start != -1 and end != -1:
            raw = content[start:end+1]
            try:
                data = json.loads(raw)
                if isinstance(data, dict) and "name" in data and "arguments" in data:
                    parsed_calls.append(MockToolCall(MockFunction(data["name"], data["arguments"])))
                elif isinstance(data, list):
                    for item in data:
                        if isinstance(item, dict) and "name" in item and "arguments" in item:
                            parsed_calls.append(MockToolCall(MockFunction(item["name"], item["arguments"])))
            except Exception as e:
                logging.getLogger(__name__).warning(f"[Agent] 無法解析 raw tool_call JSON: {e}\nRaw:{raw}")
                
        return parsed_calls

    @staticmethod
    def _infer_intent(tool_name: str, tool_args: str | dict, current: str) -> str:
        """從 Tool 名稱與參數推斷意圖。"""
        if isinstance(tool_args, str):
            import json
            try:
                args = json.loads(tool_args)
            except:
                args = {}
        else:
            args = tool_args or {}

        if tool_name == "universal_query_engine":
            return "query"
        elif tool_name == "universal_data_entry" or tool_name == "universal_delete_entry":
            entity = args.get("entity_type", "")
            if "fabric" in entity or "stock" in entity:
                return "stock_in"
            elif "production" in entity:
                return "production_log"
            elif "sample" in entity:
                return "sample"
            return current
        elif tool_name in ("multimodal_extractor", "multimodal_processor", "deduplicate_color_corrections"):
            return "sample"
        return current

    def _build_user_message(self, user_text: str) -> str:
        """構建用戶訊息，包含圖片上下文提示。"""
        has_context_image = self.has_image
        if has_context_image:
            text = (
                f"{user_text}\n\n"
                "[系統提示：用戶同時上傳了一張圖片或指定了微庫圖片。"
                "請視任務需要調用 `multimodal_processor` 進行圖片擷取或以圖搜圖。]"
            )
        else:
            text = user_text

        if self.current_entity.get("type") == "sample":
            text += (
                "\n\n"
                f"[系統提示：當前頁面 sample id={self.current_entity.get('id')}, "
                f"sample_no={self.current_entity.get('sample_no', '')}, "
                f"title={self.current_entity.get('title', '')}。"
                "若用戶說『這個』『這張』『刪除重複的』『幫我填入』，優先視為針對這筆 sample。]"
            )

        manifest = self.field_manifest or {}
        fields = manifest.get("fields") or []
        groups = manifest.get("groups") or []
        page_type = str(manifest.get("page_type") or "").strip()
        if page_type or fields or groups:
            field_parts = []
            for field in fields[:12]:
                name = str(field.get("name") or "").strip()
                label = str(field.get("label") or "").strip()
                aliases = [str(alias).strip() for alias in (field.get("aliases") or []) if str(alias).strip()]
                alias_text = f" aliases={','.join(aliases[:4])}" if aliases else ""
                if name:
                    field_parts.append(f"{name}({label or name}{alias_text})")
            group_parts = []
            for group in groups[:6]:
                group_name = str(group.get("name") or "").strip()
                group_kind = str(group.get("kind") or "").strip()
                if group_name:
                    group_parts.append(f"{group_name}:{group_kind or 'group'}")
            text += (
                "\n\n"
                f"[系統提示：當前頁面 page_type={page_type or 'unknown'}。"
                f"可編輯欄位: {'; '.join(field_parts) if field_parts else '無'}。"
                f"欄位群組: {'; '.join(group_parts) if group_parts else '無'}。"
                "若用戶要求『填入』『補充』『更新本頁欄位』，優先針對這些欄位產生最小必要更新；"
                "若已鎖定 current_entity，請避免再要求無關的必填欄位。]"
            )
        return text

    def _build_response(
        self,
        status: str,
        intent: str,
        reply: str,
        params: dict | None = None,
    ) -> dict[str, Any]:
        """構建向後相容的回應 dict。"""
        resp = {
            "status": status,
            "intent": intent,
            "reply": reply,
        }
        if params:
            resp["params"] = params

        # 注入可安全展示的 debug reasoning 摘要
        if hasattr(self, 'accumulated_thinking') and self.accumulated_thinking:
            valid = [t for t in self.accumulated_thinking if t.strip()]
            if valid:
                summary = "\n\n---\n\n".join(valid)
                resp["reasoning_summary"] = summary
                resp["thinking_process"] = summary
        if self.tool_trace:
            resp["tool_trace"] = self.tool_trace

        return resp

    def _error_response(self, detail: str = "") -> dict[str, Any]:
        """錯誤回應。"""
        fallback = self._fallback_text()
        reply = f"{fallback}" if not detail else f"{fallback}\n({detail})"
        return {
            "status": "error",
            "intent": "unknown",
            "reply": reply,
        }

    def _fallback_text(self) -> str:
        """保底文字。"""
        if self.lang == "zh":
            return "抱歉，我無法處理您的請求。請提供更多細節（如布號、缸號等），或稍後再試。"
        return "Xin lỗi, tôi không thể xử lý yêu cầu lúc này. Vui lòng cung cấp thêm thông tin."

    def _summarize_result(self, result: dict) -> str:
        """將 Tool 執行結果摘要為簡短文字。"""
        if "reply" in result:
            return result["reply"]
        if "message" in result:
            return result["message"]
        if "error" in result:
            if self.lang == "zh":
                return f"操作失敗：{result['error']}"
            return f"Thao tác thất bại: {result['error']}"
        # 預設：將完整結果轉為文字
        return json.dumps(result, ensure_ascii=False, default=str)
