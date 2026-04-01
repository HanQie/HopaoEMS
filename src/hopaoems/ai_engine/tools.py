"""
tools.py
========
通用工具箱：Universal Tools for Schema-Aware Agent.

包含以下四大核心工具：
1. universal_data_entry: 動態讀取 Schema 執行 upsert / delete
2. universal_query_engine: 自然語言查詢 (Text-to-SQL)
3. multimodal_processor: 視覺內容提取 / 以圖搜圖
4. deduplicate_color_corrections: 樣品顏色重複資料去重
5. ask_user: 關鍵資訊缺失回問
"""

from __future__ import annotations

import json
import logging
import sqlite3
import re
from typing import Any, Callable

logger = logging.getLogger(__name__)


def _normalize_field_token(value: Any) -> str:
    raw = str(value or "").strip().lower()
    if not raw:
        return ""
    raw = raw.replace("*", "")
    raw = re.sub(r"[:：]+$", "", raw)
    raw = re.sub(r"[\s\-]+", "_", raw)
    raw = re.sub(r"_+", "_", raw)
    return raw.strip("_")


def _build_manifest_alias_map(field_manifest: dict[str, Any] | None) -> dict[str, str]:
    manifest = field_manifest or {}
    alias_map: dict[str, str] = {}

    def register(field: dict[str, Any]) -> None:
        if not isinstance(field, dict):
            return
        canonical = str(field.get("name") or "").strip()
        if not canonical:
            return

        candidates = {
            canonical,
            field.get("label"),
            field.get("db_field"),
        }
        for alias in field.get("aliases") or []:
            candidates.add(alias)

        for candidate in candidates:
            token = _normalize_field_token(candidate)
            if token:
                alias_map[token] = canonical

    for field in manifest.get("fields") or []:
        register(field)
    for group in manifest.get("groups") or []:
        if not isinstance(group, dict):
            continue
        for field in group.get("row_fields") or []:
            register(field)

    return alias_map


def _normalize_entity_fields(
    entity_type: str,
    data: dict[str, Any],
    field_manifest: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    將常見業務欄位別名轉成實際資料庫欄位名稱。
    目的是讓通用寫入工具能吃下 UI / Agent 常用語彙。
    """
    if not isinstance(data, dict):
        return {}

    normalized = dict(data)
    manifest_aliases = _build_manifest_alias_map(field_manifest)
    if manifest_aliases:
        remapped: dict[str, Any] = {}
        for key, value in normalized.items():
            canonical = manifest_aliases.get(_normalize_field_token(key), key)
            if canonical not in remapped:
                remapped[canonical] = value
            elif remapped[canonical] in (None, "", []):
                remapped[canonical] = value
        normalized = remapped
    alias_map: dict[str, dict[str, str]] = {
        "fabrics": {
            "material_type": "material",
            "gram_per_yard": "yard_weight_gyd",
            "weight_gyd": "yard_weight_gyd",
            "width": "width_mm",
        },
    }

    entity_aliases = alias_map.get(entity_type, {})
    for source_key, target_key in entity_aliases.items():
        if source_key in normalized and target_key not in normalized:
            normalized[target_key] = normalized[source_key]
        if source_key in normalized and source_key != target_key:
            normalized.pop(source_key, None)

    return normalized


def _merge_upsert_identity(entity_type: str, args: dict[str, Any], data_dict: dict[str, Any], ctx: ToolContext) -> dict[str, Any]:
    """
    將工具層常見的識別資訊合併回 data_dict。
    支援：
    1. Agent 把 id 放在頂層 args，而不是 data_dict。
    2. 當前頁面已鎖定某筆 sample，但 agent 只提供局部欄位更新。
    """
    merged = dict(data_dict or {})

    top_level_id = args.get("id")
    if top_level_id is not None and "id" not in merged:
        try:
            merged["id"] = int(top_level_id)
        except Exception:
            merged["id"] = top_level_id

    current_entity = ctx.current_entity or {}
    current_type = str(current_entity.get("type") or "").strip().lower()
    current_id = current_entity.get("id")
    type_matches_current = (
        (entity_type == "samples" and current_type == "sample")
        or (entity_type == current_type)
        or (entity_type.rstrip("s") == current_type.rstrip("s") and current_type)
    )
    if current_id is not None and "id" not in merged and type_matches_current:
        merged["id"] = current_id

    return merged

# ---------------------------------------------------------------------------
# ToolContext 定義
# ---------------------------------------------------------------------------
class ToolContext:
    """Tool 執行時的上下文環境。"""

    def __init__(
        self,
        db_path: str,
        lang: str,
        username: str,
        conversation_id: str,
        processor,
        image_bytes: bytes | None = None,
        current_entity: dict | None = None,
        field_manifest: dict | None = None,
    ):
        self.db_path = db_path
        self.lang = lang
        self.username = username
        self.conversation_id = conversation_id
        self.processor = processor
        self.image_bytes = image_bytes
        self.current_entity = current_entity or {}
        self.field_manifest = field_manifest or {}

    def get_image(self, image_id: str | None = None) -> bytes | None:
        """
        取得圖片二進位資料。
        若無上傳，則嘗試從暫存目錄中取得最新一張圖片。
        """
        import os
        from flask import current_app

        temp_dir = os.path.join(
            current_app.root_path,
            "static",
            "uploads",
            "temp_ai",
            self.username,
            self.conversation_id,
        )

        # 1. 指定 ID 讀取
        if image_id:
            safe_id = os.path.basename(image_id)
            file_path = os.path.join(temp_dir, safe_id)
            if os.path.isfile(file_path):
                try:
                    with open(file_path, "rb") as f:
                        return f.read()
                except Exception as e:
                    current_app.logger.warning(f"無法讀取微庫圖片 {image_id}: {e}")
            return None

        # 2. 本次有上傳
        if self.image_bytes:
            return self.image_bytes

        # 3. Fallback 到最新的圖片
        if os.path.isdir(temp_dir):
            try:
                files = [f for f in os.listdir(temp_dir) if f.lower().endswith(('.jpg', '.jpeg', '.png'))]
                if files:
                    files.sort()
                    latest_file = files[-1]
                    file_path = os.path.join(temp_dir, latest_file)
                    with open(file_path, "rb") as f:
                        return f.read()
            except Exception as e:
                current_app.logger.warning(f"無法讀取最新的微庫圖片: {e}")

        return None


# ---------------------------------------------------------------------------
# Tool Schemas
# ---------------------------------------------------------------------------
UNIVERSAL_DATA_ENTRY_SCHEMA = {
    "type": "function",
    "function": {
        "name": "universal_data_entry",
        "description": "實體寫入工具。action=upsert 時執行新增或更新；action=delete 時依條件刪除。這是唯一允許改變資料庫狀態的工具。",
        "parameters": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "description": "資料寫入動作。僅允許 upsert 或 delete。"
                },
                "entity_type": {
                    "type": "string",
                    "description": "資料表名稱，例如 'fabrics', 'samples', 'production_logs' 等。"
                },
                "id": {
                    "type": ["integer", "string"],
                    "description": "可選。更新既有資料時的目標 id。若當前頁面已鎖定某筆記錄，也建議帶入這個 id。"
                },
                "data_dict": {
                    "type": "object",
                    "description": "要寫入或更新的資料欄位與值，請務必使用 Schema 中實際存在的欄位名稱，例如 {\"fabric_code\": \"95278\"}"
                },
                "conditions": {
                    "type": "object",
                    "description": "刪除條件（AND 邏輯），例如 {\"id\": [1,2,3]} 或 {\"fabric_code\": \"95278\"}。僅 action=delete 時使用。"
                }
            },
            "required": ["action", "entity_type"],
        },
    },
}

UNIVERSAL_QUERY_ENGINE_SCHEMA = {
    "type": "function",
    "function": {
        "name": "universal_query_engine",
        "description": "自然語言查詢工具。用於查詢資料庫內容。",
        "parameters": {
            "type": "object",
            "properties": {
                "natural_query": {
                    "type": "string",
                    "description": "用戶的自然語言查詢，例如 '列出今天建立的布號'"
                }
            },
            "required": ["natural_query"],
        },
    },
}

MULTIMODAL_PROCESSOR_SCHEMA = {
    "type": "function",
    "function": {
        "name": "multimodal_processor",
        "description": "多模態感官工具。action=extract 時做 OCR/結構化擷取；action=search 時做 CLIP/VSS 以圖搜圖。",
        "parameters": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "description": "多模態動作。僅允許 extract 或 search。"
                },
                "target_schema": {
                    "type": "string",
                    "description": "希望提取的 JSON Schema 或要求描述，例如 '{\"product_name\": \"str\", \"qty\": \"int\"}'。僅 action=extract 時使用。"
                },
                "image_id": {
                    "type": "string",
                    "description": "指定的圖片檔名（非必填）。如果不填，將自動使用最新上傳的圖片。"
                },
                "top_k": {
                    "type": "integer",
                    "description": "以圖搜圖回傳最多幾筆結果。僅 action=search 時使用，預設 5。"
                }
            },
            "required": ["action"],
        },
    },
}

DEDUPLICATE_COLOR_CORRECTIONS_SCHEMA = {
    "type": "function",
    "function": {
        "name": "deduplicate_color_corrections",
        "description": (
            "刪除樣品中重複的顏色校正列。"
            "當用戶提到『刪除重複原顏色』『同色只留一筆』『重複顏色去掉』時，"
            "必須優先使用此工具，不可直接對 sample_color_map 做泛用刪除。"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "sample_query": {
                    "type": "string",
                    "description": "樣品編號、標題，或目前頁面 sample 的識別資訊。當前頁面已是 sample 時可省略。"
                },
                "dedupe_by": {
                    "type": "string",
                    "enum": ["rgb", "rgb+target"],
                    "description": "依 RGB 或 RGB+目標值判定重複。預設 rgb。"
                },
                "keep": {
                    "type": "string",
                    "enum": ["first", "last"],
                    "description": "保留第一筆或最後一筆。預設 first。"
                }
            },
        },
    },
}

ASK_USER_SCHEMA = {
    "type": "function",
    "function": {
        "name": "ask_user",
        "description": "向用戶詢問更多資訊或確認操作。若是因為缺少必填欄位或需要用戶親自確認，才可使用此工具。",
        "parameters": {
            "type": "object",
            "properties": {
                "question_zh": {"type": "string", "description": "要詢問用戶的繁體中文問題"},
                "question_vi": {"type": "string", "description": "要詢問用戶的越南文問題"},
            },
            "required": ["question_zh", "question_vi"],
        },
    },
}

TOOL_SCHEMAS = [
    UNIVERSAL_DATA_ENTRY_SCHEMA,
    UNIVERSAL_QUERY_ENGINE_SCHEMA,
    MULTIMODAL_PROCESSOR_SCHEMA,
    DEDUPLICATE_COLOR_CORRECTIONS_SCHEMA,
    ASK_USER_SCHEMA,
]

# ---------------------------------------------------------------------------
# Tool Executors
# ---------------------------------------------------------------------------
def exec_universal_data_entry(args: dict[str, Any], ctx: ToolContext) -> dict[str, Any]:
    """唯一寫入入口：處理 upsert / delete。"""
    action = str(args.get("action") or "upsert").strip().lower()
    if action == "delete":
        return _exec_universal_delete(args, ctx)
    if action != "upsert":
        return {"error": "action 僅允許 upsert 或 delete"}

    entity_type = args.get("entity_type")
    data_dict = _normalize_entity_fields(
        str(entity_type or ""),
        args.get("data_dict", {}),
        ctx.field_manifest,
    )
    data_dict = _merge_upsert_identity(str(entity_type or ""), args, data_dict, ctx)
    
    if not entity_type or not data_dict:
        return {"error": "缺少 entity_type 或 data_dict"}
    
    # 防止 SQL Injection 表名
    if not entity_type.isidentifier():
        return {"error": f"不合法的資料表名稱: {entity_type}"}

    try:
        conn = sqlite3.connect(ctx.db_path)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()

        # 1. 取得 Table Schema
        cur.execute(f"PRAGMA table_info({entity_type})")
        columns_info = cur.fetchall()
        if not columns_info:
            conn.close()
            return {"error": f"找不到資料表 {entity_type}"}

        primary_keys = []
        required_cols = []
        col_names = []

        for col in columns_info:
            c_name = col["name"]
            c_notnull = col["notnull"]
            c_dflt = col["dflt_value"]
            c_pk = col["pk"]

            col_names.append(c_name)
            
            if c_pk > 0:
                primary_keys.append(c_name)
            
            if c_notnull and c_dflt is None and c_pk == 0 and c_name not in ["id", "created_at", "updated_at"]:
                required_cols.append(c_name)

        # 過濾出 DB 中確實存在的欄位
        filtered_data = {k: v for k, v in data_dict.items() if k in col_names}
        ignored_fields = [k for k in data_dict.keys() if k not in col_names]
        if not filtered_data:
            conn.close()
            return {"error": "沒有對應到任何有效的資料庫欄位"}

        # 定義業務邏輯主鍵 (Logical Keys) 以彌補 SQLite Scheme 無 UNIQUE 的問題
        LOGICAL_KEYS = {
            "fabrics": "fabric_code",
            "samples": "sample_no",
            "cylinders": "batch_no",
            "rolls": "roll_no",
        }
        
        logical_key = LOGICAL_KEYS.get(entity_type)
        exist_id = None
        
        # 檢查是否已存在 (以 SQLite PK 或 Logical Key)
        if primary_keys[0] in filtered_data:
            pk_val = filtered_data[primary_keys[0]]
            row = cur.execute(f"SELECT id FROM {entity_type} WHERE {primary_keys[0]}=?", (pk_val,)).fetchone()
            if row: exist_id = row["id"]
        elif logical_key and logical_key in filtered_data:
            lk_val = filtered_data[logical_key]
            row = cur.execute(f"SELECT id FROM {entity_type} WHERE {logical_key}=?", (lk_val,)).fetchone()
            if row: exist_id = row["id"]

        if exist_id:
            # UPDATE (部分建檔: 不檢查 NOT NULL，因為只更新提供的欄位)
            immutable_lookup_cols = set(primary_keys)
            if logical_key and logical_key in filtered_data:
                immutable_lookup_cols.add(logical_key)

            update_cols = [c for c in filtered_data.keys() if c not in immutable_lookup_cols]
            if not update_cols:
                conn.close()
                if ignored_fields:
                    return {
                        "error": f"沒有可更新的有效欄位。已忽略欄位: {', '.join(ignored_fields)}",
                        "status": "needs_clarification",
                    }
                return {
                    "error": "資料已存在，但本次沒有提供可更新欄位。",
                    "status": "needs_clarification",
                }
            
            set_clause = ", ".join([f"{c}=?" for c in update_cols])
            vals = [filtered_data[c] for c in update_cols]
            vals.append(exist_id)
            cur.execute(f"UPDATE {entity_type} SET {set_clause} WHERE id=?", vals)
            conn.commit()
            updated_row = cur.execute(f"SELECT * FROM {entity_type} WHERE id=?", (exist_id,)).fetchone()
            conn.close()
            reply_lang = "成功更新資料" if ctx.lang == "zh" else "Cập nhật dữ liệu thành công"
            return {
                "status": "success",
                "message": f"{reply_lang} (Table: {entity_type}, ID: {exist_id})",
                "updated_fields": {c: filtered_data[c] for c in update_cols},
                "ignored_fields": ignored_fields,
                "record": dict(updated_row) if updated_row else None,
            }

        else:
            # INSERT (必須檢查 NOT NULL)
            missing_cols = [c for c in required_cols if c not in filtered_data]
            if missing_cols:
                conn.close()
                return {"error": f"缺少必填欄位: {', '.join(missing_cols)}"}

            cols = list(filtered_data.keys())
            vals = tuple(filtered_data.values())
            placeholders = ", ".join(["?"] * len(cols))
            
            cur.execute(f"INSERT INTO {entity_type} ({', '.join(cols)}) VALUES ({placeholders})", vals)
            last_id = cur.lastrowid
            conn.commit()
            inserted_row = cur.execute(f"SELECT * FROM {entity_type} WHERE id=?", (last_id,)).fetchone()
            conn.close()

            reply_lang = "成功新增資料" if ctx.lang == "zh" else "Thêm dữ liệu thành công"
            return {
                "status": "success",
                "message": f"{reply_lang} (Table: {entity_type}, ID: {last_id})",
                "updated_fields": dict(filtered_data),
                "ignored_fields": ignored_fields,
                "record": dict(inserted_row) if inserted_row else None,
            }

    except sqlite3.IntegrityError as e:
        return {"error": f"資料庫完整性錯誤 (可能資料重複或違反約束): {str(e)}"}
    except Exception as e:
        logger.error(f"[UniversalDataEntry] 寫入失敗: {e}", exc_info=True)
        return {"error": str(e)}

def _exec_universal_delete(args: dict[str, Any], ctx: ToolContext) -> dict[str, Any]:
    """動態刪除資料庫紀錄。"""
    entity_type = args.get("entity_type")
    conditions = args.get("conditions", {})
    if not entity_type or not conditions:
        return {"error": "缺少 entity_type 或 conditions"}
    
    if not entity_type.isidentifier():
        return {"error": f"不合法的資料表名稱: {entity_type}"}

    # 安全防線：sample_color_map 的刪除非常容易誤刪整張樣品色票。
    # 去重必須走專用 deduplicate_color_corrections；泛用刪除只允許指定明確 id。
    if entity_type == "sample_color_map":
        has_explicit_id = isinstance(conditions, dict) and "id" in conditions
        if not has_explicit_id:
            return {
                "error": (
                    "禁止對 sample_color_map 以 sample_id 或模糊條件做泛用刪除。"
                    "若需求是刪除重複顏色，請改用 deduplicate_color_corrections；"
                    "若要刪單筆，必須提供明確 id。"
                ),
                "status": "needs_clarification",
            }

    try:
        conn = sqlite3.connect(ctx.db_path)
        cur = conn.cursor()
        
        cur.execute(f"PRAGMA table_info({entity_type})")
        columns_info = cur.fetchall()
        if not columns_info:
            conn.close()
            return {"error": f"找不到資料表 {entity_type}"}
            
        valid_cols = [c[1] for c in columns_info]
        filtered_conditions = {k: v for k, v in conditions.items() if k in valid_cols}
        
        if not filtered_conditions:
            conn.close()
            return {"error": "提供的條件沒有對應到任何有效的資料庫欄位"}
            
        where_clauses = []
        vals = []
        for k, v in filtered_conditions.items():
            if isinstance(v, list):
                if not v: continue
                placeholders = ", ".join(["?"] * len(v))
                where_clauses.append(f"{k} IN ({placeholders})")
                vals.extend(v)
            else:
                where_clauses.append(f"{k}=?")
                vals.append(v)
                
        if not where_clauses:
            conn.close()
            return {"error": "提供的條件為空 (可能是空的陣列)"}
            
        where_clause_str = " AND ".join(where_clauses)
        
        missing_vals = {}
        for k, v in filtered_conditions.items():
            check_vals = v if isinstance(v, list) else [v]
            if not check_vals: continue
            placeholders = ", ".join(["?"] * len(check_vals))
            cur.execute(f"SELECT DISTINCT {k} FROM {entity_type} WHERE {k} IN ({placeholders})", check_vals)
            found = [str(r[0]) for r in cur.fetchall()]
            missing = [item for item in check_vals if str(item) not in found]
            if missing:
                missing_vals[k] = missing

        if missing_vals:
            suggestions = {}
            for k, missing_list in missing_vals.items():
                col_suggs = []
                for item in missing_list:
                    cur.execute(f"SELECT DISTINCT {k} FROM {entity_type} WHERE {k} LIKE ? LIMIT 5", (f"%{item}%",))
                    for r in cur.fetchall():
                        if r[0] not in col_suggs:
                            col_suggs.append(r[0])
                if col_suggs:
                    suggestions[k] = col_suggs

            conn.close()
            err_msg = [f"無法執行刪除，因為有部分條件無法精確匹配: {missing_vals}"]
            if suggestions:
                err_msg.append(f"👉 發現可能相似的紀錄: {suggestions}")
                err_msg.append("請向用戶詢問是否是指這些紀錄，如果是，請用戶確認後再重新以正確名稱調用本工具。")
            else:
                err_msg.append("而且資料庫中也找不到相似的紀錄，請向用戶回報。")
            return {"error": "\n".join(err_msg), "status": "needs_clarification"}

        cur.execute(f"SELECT COUNT(*) FROM {entity_type} WHERE {where_clause_str}", vals)
        count = cur.fetchone()[0]
        if count == 0:
            conn.close()
            return {"error": "找不到符合所有給定條件的紀錄", "status": "needs_clarification"}
            
        cur.execute(f"DELETE FROM {entity_type} WHERE {where_clause_str}", vals)
        conn.commit()
        conn.close()
        
        msg = f"成功刪除 {count} 筆記錄 (Table: {entity_type})" if ctx.lang == "zh" else f"Đã xóa thành công {count} bản ghi (Table: {entity_type})"
        return {"status": "success", "message": msg, "deleted_count": count}
        
    except sqlite3.IntegrityError as e:
        return {"error": f"資料刪除失敗，可能有外鍵依賴 (如有其他資料綁定此紀錄則無法刪除): {str(e)}"}
    except Exception as e:
        logger.error(f"[UniversalDeleteEntry] 刪除失敗: {e}", exc_info=True)
        return {"error": str(e)}

def exec_universal_query_engine(args: dict[str, Any], ctx: ToolContext) -> dict[str, Any]:
    natural_query = args.get("natural_query", "")
    if not natural_query:
        return {"error": "請提供查詢語句"}
    
    from .sql_agent import ask
    try:
        ans = ask(
            question=natural_query,
            lang=ctx.lang,
            db_path=ctx.db_path,
            processor=ctx.processor
        )
        return {"reply": ans}
    except Exception as e:
        return {"error": f"查詢執行失敗: {str(e)}"}

def exec_multimodal_processor(args: dict[str, Any], ctx: ToolContext) -> dict[str, Any]:
    action = str(args.get("action") or "extract").strip().lower()
    target_schema = args.get("target_schema", "")
    image_id = args.get("image_id")
    img_bytes = ctx.get_image(image_id)
    if not img_bytes:
        return {"error": "未找到相關圖片"}

    if action == "extract":
        prompt = f"請識別這張圖片，並依照以下 Schema 規則或要求提取資料，請只回傳符合結構的 JSON，不要有任何 Markdown 或額外文字。\nSchema/要求：\n{target_schema}"
        from .ai_service import call_ollama, _extract_json_object, extract_text_from_image_local
        try:
            raw = call_ollama(
                prompt=prompt,
                images=[img_bytes],
                model="qwen3-vl:4b",
                temperature=0.0,
                max_tokens=1024
            )

            extracted = _extract_json_object(raw)
            if not extracted:
                local_text = extract_text_from_image_local(img_bytes)
                return {
                    "action": "extract",
                    "extracted_text": raw or local_text,
                    "fallback": "local_ocr" if local_text and not raw else None,
                }
            return {"action": "extract", "extracted_data": extracted}
        except Exception as e:
            logger.error(f"[MultimodalProcessor] extract 失敗: {e}", exc_info=True)
            local_text = extract_text_from_image_local(img_bytes)
            if local_text:
                return {
                    "action": "extract",
                    "extracted_text": local_text,
                    "warning": f"vision_model_failed: {e}",
                    "fallback": "local_ocr",
                }
            return {
                "action": "extract",
                "extracted_text": "",
                "warning": f"vision_model_failed: {e}",
            }

    if action == "search":
        from .ai_service import compute_image_embedding, search_similar_images
        try:
            top_k = int(args.get("top_k") or 5)
            query_embedding = compute_image_embedding(img_bytes)
            matches = search_similar_images(
                query_embedding=query_embedding,
                db_path=ctx.db_path,
                top_k=max(1, min(top_k, 20)),
            )
            return {
                "action": "search",
                "matches": matches,
                "count": len(matches),
            }
        except Exception as e:
            logger.error(f"[MultimodalProcessor] search 失敗: {e}", exc_info=True)
            return {"error": str(e)}

    return {"error": "multimodal_processor.action 僅允許 extract 或 search"}


def exec_deduplicate_color_corrections(args: dict[str, Any], ctx: ToolContext) -> dict[str, Any]:
    from .tooling.color_tools import exec_deduplicate_color_corrections as _dedupe_executor

    return _dedupe_executor(args, ctx)

def exec_ask_user(args: dict[str, Any], ctx: ToolContext) -> dict[str, Any]:
    # 直接回傳，Agent 迴圈會捕捉這個然後設定狀態為 need_info
    return args

TOOL_EXECUTORS: dict[str, Callable[[dict[str, Any], ToolContext], dict[str, Any]]] = {
    "universal_data_entry": exec_universal_data_entry,
    "universal_query_engine": exec_universal_query_engine,
    "multimodal_processor": exec_multimodal_processor,
    "deduplicate_color_corrections": exec_deduplicate_color_corrections,
    "ask_user": exec_ask_user,
    # backward compatibility
    "universal_delete_entry": _exec_universal_delete,
    "multimodal_extractor": exec_multimodal_processor,
}

def execute_tool(name: str, arguments: dict[str, Any], ctx: ToolContext) -> dict[str, Any]:
    logger.info(f"[Tools] 執行 Tool: {name}，參數: {json.dumps(arguments, ensure_ascii=False)[:200]}")
    executor = TOOL_EXECUTORS.get(name)
    if executor is None:
        return {"error": f"未知的 Tool: {name}"}

    try:
        return executor(arguments, ctx)
    except Exception as e:
        logger.error(f"[Tools] Tool '{name}' 執行失敗: {e}", exc_info=True)
        return {"error": str(e)}
