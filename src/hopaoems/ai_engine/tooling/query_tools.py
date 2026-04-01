from __future__ import annotations

from typing import Any

from .common import ToolContext


QUERY_DATABASE_SCHEMA = {
    "type": "function",
    "function": {
        "name": "query_database",
        "description": (
            "查詢工廠管理系統的資料庫。"
            "當用戶是在問庫存、訂單、生產、樣品、洗水或布料現況，而不是要求新增/修改/刪除資料時使用。"
            "你應傳入原始自然語言問題，工具會負責轉 SQL 與產生人類可讀答案。"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "question": {
                    "type": "string",
                    "description": "用戶原始問題，保留完整語意，不要自行改寫成 SQL。",
                }
            },
            "required": ["question"],
        },
    },
}


def exec_query_database(args: dict[str, Any], ctx: ToolContext) -> dict[str, Any]:
    from .. import sql_agent

    question = args.get("question", "")
    reply = sql_agent.ask(question, ctx.lang, ctx.db_path, ctx.processor)
    return {"reply": reply or "查詢未回傳結果。"}
