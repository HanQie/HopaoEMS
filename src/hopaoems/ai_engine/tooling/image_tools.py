from __future__ import annotations

from typing import Any

from .common import ToolContext


CLASSIFY_UPLOADED_IMAGE_SCHEMA = {
    "type": "function",
    "function": {
        "name": "classify_uploaded_image",
        "description": (
            "圖片意圖不明時的第一步：判斷圖片屬於樣品圖、對色表、入庫標籤、一般文件或未知。"
            "用戶只貼圖但沒清楚読用時，請先呼叫此工具判斷後再決定流程；不要直接假設是樣品圖或對色表。"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "image_id": {
                    "type": "string",
                    "description": "微庫中的圖片ID。若要讀取之前的圖片請提供此值。若為當前上傳的新圖則可省略。",
                }
            }
        },
    },
}

EXTRACT_STOCK_IN_DATA_FROM_IMAGE_SCHEMA = {
    "type": "function",
    "function": {
        "name": "extract_stock_in_data_from_image",
        "description": (
            "從用戶上傳的標籤、疋卡或布料照片中提取入庫資料。"
            "當用戶想用拍照圖片直接入庫，或說『從這張圖幫我讀布號/缸號/重量』時使用。"
            "執行後若 result 內含 missing_fields，"
            "請用自然語言提示用戶補充不足的欄位，再從右化工具。"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "image_id": {
                    "type": "string",
                    "description": "微庫中的圖片ID。若要讀取之前的圖片請提供此值。若為當前上傳的新圖則可省略。",
                }
            }
        },
    },
}

SUGGEST_SAMPLE_TITLE_FROM_IMAGE_SCHEMA = {
    "type": "function",
    "function": {
        "name": "suggest_sample_title_from_image",
        "description": (
            "根據用戶上傳的樣品圖片給出建議標題與關鍵字。"
            "當用戶說『這張圖叫什麼比較好』或準備建立 sample 但尚未決定標題時使用。"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "image_id": {
                    "type": "string",
                    "description": "微庫中的圖片ID。若要讀取之前的圖片請提供此值。若為當前上傳的新圖則可省略。",
                }
            }
        },
    },
}


def exec_classify_uploaded_image(args: dict[str, Any], ctx: ToolContext) -> dict[str, Any]:
    image_bytes = ctx.get_image(args.get("image_id"))
    if not image_bytes:
        return {"error": "沒有收到圖片，無法分類。"}

    from ..image_router import route_image_request

    result = route_image_request(args.get("text") or "", image_bytes)
    result["needs_user_clarification"] = result.get("confidence") == "low"
    return result


def exec_extract_stock_in_data_from_image(args: dict[str, Any], ctx: ToolContext) -> dict[str, Any]:
    image_bytes = ctx.get_image(args.get("image_id"))
    if not image_bytes:
        return {"error": "沒有收到圖片，無法提取入庫資料。"}

    from .. import ai_service

    data = ai_service.extract_stock_in_data_from_image(image_bytes)
    return {
        "status": "success",
        "data": data,
        "confidence": data.get("confidence", "low"),
        "missing_fields": data.get("missing_fields", []),
        "needs_user_clarification": data.get("confidence") == "low" or bool(data.get("missing_fields")),
        "message": "已從圖片中提取可辨識的入庫資料。",
    }


def exec_suggest_sample_title_from_image(args: dict[str, Any], ctx: ToolContext) -> dict[str, Any]:
    image_bytes = ctx.get_image(args.get("image_id"))
    if not image_bytes:
        return {"error": "沒有收到圖片，無法產生樣品標題建議。"}

    from .. import ai_service

    result = ai_service.suggest_sample_title_from_image(image_bytes)
    result["needs_user_clarification"] = bool(result.get("needs_user_confirmation"))
    return result
