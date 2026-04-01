"""
api_ai.py
=========
AI 助理 API Blueprint

路由：
  POST /api/ai/chat          — 文字提問（查詢或登記）
  POST /api/ai/image-ingest  — 圖片入庫（OCR 識別 + 向量化存入 image_vectors）
  POST /api/ai/image-search  — 以圖搜圖（上傳圖片，回傳相似的已入庫圖片）

所有路由僅限 operator 角色。
"""

from __future__ import annotations

import os
import sqlite3
from flask import Blueprint, request, jsonify, current_app, g
from ..services.auth_service import operator_required

bp = Blueprint("api_ai", __name__, url_prefix="/api/ai")


def _get_processor():
    """取得 AI 處理器，若未就緒則回傳 None。"""
    from .. import ai_engine
    return ai_engine.get_processor()


def _get_db_path() -> str:
    return current_app.config["DATABASE"]


def _parse_current_entity(raw) -> dict:
    if not raw:
        return {}
    if isinstance(raw, dict):
        data = raw
    else:
        try:
            import json
            data = json.loads(raw)
        except Exception:
            return {}
    if not isinstance(data, dict):
        return {}
    entity_type = str(data.get("type") or "").strip()
    entity_id = data.get("id")
    try:
        entity_id = int(entity_id) if entity_id is not None and str(entity_id).strip() else None
    except Exception:
        entity_id = None
    return {
        "type": entity_type,
        "id": entity_id,
        "sample_no": str(data.get("sample_no") or "").strip(),
        "title": str(data.get("title") or "").strip(),
    }


def _parse_field_manifest(raw) -> dict:
    if not raw:
        return {}
    if isinstance(raw, dict):
        data = raw
    else:
        try:
            import json
            data = json.loads(raw)
        except Exception:
            return {}
    return data if isinstance(data, dict) else {}


def _sanitize_conversation_id(raw: str | None) -> str:
    import re

    value = str(raw or "").strip()
    if not value:
        return "default"
    cleaned = re.sub(r"[^a-zA-Z0-9_-]", "", value)
    return cleaned[:80] or "default"


def _build_temp_dir(username: str, conversation_id: str) -> str:
    return os.path.join(
        current_app.root_path,
        "static",
        "uploads",
        "temp_ai",
        username,
        conversation_id,
    )


def _text_requests_image_context(text: str) -> bool:
    """
    僅在用戶明確談到圖片/辨識/搜尋圖片時，才注入微庫提示。
    避免純文字任務被殘留圖片誤導到 OCR 流程。
    """
    lowered = (text or "").strip().lower()
    if not lowered:
        return False
    keywords = (
        "圖", "圖片", "照片", "影像", "樣品照", "這張", "那張", "上傳",
        "ocr", "辨識", "識別", "擷取", "搜圖", "以圖搜圖", "image", "photo", "picture",
    )
    return any(token in lowered for token in keywords)


# ---------------------------------------------------------------------------
# POST /api/ai/chat
# ---------------------------------------------------------------------------
@bp.route("/chat", methods=["POST"])
@operator_required
def chat():
    """
    接收文字輸入（可附帶圖片），判斷意圖並回應。

    支持兩種格式：
    1. JSON: { "text": "...", "lang": "zh" | "vi" }
    2. Multipart/form-data: text=...&lang=zh + image file

    Response JSON:
      {
        "status": "ok" | "need_info" | "ready" | "error",
        "reply":  "...",
        "intent": "query" | "stock_in" | "production_log" | "sample_search" | "unknown",
        "params": {...}   // 僅 status=ready 時存在
      }
    """
    processor = _get_processor()
    if processor is None:
        return jsonify({
            "status": "error",
            "reply": "AI 模型尚未就緒，請確認 Ollama 服務已啟動。",
            "intent": "unknown",
        }), 503

    # 從 JSON 或 form-data 中提取參數
    image_bytes = None
    history = []
    current_entity = {}
    field_manifest = {}
    username = g.user["username"] if g.user else "operator"
    conversation_id = "default"
    routing_text = ""
    
    # 用於儲存與讀取最後一次上傳的圖片（跨回合記憶）
    import os
    import time
    from flask import current_app
    
    # 建立該使用者的專屬微庫暫存目錄
    if request.content_type and "multipart" in request.content_type:
        text = (request.form.get("text") or "").strip()
        routing_text = text
        lang = request.form.get("lang", "zh")
        hist_raw = request.form.get("history")
        current_entity = _parse_current_entity(request.form.get("current_entity"))
        field_manifest = _parse_field_manifest(request.form.get("field_manifest"))
        conversation_id = _sanitize_conversation_id(request.form.get("conversation_id"))
        temp_dir = _build_temp_dir(username, conversation_id)
        os.makedirs(temp_dir, exist_ok=True)
        if hist_raw:
            try:
                import json
                history = json.loads(hist_raw)
            except:
                history = []
        # 提取上傳的圖片
        if "image" in request.files:
            img_file = request.files["image"]
            if img_file and img_file.filename:
                image_bytes = img_file.read()
                
                # 存入微庫暫存（按時間戳命名）
                new_img_filename = f"img_{int(time.time())}.jpg"
                new_img_path = os.path.join(temp_dir, new_img_filename)
                with open(new_img_path, "wb") as f:
                    f.write(image_bytes)
                    
                # 清理微庫，只保留最近 3 張
                try:
                    existing_files = [f for f in os.listdir(temp_dir) if f.lower().endswith(('.jpg', '.jpeg', '.png'))]
                    if len(existing_files) > 3:
                        existing_files.sort(key=lambda x: os.path.getmtime(os.path.join(temp_dir, x)))
                        for old_file in existing_files[:-3]:
                            os.remove(os.path.join(temp_dir, old_file))
                except Exception as e:
                    current_app.logger.warning(f"[AI Chat] 清理微庫失敗：{e}")

                # 按需做輕量圖片前處理，避免所有圖片都先跑一次 VL
                try:
                    from ..ai_engine import ai_service
                    image_context = ai_service.build_chat_image_context(text, image_bytes)
                    if image_context:
                        text = image_context + text
                        current_app.logger.info("[AI Chat] 圖片前處理成功，已併入文字 context")
                except Exception as image_err:
                    current_app.logger.warning(f"[AI Chat] 圖片前處理失敗（跳過）：{image_err}")
    else:
        data = request.get_json(silent=True) or {}
        text = str(data.get("text") or "").strip()
        routing_text = text
        lang = data.get("lang", "zh")
        history = data.get("history", [])
        current_entity = _parse_current_entity(data.get("current_entity"))
        field_manifest = _parse_field_manifest(data.get("field_manifest"))
        conversation_id = _sanitize_conversation_id(data.get("conversation_id"))
        temp_dir = _build_temp_dir(username, conversation_id)
        os.makedirs(temp_dir, exist_ok=True)

    if not text and not image_bytes:
        return jsonify({
            "status": "error",
            "reply": "請輸入問題或指令。" if lang == "zh" else "Vui lòng nhập câu hỏi hoặc lệnh.",
            "intent": "unknown",
        }), 400

    if not text and image_bytes:
        text = "[用戶發送了一張圖片，請根據圖片內容與 OCR 數據判斷意圖。如果是表格則嘗試記錄資料，如果是樣品照則嘗試查找樣品。]"

    # -- 微庫狀態提示注入 --
    # 只有當前回合真的涉及圖片時，才把微庫資訊附加到文字，避免污染純文字任務。
    try:
        should_attach_image_context = bool(image_bytes) or _text_requests_image_context(text)
        if should_attach_image_context:
            available_images = []
            if os.path.isdir(temp_dir):
                files = [f for f in os.listdir(temp_dir) if f.lower().endswith(('.jpg', '.jpeg', '.png'))]
                files.sort(key=lambda x: os.path.getmtime(os.path.join(temp_dir, x)), reverse=True)
                for f in files:
                    mtime = os.path.getmtime(os.path.join(temp_dir, f))
                    age_minutes = int((time.time() - mtime) / 60)
                    if age_minutes == 0:
                        age_str = "剛剛"
                    elif age_minutes < 60:
                        age_str = f"{age_minutes} 分鐘前"
                    else:
                        age_str = f"{age_minutes // 60} 小時前"
                    available_images.append(f"{f} ({age_str})")

            if available_images:
                images_list_str = "、".join(available_images)
                micro_lib_hint = f"\n\n[系統提示：目前『微庫』暫存區內有以下圖片：{images_list_str}。如果需要提取圖片資料，可在視覺工具中使用對應的 image_id。]"
                text += micro_lib_hint
                current_app.logger.info(f"[AI Chat] 已注入微庫 Context: {images_list_str}")
    except Exception as e:
        current_app.logger.warning(f"[AI Chat] 注入微庫 Context 失敗：{e}")

    try:
        from ..ai_engine import intent_dispatcher
        result = intent_dispatcher.dispatch(
            text=text,
            route_text=routing_text,
            lang=lang,
            db_path=_get_db_path(),
            processor=processor,
            username=username,
            image_bytes=image_bytes,
            history=history,
            current_entity=current_entity,
            field_manifest=field_manifest,
            conversation_id=conversation_id,
        )
        return jsonify(result)
    except Exception as exc:
        current_app.logger.error(f"[AI Chat] 錯誤：{exc}", exc_info=True)
        return jsonify({
            "status": "error",
            "reply": f"處理失敗：{exc}" if lang == "zh" else f"Lỗi xử lý: {exc}",
            "intent": "unknown",
        }), 500


# ---------------------------------------------------------------------------
# POST /api/ai/image-ingest
# ---------------------------------------------------------------------------
@bp.route("/image-ingest", methods=["POST"])
@operator_required
def image_ingest():
    """
    圖片入庫：識別單據 + 向量化，寫入 image_vectors 表。

    Request: multipart/form-data
      - file       : 圖片檔案（必要）
      - entity_type: 關聯實體類型，例如 'fabric', 'sample'（可選）
      - entity_id  : 關聯實體 ID（可選）
      - save_path  : 圖片存放路徑（可選，填絕對或相對路徑；不填則不儲存）

    Response JSON:
      {
        "status": "ok",
        "id": <image_vectors.id>,
        "ocr_data": { "product_name": "...", "qty": ..., "unit_price": ... },
        "message": "..."
      }
    """
    processor = _get_processor()
    if processor is None:
        return jsonify({"status": "error", "message": "AI 服務未就緒"}), 503

    if "file" not in request.files:
        return jsonify({"status": "error", "message": "請上傳圖片（file 欄位）"}), 400

    file = request.files["file"]
    if not file.filename:
        return jsonify({"status": "error", "message": "檔案名稱為空"}), 400

    image_bytes = file.read()
    entity_type = request.form.get("entity_type", None)
    entity_id_raw = request.form.get("entity_id", None)
    entity_id = int(entity_id_raw) if entity_id_raw and entity_id_raw.isdigit() else None

    # 預設儲存路徑：SAMPLES_UPLOAD_DIR（src/data/uploads/samples）
    import time
    samples_dir = current_app.config.get("SAMPLES_UPLOAD_DIR", "")
    if not samples_dir:
        # fallback：相對於 instance 路徑
        samples_dir = os.path.join(os.path.dirname(current_app.instance_path), "data", "uploads", "samples")

    # 以時間戳前綴避免檔名衝突
    safe_filename = f"{int(time.time())}_{file.filename.replace(os.sep, '_')}"
    save_path = request.form.get("save_path") or os.path.join(samples_dir, safe_filename)

    from ..ai_engine import ai_service
    import json as _json

    # Step 1: OCR 識別
    try:
        ocr_data = ai_service.parse_document_image(image_bytes)
    except Exception as e:
        current_app.logger.error(f"[image-ingest] OCR 失敗：{e}", exc_info=True)
        ocr_data = {"product_name": None, "qty": None, "unit_price": None}

    # Step 2: 計算向量
    try:
        embedding = ai_service.compute_image_embedding(image_bytes)
        embedding_blob = embedding.tobytes()
        embedding_dim = int(embedding.shape[0])
    except Exception as e:
        current_app.logger.error(f"[image-ingest] 向量計算失敗：{e}", exc_info=True)
        return jsonify({"status": "error", "message": f"向量計算失敗：{e}"}), 500

    # Step 3: 儲存圖片（若提供 save_path）
    image_path = save_path or ""
    if save_path:
        try:
            os.makedirs(os.path.dirname(os.path.abspath(save_path)), exist_ok=True)
            with open(save_path, "wb") as f:
                f.write(image_bytes)
        except Exception as e:
            current_app.logger.warning(f"[image-ingest] 圖片儲存失敗（不影響入庫）：{e}")

    # Step 4: 寫入 image_vectors
    db_path = _get_db_path()
    conn = sqlite3.connect(db_path)
    try:
        cursor = conn.execute(
            """INSERT INTO image_vectors
               (image_path, entity_type, entity_id, ocr_data, embedding, embedding_dim)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (
                image_path,
                entity_type,
                entity_id,
                _json.dumps(ocr_data, ensure_ascii=False),
                embedding_blob,
                embedding_dim,
            ),
        )
        conn.commit()
        new_id = cursor.lastrowid
    finally:
        conn.close()

    return jsonify({
        "status": "ok",
        "id": new_id,
        "ocr_data": ocr_data,
        "message": "圖片已入庫並向量化。",
    })


# ---------------------------------------------------------------------------
# POST /api/ai/image-search
# ---------------------------------------------------------------------------
@bp.route("/image-search", methods=["POST"])
@operator_required
def image_search():
    """
    以圖搜圖：上傳查詢圖片，回傳最相似的已入庫圖片。

    Request: multipart/form-data
      - file  : 查詢圖片（必要）
      - top_k : 回傳最多幾筆（預設 5）

    Response JSON:
      {
        "status": "ok",
        "results": [
          {
            "id": ...,
            "image_path": "...",
            "entity_type": "...",
            "entity_id": ...,
            "ocr_data": {...},
            "score": 0.97
          }, ...
        ]
      }
    """
    processor = _get_processor()
    if processor is None:
        return jsonify({"status": "error", "message": "AI 服務未就緒"}), 503

    if "file" not in request.files:
        return jsonify({"status": "error", "message": "請上傳圖片（file 欄位）"}), 400

    file = request.files["file"]
    if not file.filename:
        return jsonify({"status": "error", "message": "檔案名稱為空"}), 400

    image_bytes = file.read()
    top_k_raw = request.form.get("top_k", "5")
    top_k = int(top_k_raw) if top_k_raw.isdigit() else 5

    from ..ai_engine import ai_service

    # Step 1: 計算查詢向量
    try:
        query_embedding = ai_service.compute_image_embedding(image_bytes)
    except Exception as e:
        current_app.logger.error(f"[image-search] 向量計算失敗：{e}", exc_info=True)
        return jsonify({"status": "error", "message": f"向量計算失敗：{e}"}), 500

    # Step 2: 搜索相似圖片
    try:
        results = ai_service.search_similar_images(
            query_embedding=query_embedding,
            db_path=_get_db_path(),
            top_k=top_k,
        )
    except Exception as e:
        current_app.logger.error(f"[image-search] 搜索失敗：{e}", exc_info=True)
        return jsonify({"status": "error", "message": f"搜索失敗：{e}"}), 500

    return jsonify({"status": "ok", "results": results})


# ---------------------------------------------------------------------------
# POST /api/ai/ocr (Legacy/Contract Support)
# ---------------------------------------------------------------------------
@bp.route("/ocr", methods=["POST"])
@operator_required
def ocr():
    """
    純 OCR 識別介面（供舊版或 Contract 驗證使用）。
    Request: multipart/form-data (file)
    """
    if "file" not in request.files:
        return jsonify({"status": "error", "message": "Missing file"}), 400
    
    file = request.files["file"]
    from ..ai_engine import ai_service
    try:
        ocr_data = ai_service.parse_document_image(file.read())
        return jsonify({"status": "ok", "ocr_data": ocr_data})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500
