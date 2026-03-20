"""
intent_dispatcher.py
====================
意圖判斷與登記參數萃取。

流程：
  1. LLM 分類意圖：query | stock_in | production_log | unknown
  2. query      → sql_agent.ask()
  3. stock_in   → 萃取 fabric_code, cylinder_no, rolls[]
  4. production_log → 萃取 task_id/order_no, roll_id/roll_no, length_m
  5. 缺必要欄位 → 以越南語反問（禁止猜測）
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# System Prompt：意圖分類（禁止猜測策略）
# ---------------------------------------------------------------------------
INTENT_CLASSIFY_SYSTEM = """
你是一個工廠管理系統的 AI 助理，負責理解操作員的輸入並分類意圖。

可能的意圖：
- "query"         : 用戶在查詢資訊（庫存、訂單、生產記錄等）
- "stock_in"      : 用戶想要登記布料入庫、新增布料資料、或註冊新布號
- "production_log": 用戶想要登記一筆生產記錄（消耗布匹）
- "unknown"       : 無法判斷或一般對話

回覆格式為純 JSON（不加 markdown 包裝），例如：
{"intent": "stock_in"}
或
{"intent": "query"}

只回覆 JSON，不要任何解釋。
"""

# ---------------------------------------------------------------------------
# System Prompt：入庫參數萃取（嚴格禁止猜測）
# ---------------------------------------------------------------------------
STOCK_IN_EXTRACT_SYSTEM = """
你是工廠管理系統的 AI 助理。任務：協助用戶提取所需的入庫資訊。

必要欄位：
- fabric_code  : 布料代碼（例如 F-001）
- cylinder_no  : 缸號（例如 V-001）
- rolls        : 捲列表，包含捲號 (roll_no) 與重量 (weight_kg)
- note         : 額外資訊或備註（如 NYLON, 黑色, 或用戶提到的特殊要求）

⚠️ 重要規則：
1. **處理部分資訊**：若用戶只給了布號（如 95278），且明確說其他資訊之後再補或不提供，請設 status="need_info" 並在 question_zh 中禮貌地告訴用戶：「已記錄布號 {code}。雖然您目前不需要輸入缸號，但系統最終存檔仍需此資訊。我已先為您開啟登記介面。」
2. **靈活應對**：若用戶文字中包含「不提供」、「不需要」、「之後補」等詞彙，不要只是報錯，要能理解並給予正面回應。
3. **禁止瞎猜**：如果完全沒有布號，絕對禁止自行發明。

回覆格式 (純 JSON)：
{
  "status": "ready" | "need_info",
  "params": { "fabric_code": "...", "cylinder_no": "...", "rolls": [...], "note": "..." },
  "question_zh": "您的回覆內容 (繁體中文)",
  "question_vi": "Nội dung phản hồi (Tiếng Việt)"
}
"""

# ---------------------------------------------------------------------------
# System Prompt：生產登記參數萃取（嚴格禁止猜測）
# ---------------------------------------------------------------------------
PRODUCTION_LOG_EXTRACT_SYSTEM = """
你是工廠管理系統的資料萃取助理。任務：從用戶輸入中萃取生產登記所需的欄位。

必要欄位（**至少**需要其中一個組合）：
- 任務識別：task_id（生產任務 ID）或 order_no（訂單號）
- 捲料識別：roll_id（捲 ID）或 roll_no（捲號）
- length_m  : 消耗長度（公尺，數字）
- note      : 備註資訊

⚠️ 極重要規則（必須嚴格遵守）：
1. 發現任何必要欄位缺失，必須回傳 status="need_info" 並詢問用戶補充。
2. 你擁有權限協助登記生產紀錄，但必須先獲得必要參數。
3. Never hallucinate. Never fill in values not explicitly stated by the user.

回覆格式（純 JSON，無 markdown）：

情況 A — 資料完整：
{
  "status": "ready",
  "params": {
    "task_id": null,
    "order_no": "...",
    "roll_id": null,
    "roll_no": "...",
    "length_m": 0.0,
    "note": "..."
  }
}

情況 B — 資料不足：
{
  "status": "need_info",
  "missing": ["roll_no", "length_m"],
  "question_zh": "請提供捲號 (roll_no) 以及消耗長度 (length_m)。",
  "question_vi": "Vui lòng cung cấp số cuộn vải (roll_no) và chiều dài sử dụng (length_m)."
}
"""


# ---------------------------------------------------------------------------
# 輔助：解析 LLM JSON 輸出
# ---------------------------------------------------------------------------
_JSON_BLOCK = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.DOTALL | re.IGNORECASE)


def _parse_json(text: str) -> dict[str, Any] | None:
    """
    嘗試從 LLM 輸出中解析 JSON 物件。
    採用較強韌的「尋找最外層花括號」策略，避免受 Markdown 或雜訊干擾。
    """
    if not text:
        return None

    # Step 1: 移除思維標籤
    from .ai_service import _strip_think_tags
    text = _strip_think_tags(text)

    # Step 2: 尋找第一個 '{' 和最後一個 '}'
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1:
        logger.warning(f"[Dispatcher] 未能於回應中找到 JSON 物件: {text[:200]}...")
        return None

    raw_json = text[start : end + 1]

    # Step 3: 解析 JSON
    try:
        # 預處理：處理常見的 LLM JSON 錯誤 (如單引號或尾隨逗號)
        # 注意：此處僅做基本嘗試，若仍失敗則由 json.loads 拋出異常
        return json.loads(raw_json)
    except json.JSONDecodeError as e:
        # 進階嘗試：有些模型會輸出單引號 JSON，嘗試修正
        try:
            # 僅用於簡單的修正嘗試
            fixed = raw_json.replace("'", '"')
            return json.loads(fixed)
        except Exception:
            pass

        logger.error(f"[Dispatcher] JSON 解析失敗！原因: {e}")
        print(f"\n[AI DEBUG] 原始回應解析失敗內容:\n{text}\n")
        return None


# ---------------------------------------------------------------------------
# 公開 API
# ---------------------------------------------------------------------------

def dispatch(
    text: str,
    lang: str,
    db_path: str,
    processor,          # AIProcessor instance
    username: str = "operator",
    image_bytes: bytes | None = None,
    history: list[dict[str, str]] | None = None,
) -> dict[str, Any]:
    """
    主要入口：使用 Agent 架構（Ollama Tool Calling）處理用戶請求。
    若 Agent 失敗，降級到舊的意圖分類邏輯。
    """
    try:
        # 優先使用 Agent 架構
        from .agent import AgentRunner
        runner = AgentRunner(
            processor=processor,
            db_path=db_path,
            lang=lang,
            username=username,
            image_bytes=image_bytes,
            history=history,
        )
        result = runner.run(text)
        logger.info(f"[Dispatcher] Agent 完成：status={result.get('status')}, intent={result.get('intent')}")
        return result

    except Exception as e:
        logger.warning(f"[Dispatcher] Agent 架構失敗，降級到舊邏輯：{e}", exc_info=True)
        # 降級路徑：使用舊的 fallback chat
        return _fallback_chat(text, lang, processor)


def _get_empty_fallback(lang: str) -> str:
    """當回應為空時的保底字串。"""
    return (
        "抱歉，我現在無法完整處理您的請求。請提供更多細節（如布號、缸號等），或稍後再試。"
        if lang == "zh"
        else "Xin lỗi, tôi không thể xử lý yêu cầu lúc này. Vui lòng cung cấp thêm thông tin."
    )


def _fallback_chat(text: str, lang: str, processor) -> dict[str, Any]:
    """當解析失敗或意圖不明時的降級對話。"""
    chat_system_prompt = (
        "你是一個工廠管理系統的 AI 助理。請用專業、友善的語氣直接協助用戶。"
        "如果用戶想要登記資料（如新增布號、入庫等），請引導他們提供必要資訊（布號、缸號、重量等）。"
        "若用戶的語言是繁體中文請用繁體中文，若是越南文則用越南文。\n"
        "若你需要思考，請先將思考過程完全包裝在 <thinking> 和 </thinking> 標籤之內。"
    )
    reply = processor.generate(
        prompt=text,
        system_prompt=chat_system_prompt,
        max_tokens=1024,
        temperature=0.7
    )
    from .ai_service import _strip_think_tags
    cleaned = _strip_think_tags(reply)
    if not cleaned:
        cleaned = _get_empty_fallback(lang)
    return {"status": "ok", "intent": "unknown", "reply": cleaned}


def _handle_stock_in(
    text: str, lang: str, processor
) -> dict[str, Any]:
    """處理入庫登記意圖。"""
    raw = processor.generate(
        prompt=text,
        system_prompt=STOCK_IN_EXTRACT_SYSTEM,
        max_tokens=1024,
        temperature=0.0,
    )
    result = _parse_json(raw)

    if not result:
        return {"status": "error", "raw": raw}

    if result.get("status") == "need_info":
        reply_text = result.get("question_zh" if lang == "zh" else "question_vi")
        if not reply_text:
            # 嘗試從 raw 中提取
            from .ai_service import _strip_think_tags
            reply_text = _strip_think_tags(raw)
        
        return {
            "status": "need_info",
            "intent": "stock_in",
            "reply": reply_text or _get_empty_fallback(lang),
        }

    if result.get("status") == "ready":
        return {
            "status": "ready",
            "intent": "stock_in",
            "params": result.get("params", {}),
            "reply": reply_text or ("入庫登記資訊已備齊，請確認後送出。" if lang == "zh" else "Thông tin nhập kho đã đầy đủ."),
        }

    return {"status": "error", "raw": raw}


def _handle_production_log(
    text: str, lang: str, processor
) -> dict[str, Any]:
    """處理生產登記意圖。"""
    raw = processor.generate(
        prompt=text,
        system_prompt=PRODUCTION_LOG_EXTRACT_SYSTEM,
        max_tokens=1024,
        temperature=0.0,
    )
    result = _parse_json(raw)

    if not result:
        return {"status": "error", "raw": raw}

    reply_text = result.get("question_zh" if lang == "zh" else "question_vi")

    if result.get("status") == "need_info":
        if not reply_text:
            from .ai_service import _strip_think_tags
            reply_text = _strip_think_tags(raw)
            
        return {
            "status": "need_info",
            "intent": "production_log",
            "reply": reply_text or _get_empty_fallback(lang),
        }

    if result.get("status") == "ready":
        return {
            "status": "ready",
            "intent": "production_log",
            "params": result.get("params", {}),
            "reply": reply_text or ("生產登記資訊已備齊，請確認後送出。" if lang == "zh" else "Thông tin đã đầy đủ."),
        }

    return {"status": "error", "raw": raw}


def _parse_error(lang: str) -> dict[str, Any]:
    """降級錯誤回應。"""
    reply = ("系統暫時無法處理您的請求，請重試。" if lang == "zh" else "Lỗi hệ thống, vui lòng thử lại.")
    return {"status": "error", "intent": "unknown", "reply": reply}
