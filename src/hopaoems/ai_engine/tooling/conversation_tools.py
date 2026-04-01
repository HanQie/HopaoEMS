from __future__ import annotations

from typing import Any

from .common import ToolContext


ASK_USER_SCHEMA = {
    "type": "function",
    "function": {
        "name": "ask_user",
        "description": (
            "通知用戶某個需要的欄位。"
            "僅在缺少關鍵欄位而無法安全執行時才使用；"
            "若資訊不全但可執行部分任務，請先執行再在回覆中提示用戶補充。"
            "問題要具體且提供明確選項（A/B 形式）。"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "question_zh": {
                    "type": "string",
                    "description": "向用戶提出的問題（繁體中文）。",
                },
                "question_vi": {
                    "type": "string",
                    "description": "向用戶提出的問題（越南語）。",
                },
            },
            "required": ["question_zh", "question_vi"],
        },
    },
}


def exec_ask_user(args: dict[str, Any], ctx: ToolContext) -> dict[str, Any]:
    return {
        "action": "ask_user",
        "question_zh": args.get("question_zh", ""),
        "question_vi": args.get("question_vi", ""),
    }
