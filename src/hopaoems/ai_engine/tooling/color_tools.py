from __future__ import annotations

from typing import Any

from .common import ToolContext


EXTRACT_COLOR_CORRECTION_DATA_SCHEMA = {
    "type": "function",
    "function": {
        "name": "extract_color_correction_data",
        "description": (
            "從用戶上傳的圖片中提取顏色校正表格數據。"
            "當用戶說『看圖裡的對色表』、『就在截圖裡』、『和圖一樣』，"
            "或 context 中沒有足夠文字表格時使用。"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "image_id": {
                    "type": "string",
                    "description": "微庫中的圖片ID。若要讀取之前的圖片請提供此值。若為當前上傳的新圖則可省略。",
                },
                "hint": {
                    "type": "string",
                    "description": "提供給視覺模型的額外提示，例如提取 RGB 與 LAB 對應表。",
                }
            },
        },
    },
}

DEDUPLICATE_COLOR_CORRECTIONS_SCHEMA = {
    "type": "function",
    "function": {
        "name": "deduplicate_color_corrections",
        "description": (
            "刪除樣品中重複的顏色校正列。"
            "適合處理『刪除重複的』『重複顏色去掉』『同一個 RGB 留一筆』這類需求。"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "sample_query": {
                    "type": "string",
                    "description": "樣品編號或標題。若當前頁面已是 sample，可省略。",
                },
                "dedupe_by": {
                    "type": "string",
                    "enum": ["rgb", "rgb+target"],
                    "description": "依 RGB 或 RGB+目標值判定重複。預設 rgb。",
                },
                "keep": {
                    "type": "string",
                    "enum": ["first", "last"],
                    "description": "保留第一筆或最後一筆。預設 first。",
                },
            },
        },
    },
}

BATCH_RECORD_COLOR_CORRECTIONS_SCHEMA = {
    "type": "function",
    "function": {
        "name": "batch_record_color_corrections",
        "description": (
            "批量寫入樣品顏色換色/校正數據。"
            "標準額色登記流程：find_sample_candidates → extract_color_correction_data → 此工具。"
            "帶圖片時必須先從圖片提取數據再呈入此工具。"
            "LAB 輸出必須拆成三個獨立欄位 (target_l/target_a/target_b)，絕不可將整列 LAB 字串塩入 note。"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "sample_query": {"type": "string", "description": "樣品編號或標題。"},
                "corrections": {
                    "type": "array",
                    "description": "顏色校正列表。",
                    "items": {
                        "type": "object",
                        "properties": {
                            "rgb_r": {"type": "integer", "description": "輸入層 R。"},
                            "rgb_g": {"type": "integer", "description": "輸入層 G。"},
                            "rgb_b": {"type": "integer", "description": "輸入層 B。"},
                            "target_mode": {"type": "string", "description": "目標模式，例如 LAB 或 YMCKBHFm。"},
                            "target_l": {"type": "number", "description": "LAB 的 L 分量（如 62.71）。必須独立填入，不得與 A/B 共用一個欄位。"},
                            "target_a": {"type": "number", "description": "LAB 的 A 分量（如 -4.58）。必須独立填入。"},
                            "target_b": {"type": "number", "description": "LAB 的 B 分量（如 -25.46）。必須独立填入。"},
                            "target_note": {"type": "string", "description": "非 LAB 模式下的值或備註。"},
                        },
                        "required": ["rgb_r", "rgb_g", "rgb_b", "target_mode"],
                    },
                },
            },
            "required": ["sample_query", "corrections"],
        },
    },
}


def exec_extract_color_correction_data(args: dict[str, Any], ctx: ToolContext) -> dict[str, Any]:
    image_bytes = ctx.get_image(args.get("image_id"))
    if not image_bytes:
        return {"error": "沒有收到圖片或指定的微庫圖片不存在，無法提取數據。"}

    try:
        from .. import ai_service

        hint = args.get(
            "hint",
            "請提取圖片中的顏色換色表格，包含輸入層(Input/RGB)與輸出層(Output/LAB/YMCK)的對應關係。"
            "極度重要：如果輸出是 LAB，無論圖片中是否寫在一起，都 **必須** 拆解成三個獨立的數值：target_l、target_a、target_b。"
            "絕對不要把整串 LAB 文字塞進 note 或合併填寫。",
        )
        data = ai_service.extract_color_correction_rows(image_bytes, hint=hint)
        if data is None:
            return {"error": "無法從模型回應中解析出 JSON 列表。"}
        return {
            "status": "success",
            "data": data,
            "message": f"已成功從圖片中提取 {len(data)} 筆顏色數據。請確認後調用 batch_record_color_corrections 進行儲存。",
        }
    except Exception as e:
        return {"error": str(e)}


def exec_deduplicate_color_corrections(args: dict[str, Any], ctx: ToolContext) -> dict[str, Any]:
    from ...services import sample_repo

    sample_query = (args.get("sample_query") or "").strip()
    dedupe_by = args.get("dedupe_by") or "rgb"
    keep = args.get("keep") or "first"

    if not sample_query and ctx.current_entity.get("type") == "sample":
        sample_query = str(ctx.current_entity.get("sample_no") or ctx.current_entity.get("title") or ctx.current_entity.get("id") or "").strip()

    if not sample_query:
        return {
            "status": "need_info",
            "needs_user_clarification": True,
            "message": "請指定要整理的樣品。",
        }

    result = sample_repo.resolve_sample_for_ai(sample_query)
    if result.get("status") == "ambiguous":
        return {
            "status": "ambiguous",
            "needs_user_clarification": True,
            "message": f"找到了多個符合 '{sample_query}' 的樣品，請先確認是哪一個？",
            "options": [
                f"{item['sample_no']} ({item['title']}) score={item.get('score', 0):.2f}"
                for item in result["matches"]
            ],
            "matches": result["matches"],
        }

    summary = sample_repo.deduplicate_color_corrections(
        sample_id=result["id"],
        dedupe_by=dedupe_by,
        keep=keep,
    )
    return {
        "status": "success",
        "sample_id": result["id"],
        "sample_no": result.get("sample_no"),
        "title": result["title"],
        "removed_count": summary["removed_count"],
        "kept_count": summary["kept_count"],
        "groups": summary["groups"],
        "message": f"已為樣品 '{result['title']}' 刪除 {summary['removed_count']} 筆重複顏色資料。",
    }


def exec_batch_record_color_corrections(args: dict[str, Any], ctx: ToolContext) -> dict[str, Any]:
    from ...services import sample_repo

    sample_query = args.get("sample_query") or ""
    corrections = args.get("corrections", [])
    if not sample_query and ctx.current_entity.get("type") == "sample":
        sample_query = str(ctx.current_entity.get("sample_no") or ctx.current_entity.get("title") or ctx.current_entity.get("id") or "").strip()
    if not sample_query or not corrections:
        return {"error": "Missing sample_query or corrections"}

    try:
        result = sample_repo.update_sample_by_ai(query=sample_query)
        if result.get("status") == "ambiguous":
            return {
                "status": "ambiguous",
                "needs_user_clarification": True,
                "message": f"找到了多個符合 '{sample_query}' 的樣品，請先確認是哪一個？",
                "options": [
                    f"{item['sample_no']} ({item['title']}) score={item.get('score', 0):.2f}"
                    for item in result["matches"]
                ],
                "matches": result["matches"],
            }

        sample_id = result["id"]
        count = 0
        
        # 預先檢核：確保所有 row 都具備有效的目標值 (LAB 或 Note)，並矯正空白模式
        for row in corrections:
            mode = str(row.get("target_mode") or "").strip().upper()
            
            # 若 mode 為空，但 target_l 有值，將 mode 自動判定為 LAB
            if not mode and row.get("target_l") is not None:
                mode = "LAB"
                row["target_mode"] = "LAB"
                
            # 若為 LAB 模式，必須三格皆有值
            if "LAB" in mode:
                if row.get("target_l") is None or row.get("target_a") is None or row.get("target_b") is None:
                    return {
                        "status": "need_info",
                        "needs_user_clarification": True,
                        "error": "部分 LAB 目標值為空",
                        "message": "圖片提取的 LAB 值不完整，或未正確給出 target_l, target_a, target_b。請要求用戶提供這些 LAB 數值後再寫入。",
                    }
            else:
                # 非 LAB 模式（如 YMCK 或空白），若無任何 target 資訊則整行無效
                # 非 LAB 模式（如 YMCK 或空白），若無任何 target 資訊則整行無效
                target_note = str(row.get("target_note") or "").strip().lower()
                if not mode and (not target_note or target_note in ("-", "none", "null", "n/a", "無", "empty")):
                    return {
                        "status": "need_info",
                        "needs_user_clarification": True,
                        "error": "缺乏目標顏色資料",
                        "message": "圖片部分行有 RGB，但未成功提取到對應的目標顏色(LAB/YMCK)。請確認圖片清晰度，或手動提供目標數值。",
                    }
                    
        # 檢核通過後，再統一寫入資料庫
        for row in corrections:
            sample_repo.add_full_color_correction(
                sample_id=sample_id,
                rgb_r=row.get("rgb_r"),
                rgb_g=row.get("rgb_g"),
                rgb_b=row.get("rgb_b"),
                target_mode=row.get("target_mode"),
                target_l=row.get("target_l"),
                target_a=row.get("target_a"),
                target_b=row.get("target_b"),
                target_note=row.get("target_note"),
            )
            count += 1
        return {
            "status": "success",
            "message": f"已成功為樣品 '{result['title']}' 記錄 {count} 筆顏色換色數據。",
        }
    except Exception as e:
        return {"error": str(e)}
