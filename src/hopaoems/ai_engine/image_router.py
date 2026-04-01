from __future__ import annotations

import re
from typing import Any


def detect_image_intent(text: str) -> str:
    lowered = (text or "").lower()
    color_words = (
        "校色", "校色紀錄", "對色", "對色紀錄", "換色", "色表", "顏色",
        "數色", "數色紀錄", "配色", "配色紀錄", "rgb", "lab", "ymck",
        "目標色", "目標顏色", "目標值", "lab值", "l*a*b",
    )
    apply_words = (
        "填入", "填進", "填寫", "填上", "登記", "寫入", "套用", "同步",
        "補充", "補上", "補齊", "更新", "覆蓋", "改成",
        "一樣", "照圖", "按圖", "欄位", "紀錄裡",
    )
    search_words = ("找", "搜尋", "搜索", "查", "叫什麼", "名稱", "相似", "是哪個")
    stock_words = ("入庫", "布號", "缸號", "疋", "重量", "標籤", "roll", "fabric", "stock")

    if any(word in lowered for word in color_words) and any(word in lowered for word in apply_words):
        return "color_correction_apply"
    if any(word in lowered for word in color_words):
        return "color_correction_extract"
    if any(word in lowered for word in stock_words):
        return "stock_in_from_image"
    if any(word in lowered for word in search_words):
        return "search_by_image"
    return "generic_image"


def route_image_request(text: str, image_bytes: bytes | None) -> dict[str, Any]:
    if not image_bytes:
        return {
            "intent": "text_only",
            "image_kind": "none",
            "extractor": "none",
            "confidence": "high",
            "reason": "no_image",
        }

    from . import ai_service

    intent = detect_image_intent(text)
    image_info = ai_service.classify_uploaded_image_local(image_bytes)
    image_kind = image_info.get("image_kind", "unknown")
    confidence = image_info.get("confidence", "low")

    extractor = "vl"
    if image_kind in {"color_table", "stock_in_label", "document"}:
        extractor = "ocr_parser"
    elif image_kind == "sample_photo" and intent == "search_by_image":
        extractor = "embedding_or_vl"

    if intent.startswith("color_correction"):
        extractor = "ocr_parser"
    elif intent == "stock_in_from_image":
        extractor = "ocr_parser"

    return {
        "intent": intent,
        "image_kind": image_kind,
        "extractor": extractor,
        "confidence": confidence,
        "reason": image_info.get("reason", ""),
    }


def extract_sample_query_candidates(text: str) -> list[str]:
    raw = (text or "").strip()
    if not raw:
        return []

    candidates: list[str] = []
    patterns = [
        r"(?:樣本|樣品)\s*([^\s，。,；;:：]+)",
        r"將\s*([^\s，。,；;:：]+?)\s*的(?:校色|對色|換色)",
        r"把\s*([^\s，。,；;:：]+?)\s*的(?:校色|對色|換色)",
        r"([^\s，。,；;:：]+?)\s*的(?:校色|對色|換色)",
    ]
    for pattern in patterns:
        for match in re.finditer(pattern, raw):
            value = (match.group(1) or "").strip()
            if value and value not in candidates:
                candidates.append(value)

    cleaned = re.sub(r"(將|把|幫我|請|圖的數據|數據|填入|填進|寫入|登記|校色紀錄|校色|對色|換色|相應的欄位|欄位|裡|到)", " ", raw)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    if cleaned and cleaned not in candidates:
        candidates.append(cleaned)

    if raw not in candidates:
        candidates.append(raw)
    return candidates
