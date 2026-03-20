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
    username = g.user["username"] if g.user else "operator"
    
    # 用於儲存與讀取最後一次上傳的圖片（跨回合記憶）
    import os
    from flask import current_app
    temp_dir = os.path.join(current_app.root_path, "static", "uploads", "temp_ai")
    os.makedirs(temp_dir, exist_ok=True)
    last_img_path = os.path.join(temp_dir, f"last_chat_image_{username}.jpg")
    
    if request.content_type and "multipart" in request.content_type:
        text = (request.form.get("text") or "").strip()
        lang = request.form.get("lang", "zh")
        hist_raw = request.form.get("history")
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
                # 存入備份，供下一回合使用
                with open(last_img_path, "wb") as f:
                    f.write(image_bytes)

                # [新增] 立即嘗試 OCR 提取顏色表（預處理）
                try:
                    from ..ai_engine import ai_service
                    ocr_prompt = "請識別圖片中的顏色表，列出所有的 RGB 與對應的 LAB 或 YMCK。格式儘量整齊。"
                    ocr_raw = ai_service.call_ollama(
                        prompt=ocr_prompt,
                        images=[image_bytes],
                        temperature=0.0,
                        max_tokens=1024
                    )
                    if ocr_raw:
                        # 放在 text 最前面，讓主腦第一時間看到
                        text = f"[系統自動解析當前圖片內容：\n{ocr_raw}\n]\n\n" + text
                        current_app.logger.info("[AI Chat] 立即 OCR 成功，已併入文字 context")
                except Exception as ocr_err:
                    current_app.logger.warning(f"[AI Chat] 立即 OCR 失敗（跳過）：{ocr_err}")
    else:
        data = request.get_json(silent=True) or {}
        text = str(data.get("text") or "").strip()
        lang = data.get("lang", "zh")
        history = data.get("history", [])

    if not text and not image_bytes:
        return jsonify({
            "status": "error",
            "reply": "請輸入問題或指令。" if lang == "zh" else "Vui lòng nhập câu hỏi hoặc lệnh.",
            "intent": "unknown",
        }), 400

    if not text and image_bytes:
        text = "[用戶發送了一張圖片，請根據圖片內容與 OCR 數據判斷意圖。如果是表格則嘗試記錄資料，如果是樣品照則嘗試查找樣品。]"

    # 如果當前沒上傳圖片，但有歷史紀錄，嘗試從備份讀取（實現跨回合記憶）
    if not image_bytes and history and os.path.exists(last_img_path):
        vision_keywords = ["圖", "照片", "表", "圖片", "這裡面", "picture", "image", "table", "chart"]
        if any(k in text for k in vision_keywords) or "就在這" in text:
            with open(last_img_path, "rb") as f:
                image_bytes = f.read()
            current_app.logger.info(f"[AI Chat] 從備份載入圖片 context (user: {username})")
            
            try:
                from ..ai_engine import ai_service
                # 使用測試成功的簡單 Prompt
                ocr_prompt = "請識別圖片中的顏色表，列出所有的 RGB 與對應的 LAB 或 YMCK。只要回傳資料內容即可。"
                ocr_raw = ai_service.call_ollama(
                    prompt=ocr_prompt,
                    images=[image_bytes],
                    temperature=0.0,
                    max_tokens=1024
                )
                if ocr_raw:
                    # 注入到 text 中，放在最前面以策安全
                    text = f"[系統偵測到圖片內容並自動解析如下，請優先參考：\n{ocr_raw}\n]\n\n" + text
                    current_app.logger.info("[AI Chat] 立即 OCR 成功，已併入文字 context")
            except Exception as ocr_err:
                current_app.logger.warning(f"[AI Chat] 立即 OCR 失敗：{ocr_err}")

    try:
        from ..ai_engine import intent_dispatcher
        result = intent_dispatcher.dispatch(
            text=text,
            lang=lang,
            db_path=_get_db_path(),
            processor=processor,
            username=username,
            image_bytes=image_bytes,
            history=history,
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
