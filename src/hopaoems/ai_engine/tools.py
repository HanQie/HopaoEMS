"""
tools.py
========
Agent Tool 定義層。

每個 Tool 包含：
  - SCHEMA : Ollama tools 格式的 JSON Schema（傳給模型做 Function Calling）
  - execute(): 實際執行邏輯（調用 repo 層）

Tools 一覽：
  1. query_database        — 自然語言查詢資料庫
  2. stock_in_full          — 完整入庫（布號 + 缸號 + 捲料列表）
  3. partial_stock_in       — 部分入庫（僅布號）
  4. log_production         — 登記生產記錄
  5. lookup_fabric          — 查找布號是否存在
  6. lookup_roll            — 搜索在庫捲料
  7. ask_user               — 向用戶反問補充資訊
  8. create_sample          — 建立樣品記錄
  9. search_sample_by_image — 以圖搜樣品（CLIP 向量比對）
 10. list_samples           — 搜索/列出樣品
"""

from __future__ import annotations

import json
import logging
from typing import Any

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════
# Tool Schemas（Ollama tools 格式）
# ═══════════════════════════════════════════════════════════════════════════

TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "extract_color_correction_data",
            "description": "從用戶上傳的圖片中提取顏色校正表格數據（如 RGB -> LAB/YMCK）。當用戶提到「就在圖中」、發送顏色表圖片、或你找不到文字數據時使用。",
            "parameters": {
                "type": "object",
                "properties": {
                    "hint": {
                        "type": "string",
                        "description": "提供給視覺模型的額外提示（例如：提取這張圖中的 RGB 和 LAB 對應表）"
                    }
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "batch_record_color_corrections",
            "description": "批量記錄樣品顏色校正/換色數據。當用戶提供顏色表格（如 RGB 對應 LAB 或 YMCK）時使用。",
            "parameters": {
                "type": "object",
                "properties": {
                    "sample_query": {
                        "type": "string",
                        "description": "樣品編號或標題（自然語言或精確值）"
                    },
                    "corrections": {
                        "type": "array",
                        "description": "顏色校正列表",
                        "items": {
                            "type": "object",
                            "properties": {
                                "rgb_r": {"type": "integer", "description": "輸入層 R (0-255)"},
                                "rgb_g": {"type": "integer", "description": "輸入層 G (0-255)"},
                                "rgb_b": {"type": "integer", "description": "輸入層 B (0-255)"},
                                "target_mode": {"type": "string", "description": "目標模式 (例如 'LAB', 'YMCKBHFm', 'note')"},
                                "target_l": {"type": "number", "description": "LAB 的 L"},
                                "target_a": {"type": "number", "description": "LAB 的 A"},
                                "target_b": {"type": "number", "description": "LAB 的 B"},
                                "target_note": {"type": "string", "description": "非 LAB 模式下的數值字串或備註"}
                            },
                            "required": ["rgb_r", "rgb_g", "rgb_b", "target_mode"]
                        }
                    }
                },
                "required": ["sample_query", "corrections"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "query_database",
            "description": (
                "查詢工廠管理系統的資料庫。可用於查詢庫存、訂單、生產記錄、布料資訊等。"
                "將用戶的自然語言問題轉換為 SQL 並執行，回傳人類可讀的回答。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "question": {
                        "type": "string",
                        "description": "用戶的查詢問題（自然語言）",
                    }
                },
                "required": ["question"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "stock_in_full",
            "description": (
                "完整入庫登記：當用戶同時提供了布號、缸號、以及至少一筆捲料資料時使用。"
                "會建立布號（如不存在）、缸號、以及所有捲料記錄。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "fabric_code": {
                        "type": "string",
                        "description": "布料代碼（例如 F-001、95278）",
                    },
                    "cylinder_no": {
                        "type": "string",
                        "description": "缸號（例如 V-001）",
                    },
                    "rolls": {
                        "type": "array",
                        "description": "捲料列表",
                        "items": {
                            "type": "object",
                            "properties": {
                                "roll_no": {
                                    "type": "string",
                                    "description": "該疋的單獨捲號。如果是批量入庫且用戶提供連寫數字（如 12345），請拆解給每一疋分別填入 1, 2, 3, 4, 5。如果用戶沒提供捲號，請你自動幫每一疋填上 1, 2, 3, 4... 作為捲號。絕對不能把重量數值當成捲號！",
                                },
                                "weight_kg": {
                                    "type": "number",
                                    "description": "該疋的重量（公斤）",
                                },
                                "length_m": {
                                    "type": "number",
                                    "description": "長度（公尺）。禁止主動詢問此欄位，系統會自動根據克重換算。未提供時請直接留空或設為0。",
                                },
                            },
                            "required": ["roll_no", "weight_kg"],
                        },
                    },
                    "note": {
                        "type": "string",
                        "description": "備註（其他資訊）",
                    },
                    "material": {
                        "type": "string",
                        "description": "材質（例如 nylon、cotton、聚酯纖維等）",
                    },
                    "width_inch": {
                        "type": "number",
                        "description": "門幅寬度（英吋/inch），系統會自動換算為 mm",
                    },
                    "weight_gsm": {
                        "type": "number",
                        "description": "克重（g/m² 或 GSM），系統會根據門幅換算為 g/yd",
                    },
                },
                "required": ["fabric_code", "cylinder_no", "rolls"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "register_fabric_only",
            "description": (
                "僅建立或註冊布號主檔：當用戶只想新增布號，或者目前沒有缸號/捲料資訊時使用。"
                "只會建立布號記錄（如不存在），不會建立缸號或捲料。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "fabric_code": {
                        "type": "string",
                        "description": "布料代碼（例如 95278）",
                    },
                    "material": {
                        "type": "string",
                        "description": "材質（例如 nylon、cotton、聚酯纖維等）",
                    },
                    "width_inch": {
                        "type": "number",
                        "description": "門幅寬度（英吋/inch），系統會自動換算為 mm",
                    },
                    "weight_gsm": {
                        "type": "number",
                        "description": "克重（g/m² 或 GSM），系統會根據門幅換算為 g/yd",
                    },
                    "note": {
                        "type": "string",
                        "description": "備註（其他資訊）",
                    },
                },
                "required": ["fabric_code"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "log_production",
            "description": (
                "登記一筆生產記錄（消耗布匹）。"
                "需要提供任務 ID、捲料 ID、消耗長度等資訊。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "task_id": {
                        "type": "integer",
                        "description": "生產任務 ID",
                    },
                    "roll_id": {
                        "type": "integer",
                        "description": "捲料 ID",
                    },
                    "length_m": {
                        "type": "number",
                        "description": "消耗長度（公尺）",
                    },
                    "note": {
                        "type": "string",
                        "description": "備註",
                    },
                    "mark_depleted": {
                        "type": "boolean",
                        "description": "是否標記捲料為用盡",
                    },
                },
                "required": ["task_id", "roll_id", "length_m"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "lookup_fabric",
            "description": (
                "查找某個布號是否已存在於系統中。"
                "回傳布號的詳細資料或表示不存在。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "fabric_code": {
                        "type": "string",
                        "description": "要查找的布料代碼",
                    }
                },
                "required": ["fabric_code"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "lookup_roll",
            "description": (
                "搜索在庫的捲料。可按布號或捲號模糊搜索。"
                "回傳符合條件的在庫捲料列表。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "搜索關鍵字（布號或捲號）",
                    }
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "ask_user",
            "description": (
                "當你需要更多資訊才能完成用戶的請求時，使用此工具向用戶提問。"
                "例如缺少缸號、捲號、長度等必要欄位時。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "question_zh": {
                        "type": "string",
                        "description": "向用戶提出的問題（繁體中文）",
                    },
                    "question_vi": {
                        "type": "string",
                        "description": "向用戶提出的問題（越南語）",
                    },
                },
                "required": ["question_zh", "question_vi"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_sample",
            "description": (
                "建立一個新的樣品記錄。"
                "需要提供樣品編號和標題，可選提供布號、備註等。"
                "注意：圖片上傳由系統另外處理，此工具只建立文字記錄。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "sample_no": {
                        "type": "string",
                        "description": "樣品編號（例如 S-001）",
                    },
                    "title": {
                        "type": "string",
                        "description": "樣品名稱/標題",
                    },
                    "fabric_no": {
                        "type": "string",
                        "description": "對應的布號",
                    },
                    "remark": {
                        "type": "string",
                        "description": "備註",
                    },
                },
                "required": ["sample_no", "title"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_sample_by_image",
            "description": (
                "以圖搜樣品：當用戶發送了一張圖片，使用此工具找出系統中與該圖片最相似的樣品。"
                "利用 CLIP 圖片向量計算相似度，回傳最匹配的樣品列表。"
                "此工具無需參數，會自動使用用戶上傳的圖片。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "top_k": {
                        "type": "integer",
                        "description": "回傳前幾個最相似的結果（預設 5）",
                    }
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_samples",
            "description": (
                "搜索或列出系統中的樣品。可按樣品編號或標題模糊搜索。"
                "回傳符合條件的樣品列表。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "搜索關鍵字（樣品編號或標題）",
                    }
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "edit_sample",
            "description": (
                "修改樣品的資料，例如更新標題、布號或備註。"
                "可以透過樣品編號或樣品標題模糊尋找。"
                "如果用戶要求「清空」或「移除備註」，請務必傳入 note 參數，值為空字串 \"\"。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "要修改的樣品編號或標題（用於搜尋比對）",
                    },
                    "title": {
                        "type": "string",
                        "description": "新標題（若不修改請省略）",
                    },
                    "fabric_no": {
                        "type": "string",
                        "description": "新的關聯布號（若不修改請省略）",
                    },
                    "remark": {
                        "type": "string",
                        "description": "新備註。若要清空則必須明確提供空字串 \"\"。（若不修改請省略）",
                    },
                },
                "required": ["query"],
            },
        },
    },
]


# ═══════════════════════════════════════════════════════════════════════════
# Tool 執行器
# ═══════════════════════════════════════════════════════════════════════════

class ToolContext:
    """Tool 執行時的上下文環境。"""

    def __init__(self, db_path: str, lang: str, username: str, processor,
                 image_bytes: bytes | None = None):
        self.db_path = db_path
        self.lang = lang
        self.username = username
        self.processor = processor
        self.image_bytes = image_bytes  # 用戶上傳的圖片（用於 search_sample_by_image）


def execute_tool(name: str, arguments: dict[str, Any], ctx: ToolContext) -> dict[str, Any]:
    """
    根據 Tool 名稱分派執行。回傳 dict 結果（將被注入回 Agent 對話）。
    """
    logger.info(f"[Tools] 執行 Tool: {name}，參數: {json.dumps(arguments, ensure_ascii=False)[:200]}")

    try:
        if name == "query_database":
            return _exec_query_database(arguments, ctx)
        elif name == "stock_in_full":
            return _exec_stock_in_full(arguments, ctx)
        elif name == "register_fabric_only":
            return _exec_partial_stock_in(arguments, ctx)
        elif name == "log_production":
            return _exec_log_production(arguments, ctx)
        elif name == "lookup_fabric":
            return _exec_lookup_fabric(arguments, ctx)
        elif name == "lookup_roll":
            return _exec_lookup_roll(arguments, ctx)
        elif name == "ask_user":
            return _exec_ask_user(arguments, ctx)
        elif name == "create_sample":
            return _exec_create_sample(arguments, ctx)
        elif name == "search_sample_by_image":
            return _exec_search_sample_by_image(arguments, ctx)
        elif name == "list_samples":
            return _exec_list_samples(arguments, ctx)
        elif name == "edit_sample":
            return _exec_edit_sample(arguments, ctx)
        elif name == "batch_record_color_corrections":
            return _exec_batch_record_color_corrections(arguments, ctx)
        elif name == "extract_color_correction_data":
            return _exec_extract_color_correction_data(arguments, ctx)
        elif name == "delete_fabric":
            return _exec_delete_fabric(arguments, ctx)
        else:
            return {"error": f"未知的 Tool: {name}"}
    except Exception as e:
        logger.error(f"[Tools] Tool '{name}' 執行失敗: {e}", exc_info=True)
        return {"error": str(e)}


# ---------------------------------------------------------------------------
# 個別 Tool 實作
# ---------------------------------------------------------------------------

def _exec_query_database(args: dict, ctx: ToolContext) -> dict:
    """自然語言查詢 → SQL → 人類語言回答。"""
    from . import sql_agent
    question = args.get("question", "")
    reply = sql_agent.ask(question, ctx.lang, ctx.db_path, ctx.processor)
    return {"reply": reply or "查詢未回傳結果。"}


def _handle_fabric_units(args: dict, existing_data: dict | None = None) -> tuple:
    """處理布料單位換算 (Inch -> mm, GSM -> g/yd)。"""
    width_inch = args.get("width_inch")
    weight_gsm = args.get("weight_gsm")
    
    # 取得現有值作為備援
    current_width_mm = existing_data.get("width_mm") if existing_data else None
    current_yard_weight_gyd = existing_data.get("yard_weight_gyd") if existing_data else None
    
    width_mm = current_width_mm
    yard_weight_gyd = current_yard_weight_gyd
    
    if width_inch:
        width_mm = round(float(width_inch) * 25.4, 1)
        
    if weight_gsm:
        # 換算 g/yd 需要門幅資訊
        # 如果用戶這次有給 width_inch，用這次的；否則看現有資料有沒有 width_mm
        w_mm = width_mm or current_width_mm
        if w_mm:
            # g/yd = GSM * (width_m) * 0.9144
            width_m = float(w_mm) / 1000.0
            yard_weight_gyd = round(float(weight_gsm) * width_m * 0.9144, 1)
            
    return width_mm, yard_weight_gyd


def _exec_stock_in_full(args: dict, ctx: ToolContext) -> dict:
    """完整入庫：布號 + 缸號 + 捲料列表。"""
    from ..services import fabric_repo

    fabric_code = args["fabric_code"]
    cylinder_no = str(args["cylinder_no"])
    rolls_raw = args.get("rolls", [])
    note = args.get("note") # 使用 get 而非 get(..., "") 以區分未提供與空字串

    # 1. 確保布號存在
    fabric = fabric_repo.get_fabric_by_code(fabric_code)
    
    # 處理單位換算
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
        # 如果布號已存在，也更新其材質與備註（若有提供）
        new_material = args.get("material") or fabric.get("material")
        
        # 如果 note 是 None (AI 沒提供)，保留原樣；如果是 "" (AI 提供空字串)，則清除
        new_remark = note if note is not None else fabric.get("remark")
        
        fabric_repo.update_fabric(
            id=fabric["id"],
            fabric_code=fabric_code,
            material_type=new_material,
            width_mm=width_mm,
            gram_per_yard=yard_weight_gyd,
            remark=new_remark,
        )
        # 重新取得更新後的資料
        fabric = fabric_repo.get_fabric(fabric["id"])
    fabric_id = fabric["id"]

    # 2. 準備捲料資料 (處理重複捲號問題)
    from ..services.db import query_db
    roll_rows = []
    used_nos = set()
    
    # 預先載入資料庫中已存在的捲號，避免 SQLite Unique Constraint 錯誤
    cylinder = query_db('SELECT id FROM cylinders WHERE fabric_id = ? AND cylinder_no = ?', (fabric_id, cylinder_no), one=True)
    if cylinder:
        existing_rolls = query_db('SELECT roll_no FROM rolls WHERE cylinder_id = ?', (cylinder['id'],))
        for r in existing_rolls:
            used_nos.add(r['roll_no'])
    for i, r in enumerate(rolls_raw):
        rno = str(r.get("roll_no", ""))
        if not rno:
            rno = f"R{i+1}"
        
        # 如果重複就把序號帶上去
        orig_rno = rno
        counter = 1
        while rno in used_nos:
            rno = f"{orig_rno}-{counter}"
            counter += 1
        used_nos.add(rno)

        roll_rows.append({
            "roll_no": rno,
            "length_m": r.get("length_m", 0),
            "weight_kg": r.get("weight_kg"),
            "remark": note if note is not None else "",
        })

    # 3. 批次入庫
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


def _exec_partial_stock_in(args: dict, ctx: ToolContext) -> dict:
    """部分入庫：僅建立布號記錄。"""
    from ..services import fabric_repo

    fabric_code = args["fabric_code"]
    note = args.get("note")

    # 檢查是否已存在
    existing = fabric_repo.get_fabric_by_code(fabric_code)
    
    # 處理單位換算
    width_mm, yard_weight_gyd = _handle_fabric_units(args, dict(existing) if existing else None)
    
    if existing:
        existing = dict(existing)
        # 如果用戶提供了材質或備註，則更新現有記錄
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

    # 建立新布號
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


def _exec_log_production(args: dict, ctx: ToolContext) -> dict:
    """登記生產記錄。"""
    from ..services import production_repo
    from ..services.db import query_db

    task_id = args["task_id"]
    roll_id = args["roll_id"]
    length_m = args["length_m"]
    note = args.get("note", "")
    mark_depleted = args.get("mark_depleted", False)

    # 取得 operator_id
    user = query_db(
        "SELECT id FROM users WHERE username = ?",
        (ctx.username,),
        one=True,
    )
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


def _exec_lookup_fabric(args: dict, ctx: ToolContext) -> dict:
    """查找布號。"""
    from ..services import fabric_repo

    fabric_code = args["fabric_code"]
    fabric = fabric_repo.get_fabric_by_code(fabric_code)
    if fabric:
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
    return {"found": False, "fabric_code": fabric_code}


def _exec_lookup_roll(args: dict, ctx: ToolContext) -> dict:
    """搜索在庫捲料。"""
    from ..services import fabric_repo

    query = args.get("query", "")
    rolls = fabric_repo.search_in_stock_rolls(query=query)
    results = []
    for r in (rolls or [])[:20]:  # 限制回傳數量
        results.append({
            "roll_id": r["id"],
            "roll_no": r["roll_no"],
            "fabric_code": r.get("fabric_no", ""),
            "cylinder_no": r.get("cylinder_no", ""),
            "length_m": r["length_m"],
            "status": r["status"],
        })
    return {"count": len(results), "rolls": results}


def _exec_ask_user(args: dict, ctx: ToolContext) -> dict:
    """向用戶反問。"""
    return {
        "action": "ask_user",
        "question_zh": args.get("question_zh", ""),
        "question_vi": args.get("question_vi", ""),
    }


def _exec_create_sample(args: dict, ctx: ToolContext) -> dict:
    """建立樣品記錄。"""
    from ..services import sample_repo

    sample_no = args["sample_no"]
    title = args["title"]
    fabric_no = args.get("fabric_no", "")
    remark = args.get("remark", "")

    # 檢查是否已存在同樣品編號
    from ..services.db import query_db
    existing = query_db(
        "SELECT id, sample_no, title FROM samples WHERE sample_no = ?",
        (sample_no,), one=True,
    )
    if existing:
        return {
            "status": "already_exists",
            "sample_id": existing["id"],
            "sample_no": existing["sample_no"],
            "title": existing["title"],
            "message": f"樣品 {sample_no} 已存在。",
        }

    sample_id = sample_repo.create_sample(
        sample_no=sample_no,
        title=title,
        fabric_no=fabric_no,
        remark=remark or None,
    )
    return {
        "status": "created",
        "sample_id": sample_id,
        "sample_no": sample_no,
        "title": title,
        "message": f"已成功建立樣品 {sample_no}：{title}",
    }


def _exec_search_sample_by_image(args: dict, ctx: ToolContext) -> dict:
    """以圖搜樣品：使用 CLIP 向量比對 samples 的 preview 圖片。"""
    if not ctx.image_bytes:
        return {"error": "沒有收到圖片。請上傳一張圖片再試。"}

    top_k = args.get("top_k", 5)

    try:
        from . import ai_service
        import os
        import numpy as np
        from flask import current_app

        # 1. 計算查詢圖片的 CLIP embedding
        query_embedding = ai_service.compute_image_embedding(ctx.image_bytes)
        q_norm = query_embedding / (np.linalg.norm(query_embedding) + 1e-9)

        # 2. 遍歷所有有 preview_path 的 samples，計算相似度
        from ..services.db import query_db
        samples = query_db(
            "SELECT id, sample_no, title, fabric_no, preview_path "
            "FROM samples WHERE preview_path IS NOT NULL AND preview_path != ''"
        )

        if not samples:
            return {"count": 0, "samples": [], "message": "系統中沒有含預覽圖的樣品。"}

        upload_dir = current_app.config.get("SAMPLES_UPLOAD_DIR", "")
        results = []

        for s in samples:
            img_path = os.path.join(upload_dir, s["preview_path"])
            if not os.path.exists(img_path):
                continue

            try:
                with open(img_path, "rb") as f:
                    sample_bytes = f.read()
                sample_embedding = ai_service.compute_image_embedding(sample_bytes)
                s_norm = sample_embedding / (np.linalg.norm(sample_embedding) + 1e-9)
                score = float(np.dot(q_norm, s_norm))

                results.append({
                    "sample_id": s["id"],
                    "sample_no": s["sample_no"],
                    "title": s["title"],
                    "fabric_no": s["fabric_no"],
                    "score": round(score, 4),
                })
            except Exception as e:
                logger.warning(f"[Tools] 跳過 sample {s['id']}：{e}")
                continue

        # 按相似度排序
        results.sort(key=lambda x: x["score"], reverse=True)
        top_results = results[:top_k]

        return {
            "count": len(top_results),
            "samples": top_results,
            "message": (
                f"找到 {len(top_results)} 個相似樣品。"
                if top_results
                else "沒有找到相似的樣品。"
            ),
        }
    except ImportError as e:
        return {"error": f"缺少必要的依賴套件：{e}。請安裝 sentence-transformers。"}
    except Exception as e:
        logger.error(f"[Tools] search_sample_by_image 失敗: {e}", exc_info=True)
        return {"error": str(e)}


def _exec_list_samples(args: dict, ctx: ToolContext) -> dict:
    """搜索/列出樣品。"""
    from ..services import sample_repo

    query = args.get("query", "")
    samples = sample_repo.list_samples(q=query if query else None)
    results = []
    for s in (samples or [])[:20]:
        results.append({
            "sample_id": s["id"],
            "sample_no": s["sample_no"],
            "title": s["title"],
            "fabric_no": s.get("fabric_no", ""),
            "preview_path": s.get("preview_path", ""),
        })
    return {"count": len(results), "samples": results}


def _exec_edit_sample(args: dict, ctx: ToolContext) -> dict:
    """編輯樣品的標題、布號或備註。"""
    from ..services import sample_repo

    query = args.get("query")
    if not query:
        return {"error": "Missing query parameter (sample_no or title)"}

    title = args.get("title")
    fabric_no = args.get("fabric_no")
    remark = args.get("remark")

    try:
        res = sample_repo.update_sample_by_ai(
            query=query,
            title=title,
            fabric_no=fabric_no,
            remark=remark
        )
        if res.get("status") == "ambiguous":
            options = [f"編號 {m['sample_no']} ({m['title']})" for m in res["matches"]]
            return {
                "status": "ambiguous",
                "message": f"找到了多個符合 '{query}' 的樣品，請確認是哪一個？",
                "options": options
            }
        
        return {
            "status": "updated",
            "title": res["title"],
            "message": f"樣品 '{res['title']}' 已更新。"
        }
    except Exception as e:
        return {"error": str(e)}


def _exec_batch_record_color_corrections(args: dict, ctx: ToolContext) -> dict:
    """批量記錄換色數據。"""
    from ..services import sample_repo
    
    sample_query = args.get("sample_query")
    corrections = args.get("corrections", [])
    
    if not sample_query or not corrections:
        return {"error": "Missing sample_query or corrections"}
        
    try:
        # 先找到樣品
        res = sample_repo.update_sample_by_ai(query=sample_query)
        if res.get("status") == "ambiguous":
             return {
                "status": "ambiguous",
                "message": f"找到了多個符合 '{sample_query}' 的樣品，請先確認是哪一個？",
                "options": [f"{m['sample_no']} ({m['title']})" for m in res["matches"]]
            }
        
        sample_id = res["id"]
        count = 0
        for c in corrections:
            sample_repo.add_full_color_correction(
                sample_id=sample_id,
                rgb_r=c.get("rgb_r"),
                rgb_g=c.get("rgb_g"),
                rgb_b=c.get("rgb_b"),
                target_mode=c.get("target_mode"),
                target_l=c.get("target_l"),
                target_a=c.get("target_a"),
                target_b=c.get("target_b"),
                target_note=c.get("target_note")
            )
            count += 1
            
        return {
            "status": "success",
            "message": f"已成功為樣品 '{res['title']}' 記錄 {count} 筆顏色換色數據。"
        }
    except Exception as e:
        return {"error": str(e)}


def _exec_extract_color_correction_data(args: dict, ctx: ToolContext) -> dict:
    """使用視覺模型從圖片中提取顏色表數據。"""
    if not ctx.image_bytes:
        return {"error": "沒有收到圖片，無法提取數據。"}
    
    hint = args.get("hint", "請提取圖片中的顏色換色表格，包含輸入層(Input/RGB)與輸出層(Output/LAB/YMCK)的對應關係。")
    
    prompt = f"""
{hint}
請分析圖片中的表格，並將每一列轉換為 JSON 格式。
輸出格式必須是純 JSON 列表，每一項包含：
- rgb_r, rgb_g, rgb_b (數字)
- target_mode (字串，如 'LAB', 'YMCKBHFm')
- target_l, target_a, target_b (如果是 LAB 模式時的數字)
- target_note (如果是非 LAB 模式時的數值字串或備註)

只要回傳 JSON 列表即可。
"""
    try:
        from . import ai_service
        # 使用 vl_model 進行識別
        raw = ai_service.call_ollama(
            prompt=prompt,
            images=[ctx.image_bytes],
            temperature=0.0,
            max_tokens=2048
        )
        
        # 解析 JSON
        from .ai_service import _strip_think_tags
        import json
        import re
        
        cleaned = _strip_think_tags(raw)
        # 尋找 [ ... ]
        start = cleaned.find("[")
        end = cleaned.rfind("]")
        if start != -1 and end != -1:
            data = json.loads(cleaned[start:end+1])
            return {
                "status": "success",
                "data": data,
                "message": f"已成功從圖片中提取 {len(data)} 筆顏色數據。請確認後調用 batch_record_color_corrections 進行儲存。"
            }
        else:
            return {"error": "無法從模型回應中解析出 JSON 列表。", "raw_response": cleaned}
            
    except Exception as e:
        logger.error(f"[Tools] extract_color_correction_data 失敗: {e}", exc_info=True)
        return {"error": str(e)}


def _exec_delete_fabric(args: dict, ctx: ToolContext) -> dict:
    """刪除布料代碼。"""
    from ..services import fabric_repo
    fabric_code = args.get("fabric_code")
    if not fabric_code:
        return {"error": "Missing fabric_code parameter"}
        
    try:
        fabric_repo.delete_fabric_cascade(fabric_code)
        return {
            "status": "deleted",
            "fabric_code": fabric_code,
            "message": f"布號 {fabric_code} 及其所有的缸號與捲料紀錄已成功徹底刪除。"
        }
    except Exception as e:
        return {"error": str(e)}
