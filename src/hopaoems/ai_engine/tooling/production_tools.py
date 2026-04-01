from __future__ import annotations

from typing import Any

from .common import ToolContext


LOG_PRODUCTION_SCHEMA = {
    "type": "function",
    "function": {
        "name": "log_production",
        "description": (
            "登記一筆生產消耗紀錄。"
            "前提：task_id + roll_id + length_m 三者就緒才執行；"
            "若任一欄位缺失，請使用 ask_user 向用戶詢問，不要猜測或用 0 填充。"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "task_id": {"type": "integer", "description": "生產任務 ID。"},
                "roll_id": {"type": "integer", "description": "捲料 ID。"},
                "length_m": {"type": "number", "description": "消耗長度（公尺）。"},
                "note": {"type": "string", "description": "備註。"},
                "mark_depleted": {"type": "boolean", "description": "是否同時標記捲料為用盡。"},
            },
            "required": ["task_id", "roll_id", "length_m"],
        },
    },
}


def exec_log_production(args: dict[str, Any], ctx: ToolContext) -> dict[str, Any]:
    from ...services import production_repo
    from ...services.db import query_db

    task_id = args["task_id"]
    roll_id = args["roll_id"]
    length_m = args["length_m"]
    note = args.get("note", "")
    mark_depleted = args.get("mark_depleted", False)

    user = query_db("SELECT id FROM users WHERE username = ?", (ctx.username,), one=True)
    operator_id = user["id"] if user else 1

    log_id = production_repo.create_log(
        task_id=task_id,
        roll_id=roll_id,
        length=length_m,
        note=note,
        operator_id=operator_id,
        mark_depleted=mark_depleted,
    )
    return {
        "status": "success",
        "log_id": log_id,
        "task_id": task_id,
        "roll_id": roll_id,
        "length_m": length_m,
    }
