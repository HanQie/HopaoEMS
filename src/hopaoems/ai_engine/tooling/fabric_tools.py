from __future__ import annotations

from typing import Any

from .common import ToolContext


STOCK_IN_FULL_SCHEMA = {
    "type": "function",
    "function": {
        "name": "stock_in_full",
        "description": (
            "完整入庫登記：布號 + 缸號 + 至少一筆捲料重量 三者具備時使用。"
            "若用戶只提供布號而無缸號，改用 register_fabric_only。"
            "關於捲號：若用戶未提供，請自動依序編號 1,2,3,...N；"
            "絕對不可把重量數偵當捶號。"
            "長度由系統自動估算，勿主動向用戶詢問長度；申誷時可省略 length_m 或填 0。"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "fabric_code": {"type": "string", "description": "布料代碼，例如 95278。"},
                "cylinder_no": {"type": "string", "description": "缸號，例如 V-001。"},
                "rolls": {
                    "type": "array",
                    "description": "捲料列表。若是多筆重量，應拆成多個 roll 物件。",
                    "items": {
                        "type": "object",
                        "properties": {
                            "roll_no": {
                                "type": "string",
                                "description": (
                                    "該疋的捲號。"
                                    "若用戶未提供，請自動依序命名為 '1', '2', '3'...（序轉）。"
                                    "如果用戶有連寫數字（如 '12345'）對應 N 個重量，請將其拆解為 '1','2','3'...。"
                                    "絕對不可把重量數值本身當作捲號。"
                                ),
                            },
                            "weight_kg": {"type": "number", "description": "該疋重量（公斤）。"},
                            "length_m": {
                                "type": "number",
                                "description": "長度（公尺）。系統會自動估算；若用戶未提及請省略此欄或填 0，不可主動向用戶詢問長度。",
                            },
                        },
                        "required": ["roll_no", "weight_kg"],
                    },
                },
                "note": {"type": "string", "description": "備註。"},
                "material": {"type": "string", "description": "材質。"},
                "width_inch": {"type": "number", "description": "門幅（英吋）。"},
                "weight_gsm": {"type": "number", "description": "克重（GSM）。"},
            },
            "required": ["fabric_code", "cylinder_no", "rolls"],
        },
    },
}

REGISTER_FABRIC_ONLY_SCHEMA = {
    "type": "function",
    "function": {
        "name": "register_fabric_only",
        "description": (
            "用戶只提供布號而尚未提及缸號時，請使用此工具、不要等待缸號。"
            "此工具會建立布號主檔並預留後續輸入缸號的空間，執行後請提示用戶後續補充缸號。"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "fabric_code": {"type": "string", "description": "布料代碼。"},
                "material": {"type": "string", "description": "材質。"},
                "width_inch": {"type": "number", "description": "門幅（英吋）。"},
                "weight_gsm": {"type": "number", "description": "克重（GSM）。"},
                "note": {"type": "string", "description": "備註。"},
            },
            "required": ["fabric_code"],
        },
    },
}

LOOKUP_FABRIC_SCHEMA = {
    "type": "function",
    "function": {
        "name": "lookup_fabric",
        "description": "查找某個布號是否已存在。適合在寫入前先確認，或用戶直接詢問布號資訊時使用。",
        "parameters": {
            "type": "object",
            "properties": {
                "fabric_code": {"type": "string", "description": "要查的布號。"},
            },
            "required": ["fabric_code"],
        },
    },
}

LOOKUP_ROLL_SCHEMA = {
    "type": "function",
    "function": {
        "name": "lookup_roll",
        "description": "按布號或捲號搜索仍在庫的捲料。當用戶說要找某一疋、某一卷或某布號庫存時使用。",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "搜索關鍵字（布號或捲號）。"},
            },
            "required": ["query"],
        },
    },
}

DELETE_FABRIC_SCHEMA = {
    "type": "function",
    "function": {
        "name": "delete_fabric",
        "description": (
            "徹底刪除指定布號及其所有缸號與捲料紀錄。"
            "只在用戶明確要求刪除布號時使用，不能拿來代替查詢或更新。"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "fabric_code": {"type": "string", "description": "要刪除的布號代碼。"},
            },
            "required": ["fabric_code"],
        },
    },
}


def _handle_fabric_units(args: dict[str, Any], existing_data: dict[str, Any] | None = None) -> tuple[float | None, float | None]:
    width_inch = args.get("width_inch")
    weight_gsm = args.get("weight_gsm")

    current_width_mm = existing_data.get("width_mm") if existing_data else None
    current_yard_weight_gyd = existing_data.get("yard_weight_gyd") if existing_data else None

    width_mm = current_width_mm
    yard_weight_gyd = current_yard_weight_gyd

    if width_inch:
        width_mm = round(float(width_inch) * 25.4, 1)

    if weight_gsm:
        w_mm = width_mm or current_width_mm
        if w_mm:
            width_m = float(w_mm) / 1000.0
            yard_weight_gyd = round(float(weight_gsm) * width_m * 0.9144, 1)

    return width_mm, yard_weight_gyd


def exec_stock_in_full(args: dict[str, Any], ctx: ToolContext) -> dict[str, Any]:
    from ...services import fabric_repo
    from ...services.db import query_db

    fabric_code = args["fabric_code"]
    cylinder_no = str(args["cylinder_no"])
    rolls_raw = args.get("rolls", [])
    note = args.get("note")

    fabric = fabric_repo.get_fabric_by_code(fabric_code)
    width_mm, yard_weight_gyd = _handle_fabric_units(args, dict(fabric) if fabric else None)

    if not fabric:
        fabric = fabric_repo.create_fabric(
            fabric_code=fabric_code,
            material_type=args.get("material") or None,
            width_mm=width_mm,
            gram_per_yard=yard_weight_gyd,
            remark=note or None,
        )
    else:
        fabric = dict(fabric)
        fabric_repo.update_fabric(
            id=fabric["id"],
            fabric_code=fabric_code,
            material_type=args.get("material") or fabric.get("material"),
            width_mm=width_mm,
            gram_per_yard=yard_weight_gyd,
            remark=note if note is not None else fabric.get("remark"),
        )
        fabric = fabric_repo.get_fabric(fabric["id"])

    fabric_id = fabric["id"]
    roll_rows = []
    used_nos = set()
    cylinder = query_db(
        "SELECT id FROM cylinders WHERE fabric_id = ? AND cylinder_no = ?",
        (fabric_id, cylinder_no),
        one=True,
    )
    if cylinder:
        existing_rolls = query_db("SELECT roll_no FROM rolls WHERE cylinder_id = ?", (cylinder["id"],))
        for row in existing_rolls:
            used_nos.add(row["roll_no"])

    for i, row in enumerate(rolls_raw):
        roll_no = str(row.get("roll_no", "")) or f"R{i + 1}"
        original_roll_no = roll_no
        counter = 1
        while roll_no in used_nos:
            roll_no = f"{original_roll_no}-{counter}"
            counter += 1
        used_nos.add(roll_no)
        roll_rows.append(
            {
                "roll_no": roll_no,
                "length_m": row.get("length_m", 0),
                "weight_kg": row.get("weight_kg"),
                "remark": note if note is not None else "",
            }
        )

    if roll_rows:
        fabric_repo.create_stock_in_batch(
            fabric_id=fabric_id,
            cylinder_no=cylinder_no,
            roll_rows=roll_rows,
            user_name=ctx.username,
        )

    return {
        "status": "success",
        "fabric_id": fabric_id,
        "fabric_code": fabric_code,
        "cylinder_no": cylinder_no,
        "rolls_created": len(roll_rows),
    }


def exec_register_fabric_only(args: dict[str, Any], ctx: ToolContext) -> dict[str, Any]:
    from ...services import fabric_repo

    fabric_code = args["fabric_code"]
    note = args.get("note")
    existing = fabric_repo.get_fabric_by_code(fabric_code)
    width_mm, yard_weight_gyd = _handle_fabric_units(args, dict(existing) if existing else None)

    if existing:
        existing = dict(existing)
        new_material = args.get("material") or existing.get("material")
        new_remark = note if note is not None else existing.get("remark")
        fabric_repo.update_fabric(
            id=existing["id"],
            fabric_code=fabric_code,
            material_type=new_material,
            width_mm=width_mm,
            gram_per_yard=yard_weight_gyd,
            remark=new_remark,
        )
        return {
            "status": "updated",
            "fabric_id": existing["id"],
            "fabric_code": fabric_code,
            "message": f"布號 {fabric_code} 已更新（材質：{new_material or '-'}，幅寬：{width_mm or '-'} mm，克重：{yard_weight_gyd or '-'} g/yd）。",
        }

    fabric = fabric_repo.create_fabric(
        fabric_code=fabric_code,
        material_type=args.get("material") or None,
        width_mm=width_mm,
        gram_per_yard=yard_weight_gyd,
        remark=note if note is not None else None,
    )
    return {
        "status": "created",
        "fabric_id": fabric["id"],
        "fabric_code": fabric_code,
        "message": f"已成功建立布號 {fabric_code}（材質：{args.get('material') or '-'}，幅寬：{width_mm or '-'} mm，克重：{yard_weight_gyd or '-'} g/yd）。",
    }


def exec_lookup_fabric(args: dict[str, Any], ctx: ToolContext) -> dict[str, Any]:
    from ...services import fabric_repo

    fabric_code = args["fabric_code"]
    fabric = fabric_repo.get_fabric_by_code(fabric_code)
    if not fabric:
        return {"found": False, "fabric_code": fabric_code}

    fabric = dict(fabric)
    return {
        "found": True,
        "fabric_id": fabric["id"],
        "fabric_code": fabric["fabric_code"],
        "material": fabric.get("material"),
        "width_mm": fabric.get("width_mm"),
        "yard_weight_gyd": fabric.get("yard_weight_gyd"),
        "remark": fabric.get("remark"),
    }


def exec_lookup_roll(args: dict[str, Any], ctx: ToolContext) -> dict[str, Any]:
    from ...services import fabric_repo

    query = args.get("query", "")
    rolls = fabric_repo.search_in_stock_rolls(query=query)
    results = []
    for row in (rolls or [])[:20]:
        results.append(
            {
                "roll_id": row["id"],
                "roll_no": row["roll_no"],
                "fabric_code": row.get("fabric_no", ""),
                "cylinder_no": row.get("cylinder_no", ""),
                "length_m": row["length_m"],
                "status": row["status"],
            }
        )
    return {"count": len(results), "rolls": results}


def exec_delete_fabric(args: dict[str, Any], ctx: ToolContext) -> dict[str, Any]:
    from ...services import fabric_repo

    fabric_code = args.get("fabric_code")
    if not fabric_code:
        return {"error": "Missing fabric_code parameter"}
    try:
        fabric_repo.delete_fabric_cascade(fabric_code)
        return {
            "status": "deleted",
            "fabric_code": fabric_code,
            "message": f"布號 {fabric_code} 及其所有的缸號與捲料紀錄已成功徹底刪除。",
        }
    except Exception as e:
        return {"error": str(e)}
