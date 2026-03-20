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
你是 HopaoEMS 工廠管理系統的 AI 助理。你可以使用以下工具來協助用戶：

1. **query_database** — 查詢庫存、訂單、生產記錄等資料庫資訊
2. **stock_in_full** — 完整入庫登記（布號 + 缸號 + 捲料列表全部齊備時）
3. **register_fabric_only** — 即 partial_stock_in，僅建立或註冊布號主檔（當用戶只想新增布號、或是其他入庫資訊之後再補時使用）
4. **log_production** — 登記生產記錄
5. **lookup_fabric** — 查找布號是否已存在
6. **lookup_roll** — 搜索在庫的捲料
7. **ask_user** — 向用戶反問缺少的資訊
8. **create_sample** — 建立新樣品記錄
9. **search_sample_by_image** — 用戶發送圖片時，找出系統中最相似的樣品
10. **list_samples** — 搜索或列出樣品
11. **edit_sample** — 修改樣品的資料（如修改標題、備註、關聯布號等）
12. **delete_fabric** — 徹底刪除布號及其所有缸號與捲料紀錄
13. **batch_record_color_corrections** — 當用戶提供顏色表格時，批量記錄顏色校正數據（如 RGB -> LAB/YMCK）
14. **extract_color_correction_data** — 從用戶上傳的圖片中提取顏色換色表格數據（當你自己看不見圖中內容時調用）

⚠️ 重要規則：
- **批量入庫與自動編號**：若用戶連續輸入了 N 個重量數值，表示這是批量入庫。請務必在 `rolls` 陣列中產生 N 個對應的物件。關於每一項的「捲號」：如果用戶有用連寫數字（如 "12345"）對應 N 個重量，請將其拆解，理解為捲號分別是 "1", "2", "3", "4", "5"。如果用戶懶得打捲號，請你**自動依序命名為 "1", "2", "3", "4", ...** 直到 N。**絕對不可以把重量數值本身當作捲號**！
- **意圖不明確認**：如果用戶提供的入庫資料（如疋數與重量的對應關係）存在模糊、不一致，或者你不確定是否該將連寫數字拆解時，**請先中斷操作並調用 `ask_user` 工具或者直接回覆訊息詢問用戶**，同時提供明確的 A/B 選項供用戶選擇（例如：「請問 12345 是指 1 筆捲號叫做 12345？還是指 5 筆分別叫作 1, 2, 3, 4, 5？ (A) 1筆 (B) 5筆」）。
- **長度估算**：系統會根據克重自動估算長度。**禁止主動向用戶詢問長度**（除非用戶主動提供）。如果用戶未提供長度，請在調用參數中省略 `length_m` 或明確設為 0。
- **顏色換色數據提取與圖片記憶**：用戶上傳圖片後，系統會自動嘗試 OCR 並將結果放入 `[系統偵測到圖片內容並自動解析如下：... ]`。
  - **優先使用現成數據**：如果你在 context 中看到這些括號內的數據，請**直接提取並調用 `batch_record_color_corrections`**。如果數據看起來像顏色表（RGB 對應 LAB/YMCK），不要再詢問用戶，除非數據完全不可讀。
  - **手動調用視覺模型**：如果 context 中沒有數據、數據不全、或用戶提到「看這張圖」，你仍應調用 `extract_color_correction_data` 工具。
  - **流程**：(優先) Context 數據 / (備選) `extract_color_correction_data` -> 調用 `batch_record_color_corrections`。
  - **輸入層 (Input)**：通常標示為 RGB。
  - **輸出層 (Output)**：標示為 LAB、YMCK 或其他。如果是 YMCKBHFm，請將 `target_mode` 設為 "YMCKBHFm" 並將 8 位數值放入 `target_note`。
- **剪貼簿支援**：用戶現在可以 CTRL+V 貼上截圖，這會與圖片上傳行為一致，你應主動 search 相似樣品。
- **未知需求 / 能力外工作**：如果用戶要求了沒有適合上述工具的操作（例如刪除訂單、刪除紀錄、無法判斷的行為等），請明確且誠實地告訴用戶你目前無法做到或沒有對應工具，**絕對不要在沒有調用適當工具的情況下捏造成功的回覆**。
- 禁止猜測用戶沒有提供的數據（如重量）。
- 如果用戶提供了足夠資訊做完整入庫（布號 + 缸號 + 捲數及重量），調用 `stock_in_full`。
- **當用戶發送圖片時，應主動調用 search_sample_by_image** 來查找相似樣品。
- 使用繁體中文或越南語回覆（根據用戶語言）。
- 回覆要簡潔、專業。
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
    ):
        self.processor = processor
        self.ctx = ToolContext(
            db_path=db_path,
            lang=lang,
            username=username,
            processor=processor,
            image_bytes=image_bytes,
        )
        self.lang = lang
        self.has_image = image_bytes is not None
        self.history = history or []

    def run(self, user_text: str) -> dict[str, Any]:
        """
        執行 Agent 循環。回傳格式與舊 intent_dispatcher.dispatch() 相容：
        {
            "status": "ok" | "need_info" | "ready" | "partial_done" | "error",
            "intent": "query" | "stock_in" | "production_log" | "agent" | "unknown",
            "reply": "...",
            "params": {...}   // optional
        }
        """
        # 建立初始訊息列表
        messages = [
            {"role": "system", "content": AGENT_SYSTEM_PROMPT},
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
                    temperature=0.1,
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
                # 清理 <think> 標籤
                from .ai_service import _strip_think_tags
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
                detected_intent = self._infer_intent(tool_name, detected_intent)

                logger.info(f"[Agent] 調用 Tool: {tool_name}")

                # 執行 Tool
                result = execute_tool(tool_name, tool_args, self.ctx)
                last_tool_result = result

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
        import re
        import json
        
        # 尋找類似 {"name": "...", "arguments": {...}} 的 JSON 結構
        pattern = re.compile(r'\{\s*"name"\s*:\s*"[^"]+"\s*,\s*"arguments"\s*:\s*\{.*?\}\s*\}', re.DOTALL)
        matches = pattern.finditer(content)
        
        class MockFunction:
            def __init__(self, name, arguments):
                self.name = name
                self.arguments = arguments
                
        class MockToolCall:
            def __init__(self, function):
                self.function = function
                
        parsed_calls = []
        for m in matches:
            try:
                data = json.loads(m.group(0))
                name = data.get("name")
                args = data.get("arguments", {})
                if name:
                    parsed_calls.append(MockToolCall(MockFunction(name, args)))
            except Exception as e:
                logger.warning(f"[Agent] 無法解析匹配到的 raw tool_call JSON: {e}")
                
        return parsed_calls

    @staticmethod
    def _infer_intent(tool_name: str, current: str) -> str:
        """從 Tool 名稱推斷意圖。"""
        mapping = {
            "query_database": "query",
            "stock_in_full": "stock_in",
            "register_fabric_only": "stock_in",
            "log_production": "production_log",
            "lookup_fabric": "query",
            "lookup_roll": "query",
            "ask_user": current,  # 保留原意圖
            "create_sample": "sample",
            "search_sample_by_image": "sample_search",
            "list_samples": "query",
        }
        return mapping.get(tool_name, current)

    def _build_user_message(self, user_text: str) -> str:
        """構建用戶訊息，包含圖片上下文提示。"""
        if self.has_image:
            return (
                f"{user_text}\n\n"
                "[系統提示：用戶同時上傳了一張圖片。"
                "請調用 search_sample_by_image 工具來查找相似樣品。]"
            )
        return user_text

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
