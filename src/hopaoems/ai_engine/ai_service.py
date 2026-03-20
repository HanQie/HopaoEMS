"""
ai_service.py
=============
Ollama 通訊核心模組。

提供以下功能：
  - call_ollama()          : 向本地 Ollama 服務發送請求（支持圖片）
  - get_db_schema()        : 動態讀取 SQLite CREATE TABLE 語句
  - parse_document_image() : 用 qwen3-vl 識別單據圖片，輸出結構化 JSON
  - compute_image_embedding(): 使用 CLIP 對圖片計算特徵向量
  - search_similar_images(): 在 image_vectors 表中搜索最相似圖片

Ollama 服務預設地址：http://localhost:11434
"""

from __future__ import annotations

import base64
import json
import logging
import re
import sqlite3
from typing import Any, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 預設配置
# ---------------------------------------------------------------------------
_DEFAULT_BASE_URL = "http://localhost:11434"
_DEFAULT_TEXT_MODEL = "qwen3-vl:4b"
_DEFAULT_VL_MODEL = "qwen3-vl:4b"

# 全域配置（由 __init__.py 初始化時設定）
_config: dict[str, str] = {
    "base_url": _DEFAULT_BASE_URL,
    "text_model": _DEFAULT_TEXT_MODEL,
    "vl_model": _DEFAULT_VL_MODEL,
}


def configure(
    base_url: str = _DEFAULT_BASE_URL,
    text_model: str = _DEFAULT_TEXT_MODEL,
    vl_model: str = _DEFAULT_VL_MODEL,
) -> None:
    """由 ai_engine/__init__.py 呼叫，設定全域配置。"""
    _config["base_url"] = base_url
    _config["text_model"] = text_model
    _config["vl_model"] = vl_model
    logger.info(
        f"[ai_service] 配置完成 → base_url={base_url}, "
        f"text_model={text_model}, vl_model={vl_model}"
    )


def _strip_think_tags(text: str) -> str:
    """
    移除 <think>...</think> 及 <thinking>...</thinking> 區塊。
    支援未閉合標籤（將標籤之後的所有內容移除）。
    """
    # 處理閉合標籤
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<thinking>.*?</thinking>", "", text, flags=re.DOTALL | re.IGNORECASE)
    # 處理未閉合標籤（若標籤出現在結尾）
    text = re.sub(r"<think>.*", "", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<thinking>.*", "", text, flags=re.DOTALL | re.IGNORECASE)
    return text.strip()


# ---------------------------------------------------------------------------
# 核心：call_ollama
# ---------------------------------------------------------------------------
def call_ollama(
    prompt: str,
    system_prompt: str = "",
    images: Optional[list[bytes]] = None,
    model: Optional[str] = None,
    max_tokens: Optional[int] = None,
    temperature: Optional[float] = None,
) -> str:
    """
    向 Ollama 發送聊天請求並回傳模型文字輸出。

    Parameters
    ----------
    prompt        : 用戶訊息
    system_prompt : 系統角色 Prompt
    images        : 圖片 bytes 列表（傳入時自動 Base64 編碼）
    model         : 覆蓋預設模型名稱
    max_tokens    : 最大生成 token 數
    temperature   : 採樣溫度

    Raises
    ------
    ConnectionError : Ollama 服務未啟動或不可達
    RuntimeError    : 模型回應異常
    """
    try:
        import ollama as _ollama_sdk
    except ImportError:
        raise ImportError(
            "ollama SDK 未安裝，請執行：pip install ollama"
        )

    selected_model = model or (
        _config["vl_model"] if images else _config["text_model"]
    )

    # 構建訊息列表
    messages: list[dict] = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})

    user_msg: dict[str, Any] = {"role": "user", "content": prompt}

    # Ollama SDK：圖片以 base64 字串列表傳入 images 欄位
    if images:
        user_msg["images"] = [
            base64.b64encode(img).decode("utf-8") for img in images
        ]

    messages.append(user_msg)

    # 構建選項
    options: dict[str, Any] = {}
    if max_tokens:
        options["num_predict"] = max_tokens
    if temperature is not None:
        options["temperature"] = temperature

    logger.info(f"[Ollama] 發送請求 → 模型: {selected_model}, Prompt: {prompt[:50]}...")
    import time as _time
    start_t = _time.time()
    try:
        client = _ollama_sdk.Client(host=_config["base_url"])
        response = client.chat(
            model=selected_model,
            messages=messages,
            options=options if options else None,
        )
        raw = response.message.content or ""
        duration = _time.time() - start_t
        logger.info(f"[Ollama] 接收回應 ← 長度: {len(raw)} 字元, 耗時: {duration:.2f}s")
        return _strip_think_tags(raw)
    except Exception as e:
        err_str = str(e)
        logger.error(f"[Ollama] 請求失敗: {err_str}")
        if "connection" in err_str.lower() or "refused" in err_str.lower():
            raise ConnectionError(
                f"無法連接到 Ollama 服務（{_config['base_url']}）。"
                "請確認 Ollama 已啟動：ollama serve"
            )
        raise RuntimeError(f"Ollama 請求失敗：{e}")


# ---------------------------------------------------------------------------
# 核心：call_ollama_with_tools（Agent 用）
# ---------------------------------------------------------------------------
def call_ollama_with_tools(
    messages: list[dict],
    tools: list[dict] | None = None,
    model: str | None = None,
    max_tokens: int | None = None,
    temperature: float | None = None,
):
    """
    支持 Tool Calling 的 Ollama 聊天介面。

    與 call_ollama() 的差異：
    - 接收完整的 messages 列表（而非單一 prompt + system_prompt）
    - 接收 tools 列表（Ollama Function Calling schema）
    - 回傳完整的 Ollama response 物件（含 message.tool_calls）

    Parameters
    ----------
    messages    : 完整的聊天訊息列表
    tools       : Ollama tools schema 列表
    model       : 覆蓋預設模型名稱
    max_tokens  : 最大生成 token 數
    temperature : 採樣溫度

    Returns
    -------
    Ollama ChatResponse 物件
    """
    try:
        import ollama as _ollama_sdk
    except ImportError:
        raise ImportError("ollama SDK 未安裝，請執行：pip install ollama")

    selected_model = model or _config["text_model"]

    # 構建選項
    options: dict = {}
    if max_tokens:
        options["num_predict"] = max_tokens
    if temperature is not None:
        options["temperature"] = temperature

    logger.info(
        f"[Ollama/Tools] 發送請求 → 模型: {selected_model}, "
        f"messages: {len(messages)}, tools: {len(tools or [])}"
    )
    import time as _time
    start_t = _time.time()

    try:
        client = _ollama_sdk.Client(host=_config["base_url"])
        kwargs = {
            "model": selected_model,
            "messages": messages,
        }
        if options:
            kwargs["options"] = options
        if tools:
            kwargs["tools"] = tools

        response = client.chat(**kwargs)
        duration = _time.time() - start_t
        has_tools = bool(response.message.tool_calls)
        logger.info(
            f"[Ollama/Tools] 接收回應 ← "
            f"has_tool_calls: {has_tools}, "
            f"content_len: {len(response.message.content or '')}, "
            f"耗時: {duration:.2f}s"
        )
        return response
    except Exception as e:
        err_str = str(e)
        logger.error(f"[Ollama/Tools] 請求失敗: {err_str}")
        if "connection" in err_str.lower() or "refused" in err_str.lower():
            raise ConnectionError(
                f"無法連接到 Ollama 服務（{_config['base_url']}）。"
                "請確認 Ollama 已啟動：ollama serve"
            )
        raise RuntimeError(f"Ollama 請求失敗：{e}")


# ---------------------------------------------------------------------------
# Text-to-SQL 輔助：get_db_schema
# ---------------------------------------------------------------------------
def get_db_schema(db_path: str) -> str:
    """
    動態讀取 SQLite 資料庫的 CREATE TABLE 語句，
    回傳格式化的 Schema 字串（供 sql_agent 注入 prompt 用）。
    """
    try:
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        cursor = conn.execute(
            "SELECT name, sql FROM sqlite_master "
            "WHERE type='table' AND name NOT LIKE 'sqlite_%' "
            "ORDER BY name;"
        )
        rows = cursor.fetchall()
        conn.close()

        parts = []
        for name, sql in rows:
            if sql:
                parts.append(sql.strip())
        schema = "\n\n".join(parts)
        logger.debug(f"[ai_service] 讀取到 {len(rows)} 個資料表 schema")
        return schema
    except Exception as e:
        logger.error(f"[ai_service] 讀取 schema 失敗：{e}")
        return ""


def get_table_names_from_schema(schema_sql: str) -> frozenset[str]:
    """從 schema SQL 字串中提取所有表名。"""
    tables = re.findall(r"CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?[`\"']?(\w+)[`\"']?", schema_sql, re.IGNORECASE)
    return frozenset(t.lower() for t in tables)


# ---------------------------------------------------------------------------
# Phase 3：圖片 OCR 識別
# ---------------------------------------------------------------------------
_DOCUMENT_OCR_PROMPT = """請識別這張單據圖片（可能是中文或越南語）。
提取以下資料：
- product_name: 產品名稱
- qty: 數量（純數字，無單位）
- unit_price: 單價（純數字，無貨幣符號）

請**只回傳 JSON**，格式如下（無 markdown 包裝）：
{"product_name": "...", "qty": 0, "unit_price": 0.0}

如果某個欄位無法識別，設為 null。"""


def parse_document_image(image_bytes: bytes) -> dict[str, Any]:
    """
    傳送圖片給 qwen3-vl，識別單據並回傳結構化 JSON。

    Returns
    -------
    dict with keys: product_name, qty, unit_price
    （識別失敗時各欄位為 null）
    """
    try:
        raw = call_ollama(
            prompt=_DOCUMENT_OCR_PROMPT,
            images=[image_bytes],
            temperature=0.0,
            max_tokens=512,
        )
        # 嘗試解析 JSON
        raw = _strip_think_tags(raw)
        # 找第一個 { ... }
        start = raw.find("{")
        end = raw.rfind("}")
        if start != -1 and end != -1:
            return json.loads(raw[start:end + 1])
    except Exception as e:
        logger.error(f"[ai_service] 圖片識別失敗：{e}")

    return {"product_name": None, "qty": None, "unit_price": None}


# ---------------------------------------------------------------------------
# Phase 3：圖片 Embedding（CLIP）
# ---------------------------------------------------------------------------
_embedding_model = None  # lazy load


def _get_embedding_model():
    """延遲載入 CLIP embedding 模型（首次使用時下載）。"""
    global _embedding_model
    if _embedding_model is None:
        try:
            from sentence_transformers import SentenceTransformer
            logger.info("[ai_service] 載入 CLIP embedding 模型（clip-ViT-B-32）...")
            _embedding_model = SentenceTransformer("clip-ViT-B-32")
            logger.info("[ai_service] CLIP 模型載入完成")
        except ImportError:
            raise ImportError(
                "sentence-transformers 未安裝，請執行：pip install sentence-transformers"
            )
    return _embedding_model


def compute_image_embedding(image_bytes: bytes):
    """
    使用 CLIP ViT-B/32 對圖片計算特徵向量。

    Returns
    -------
    numpy.ndarray, shape=(512,), dtype=float32
    """
    from PIL import Image
    import io
    import numpy as np

    model = _get_embedding_model()
    img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    embedding = model.encode(img, convert_to_numpy=True)
    return embedding.astype("float32")


# ---------------------------------------------------------------------------
# Phase 3：以圖搜圖
# ---------------------------------------------------------------------------
def search_similar_images(
    query_embedding,
    db_path: str,
    top_k: int = 5,
) -> list[dict[str, Any]]:
    """
    在 image_vectors 表中計算餘弦相似度，回傳最相似的 top_k 記錄。

    Parameters
    ----------
    query_embedding : numpy.ndarray (512,)
    db_path         : SQLite 資料庫路徑
    top_k           : 回傳最多幾筆結果

    Returns
    -------
    list of dict: [{image_path, entity_type, entity_id, ocr_data, score}, ...]
    """
    import numpy as np

    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            "SELECT id, image_path, entity_type, entity_id, ocr_data, "
            "embedding, embedding_dim FROM image_vectors"
        ).fetchall()
    finally:
        conn.close()

    if not rows:
        return []

    # 正規化查詢向量
    q = query_embedding.astype("float32")
    q_norm = q / (np.linalg.norm(q) + 1e-9)

    results = []
    for row in rows:
        try:
            dim = row["embedding_dim"]
            vec = np.frombuffer(row["embedding"], dtype="float32")
            if vec.shape[0] != dim:
                continue
            v_norm = vec / (np.linalg.norm(vec) + 1e-9)
            score = float(np.dot(q_norm, v_norm))
            results.append({
                "id": row["id"],
                "image_path": row["image_path"],
                "entity_type": row["entity_type"],
                "entity_id": row["entity_id"],
                "ocr_data": json.loads(row["ocr_data"]) if row["ocr_data"] else None,
                "score": round(score, 4),
            })
        except Exception as e:
            logger.warning(f"[ai_service] 向量計算跳過 id={row['id']}：{e}")

    results.sort(key=lambda x: x["score"], reverse=True)
    return results[:top_k]
