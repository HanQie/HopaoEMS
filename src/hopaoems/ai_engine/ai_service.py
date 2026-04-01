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
import io
import json
import logging
import re
import sqlite3
import sys
import math
from typing import Any, Optional

logger = logging.getLogger(__name__)
_rapid_ocr_engine = None

# ---------------------------------------------------------------------------
# 預設配置
# ---------------------------------------------------------------------------
_DEFAULT_BASE_URL = "http://localhost:11434"
_DEFAULT_TEXT_MODEL = "qwen2.5:7b"
_DEFAULT_VL_MODEL = "qwen3-vl:4b"
_DEFAULT_OCR_MODEL = "qwen3-vl:4b"

# 全域配置（由 __init__.py 初始化時設定）
_config: dict[str, str] = {
    "base_url": _DEFAULT_BASE_URL,
    "text_model": _DEFAULT_TEXT_MODEL,
    "vl_model": _DEFAULT_VL_MODEL,
    "ocr_model": _DEFAULT_OCR_MODEL,
}


def configure(
    base_url: str = _DEFAULT_BASE_URL,
    text_model: str = _DEFAULT_TEXT_MODEL,
    vl_model: str = _DEFAULT_VL_MODEL,
    ocr_model: str = _DEFAULT_OCR_MODEL,
) -> None:
    """由 ai_engine/__init__.py 呼叫，設定全域配置。"""
    _config["base_url"] = base_url
    _config["text_model"] = text_model
    _config["vl_model"] = vl_model
    _config["ocr_model"] = ocr_model
    logger.info(
        f"[ai_service] 配置完成 → base_url={base_url}, "
        f"text_model={text_model}, vl_model={vl_model}, ocr_model={ocr_model}"
    )


def _extract_think_tags(text: str) -> str:
    """提取 <think>...</think> 區塊內容，用於前端展示。"""
    match = re.search(r"<think>(.*?)</think>", text, flags=re.DOTALL | re.IGNORECASE)
    if match: return match.group(1).strip()
    match = re.search(r"<thinking>(.*?)</thinking>", text, flags=re.DOTALL | re.IGNORECASE)
    if match: return match.group(1).strip()
    match = re.search(r"<think>(.*)", text, flags=re.DOTALL | re.IGNORECASE)
    if match: return match.group(1).strip()
    match = re.search(r"<thinking>(.*)", text, flags=re.DOTALL | re.IGNORECASE)
    if match: return match.group(1).strip()
    return ""


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


def summarize_reasoning_debug(text: str, max_points: int = 5) -> str:
    """
    將模型的私有思考內容壓縮成可除錯的安全摘要。
    不回傳逐字推理，只保留高層步驟。
    """
    if not text:
        return ""

    cleaned = re.sub(r"\s+", " ", text).strip()
    if not cleaned:
        return ""

    chunks = re.split(r"(?<=[。.!?])\s+|\s*[\n\r]+\s*|(?<=[:：])\s+", cleaned)
    seen: list[str] = []
    for chunk in chunks:
        item = chunk.strip(" -•\t")
        if len(item) < 4:
            continue
        if item.lower().startswith(("think", "thinking", "final answer")):
            continue
        if item in seen:
            continue
        seen.append(item[:160])
        if len(seen) >= max_points:
            break

    if not seen:
        return "模型完成了多步判斷，已省略原始推理內容。"

    return "\n".join(f"- {item}" for item in seen)


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
    candidate_models: list[str] = [selected_model]
    if images:
        fallback_vl_models = [
            _config.get("ocr_model"),
            _config.get("vl_model"),
            "qwen2.5vl:3b",
        ]
        for fallback_model in fallback_vl_models:
            if fallback_model and fallback_model not in candidate_models:
                candidate_models.append(fallback_model)

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
    client = _ollama_sdk.Client(host=_config["base_url"])
    last_error: Exception | None = None
    for attempt_idx, attempt_model in enumerate(candidate_models, start=1):
        start_t = _time.time()
        try:
            response = client.chat(
                model=attempt_model,
                messages=messages,
                options=options if options else None,
            )
            raw = response.message.content or ""
            duration = _time.time() - start_t
            logger.info(
                f"[Ollama] 接收回應 ← 模型: {attempt_model}, 長度: {len(raw)} 字元, 耗時: {duration:.2f}s"
            )
            return _strip_think_tags(raw)
        except Exception as e:
            last_error = e
            err_str = str(e)
            logger.error(f"[Ollama] 請求失敗(model={attempt_model}, attempt={attempt_idx}/{len(candidate_models)}): {err_str}")
            if "connection" in err_str.lower() or "refused" in err_str.lower():
                raise ConnectionError(
                    f"無法連接到 Ollama 服務（{_config['base_url']}）。"
                    "請確認 Ollama 已啟動：ollama serve"
                )
            resource_error = (
                "unexpectedly stopped" in err_str.lower()
                or "resource limitations" in err_str.lower()
                or "status code: 500" in err_str.lower()
                or "internal error" in err_str.lower()
            )
            has_next_model = attempt_idx < len(candidate_models)
            if images and resource_error and has_next_model:
                logger.warning(f"[Ollama] 視覺模型失敗，改用較輕量模型重試：{candidate_models[attempt_idx]}")
                continue
            break

    raise RuntimeError(f"Ollama 請求失敗：{last_error}")


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

_COLOR_TABLE_OCR_PROMPT = """請讀取這張圖片中的顏色校正表。
只提取可辨識的資料內容，不要解釋。
優先保留：
- RGB / Input 數值
- LAB / YMCK / Output 數值
- 每一列的對應關係
如果看起來不是顏色表，回傳 NOT_COLOR_TABLE。"""

_COLOR_TABLE_TRANSCRIBE_PROMPT = """請只做 OCR 轉錄，不要解釋，不要摘要。
把圖片中的每一列輸出成一行，保留原本數字順序。
若某列是 LAB，格式盡量寫成：
RGB: r g b => LAB: l a b
若某列是 YMCKBHFm，格式盡量寫成：
RGB: r g b => YMCKBHFm: n n n n n n n n
如果你無法完全辨識，也請盡量逐字輸出你看見的內容。"""

_COLOR_TABLE_JSON_PROMPT = """請讀取一張小型電腦截圖中的顏色對照表。
只回傳 JSON array，不要 markdown，不要說明。

每一列輸出格式：
{
  "rgb_r": 120,
  "rgb_g": 157,
  "rgb_b": 203,
  "target_mode": "LAB" | "YMCKBHFm",
  "target_l": 62.71,
  "target_a": -4.58,
  "target_b": -25.46,
  "target_note": ""
}

規則：
- 若右側是 LAB，必須拆成 target_l/target_a/target_b。
- 若右側是 YMCKBHFm 八個整數，放進 target_note，例如 "0 0 0 0 0 1 2 0"。
- 看不清楚的列可以略過，但不要編造不存在的數字。
- 目標是盡量提取全部有效列。
"""

_STOCK_IN_OCR_PROMPT = """請讀取這張布料/標籤/入庫照片中可辨識的資料。
只列出你看得到的原始內容，不要猜測。
優先提取：
- 布號 / fabric code
- 缸號 / cylinder no
- 疋號 / roll no
- 重量 / kg
- 材質 / material
如果沒有這些欄位，就回傳 NOT_STOCK_IN。"""

_IMAGE_CLASSIFY_PROMPT = """請判斷這張圖片最接近哪一種類型。
只能回傳 JSON：
{"image_kind":"sample_photo|color_table|stock_in_label|document|unknown","reason":"...","confidence":"high|medium|low"}

判斷原則：
- sample_photo: 布樣、花版、樣品照片
- color_table: 對色表、RGB/LAB/YMCK 對照表、色彩校正截圖
- stock_in_label: 布標、疋卡、入庫標籤、重量/缸號/布號資訊
- document: 一般單據或文件截圖
- unknown: 無法判斷
"""

_SAMPLE_TITLE_PROMPT = """請根據這張樣品圖片，產生一個適合建立樣品資料的名稱建議。
只能回傳 JSON：
{"suggested_title":"...","keywords":["...","..."],"confidence":"high|medium|low","needs_user_confirmation":true}

規則：
- 名稱簡短、可用於樣品標題
- 若無法判斷就給保守描述
- 不要輸出多餘說明
"""

_STOCK_IN_EXTRACT_PROMPT = """請從這張布料標籤、疋卡或入庫照片中提取可辨識的入庫資料。
只能回傳 JSON：
{
  "fabric_code": "...",
  "cylinder_no": "...",
  "material": "...",
  "note": "...",
  "confidence": "high|medium|low",
  "missing_fields": ["..."],
  "rolls": [
    {"roll_no": "...", "weight_kg": 0, "length_m": 0}
  ]
}

規則：
- 看不到就填 null 或空陣列，不要猜
- rolls 可為空
- 如果只有部分欄位可辨識，也照樣回傳 JSON
- 若關鍵欄位模糊，confidence 降為 low，並把缺的欄位放進 missing_fields
"""


def _extract_json_object(raw: str) -> dict[str, Any] | None:
    """從模型回應中提取第一個 JSON object。"""
    raw = _strip_think_tags(raw)
    start = raw.find("{")
    end = raw.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return None
    try:
        return json.loads(raw[start:end + 1])
    except Exception:
        return None


def _extract_json_array(raw: str) -> list[dict[str, Any]] | None:
    """從模型回應中提取第一個 JSON array。"""
    raw = _strip_think_tags(raw)
    start = raw.find("[")
    end = raw.rfind("]")
    if start == -1 or end == -1 or end <= start:
        return None
    try:
        data = json.loads(raw[start:end + 1])
        return data if isinstance(data, list) else None
    except Exception:
        return None


def should_preprocess_chat_image(text: str) -> bool:
    """
    僅在需要結構化辨識時才先做圖片預處理，避免所有圖片都先打 VL。
    以圖搜樣品這類場景直接交給 agent + embedding tool。
    """
    lowered = (text or "").lower()
    if not lowered.strip():
        return False

    search_keywords = (
        "找", "搜尋", "搜索", "查", "是哪個", "叫什麼", "名稱", "樣品", "相似",
        "search", "find", "lookup", "name", "similar", "sample",
    )
    structured_keywords = (
        "對色", "對色紀錄", "色表", "換色", "校正", "校色", "校色紀錄",
        "數色", "數色紀錄", "配色", "配色紀錄", "rgb", "lab", "ymck",
        "入庫", "布號", "缸號", "重量", "疋", "roll", "fabric", "stock",
        "register", "record", "ocr", "table", "chart",
    )

    if any(k in lowered for k in structured_keywords):
        return True
    if any(k in lowered for k in search_keywords):
        return False
    return False


def build_chat_image_context(text: str, image_bytes: bytes) -> str:
    """
    依據聊天內容選擇較便宜的圖片前處理提示。
    回傳適合注入 agent context 的文字；若不適合預處理則回傳空字串。
    """
    if not should_preprocess_chat_image(text):
        return ""

    lowered = (text or "").lower()
    if any(
        k in lowered
        for k in (
            "對色", "對色紀錄", "色表", "換色", "校正", "校色", "校色紀錄",
            "數色", "數色紀錄", "配色", "配色紀錄", "rgb", "lab", "ymck", "table", "chart",
        )
    ):
        prompt = _COLOR_TABLE_OCR_PROMPT
        header = "[系統偵測到圖片可能是顏色表，已先做輕量辨識如下：\n"
    else:
        prompt = _STOCK_IN_OCR_PROMPT
        header = "[系統偵測到圖片可能與入庫/標籤有關，已先做輕量辨識如下：\n"

    try:
        raw = call_ollama(
            prompt=prompt,
            images=[image_bytes],
            model=_config["ocr_model"],
            temperature=0.0,
            max_tokens=768,
        )
    except Exception as e:
        logger.warning(f"[ai_service] 圖片前處理失敗，跳過：{e}")
        return ""

    cleaned = _strip_think_tags(raw)
    if not cleaned or cleaned in {"NOT_COLOR_TABLE", "NOT_STOCK_IN"}:
        return ""
    return f"{header}{cleaned}\n]\n\n"


def _prepare_image_for_ocr(image_bytes: bytes, scale: int = 4) -> bytes:
    from PIL import Image, ImageFilter, ImageOps

    Image.MAX_IMAGE_PIXELS = None
    img = Image.open(io.BytesIO(image_bytes))
    img = ImageOps.exif_transpose(img).convert("RGB")
    target_scale = float(scale or 1)
    max_pixels = 60_000_000
    max_side = 7000
    scale_by_pixels = math.sqrt(max_pixels / max(1, img.width * img.height))
    scale_by_side = max_side / max(1, max(img.width, img.height))
    applied_scale = max(0.5, min(target_scale, scale_by_pixels, scale_by_side))
    new_size = (
        max(1, int(img.width * applied_scale)),
        max(1, int(img.height * applied_scale)),
    )
    img = img.resize(new_size, Image.Resampling.LANCZOS)
    img = img.filter(ImageFilter.SHARPEN)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _get_rapid_ocr_engine():
    global _rapid_ocr_engine
    if _rapid_ocr_engine is None:
        from rapidocr_onnxruntime import RapidOCR

        _rapid_ocr_engine = RapidOCR()
    return _rapid_ocr_engine


def _polygon_bounds(points: list[list[float]] | tuple[tuple[float, float], ...]) -> tuple[float, float, float, float]:
    xs = [float(point[0]) for point in points]
    ys = [float(point[1]) for point in points]
    return min(xs), min(ys), max(xs), max(ys)


def _clean_ocr_text(text: str) -> str:
    cleaned = str(text or "").strip()
    cleaned = cleaned.replace("：", ":")
    cleaned = cleaned.replace("，", ",")
    cleaned = re.sub(r"(?<=\d):(?=\d)", ".", cleaned)
    cleaned = cleaned.replace("O", "0").replace("o", "0")
    return cleaned


def _run_local_ocr_items(image_bytes: bytes) -> list[dict[str, Any]]:
    engine = _get_rapid_ocr_engine()
    from PIL import Image, ImageOps

    Image.MAX_IMAGE_PIXELS = None
    base_image = Image.open(io.BytesIO(image_bytes))
    base_image = ImageOps.exif_transpose(base_image).convert("RGB")

    rotations = [0]
    if base_image.width >= base_image.height * 1.15:
        rotations.extend([90, 270])

    base_scale = 4.0 if max(base_image.width, base_image.height) <= 1400 else 1.5
    best_items: list[dict[str, Any]] = []
    best_score = -1.0

    for rotate in rotations:
        variant = base_image.rotate(rotate, expand=True) if rotate else base_image.copy()
        buf = io.BytesIO()
        variant.save(buf, format="PNG")
        prepared = _prepare_image_for_ocr(buf.getvalue(), scale=base_scale)
        result, _ = engine(prepared)
        if not result:
            continue

        items: list[dict[str, Any]] = []
        joined_len = 0
        for item in result:
            if len(item) < 2 or not item[1]:
                continue
            box = item[0]
            text = _clean_ocr_text(item[1])
            if not text:
                continue
            score = float(item[2]) if len(item) >= 3 else 0.0
            left, top, right, bottom = _polygon_bounds(box)
            items.append({
                "box": box,
                "text": text,
                "score": score,
                "left": left,
                "top": top,
                "right": right,
                "bottom": bottom,
                "cx": (left + right) / 2.0,
                "cy": (top + bottom) / 2.0,
            })
            joined_len += len(text)

        candidate_score = joined_len + (len(items) * 8)
        if candidate_score > best_score:
            best_score = candidate_score
            best_items = items

    return best_items


def _run_local_ocr_lines(image_bytes: bytes) -> list[str]:
    return [item["text"] for item in _run_local_ocr_items(image_bytes)]


def extract_text_from_image_local(image_bytes: bytes) -> str:
    """以本地 OCR 提取圖片中的可辨識文字，避免完全依賴 VL 模型。"""
    try:
        lines = [line.strip() for line in _run_local_ocr_lines(image_bytes) if str(line or "").strip()]
    except Exception as e:
        logger.warning(f"[ai_service] 本地 OCR 文本提取失敗：{e}")
        return ""
    return "\n".join(lines).strip()


def _split_rgb_digits(raw_digits: str) -> tuple[int, int, int] | None:
    digits = re.sub(r"\D", "", raw_digits or "")
    if len(digits) < 3 or len(digits) > 9:
        return None

    candidates = []
    for a_len in range(1, 4):
        for b_len in range(1, 4):
            c_len = len(digits) - a_len - b_len
            if c_len < 1 or c_len > 3:
                continue
            a = int(digits[:a_len])
            b = int(digits[a_len:a_len + b_len])
            c = int(digits[a_len + b_len:])
            if all(0 <= v <= 255 for v in (a, b, c)):
                score = sum(1 for ln in (a_len, b_len, c_len) if ln >= 2)
                candidates.append(((a, b, c), score, (a_len, b_len, c_len)))

    if not candidates:
        return None

    candidates.sort(key=lambda item: (item[1], item[2]), reverse=True)
    return candidates[0][0]


def _parse_lab_output_text(text: str) -> dict[str, Any] | None:
    cleaned = _clean_ocr_text(text)
    # Optional "LAB" label, but match exactly three space-separated number blocks (could be floats or negatives)
    match = re.search(
        r"(?:LAB[:\s]*)?(-?\d+(?:\.\d+)?)\s+(-?\d+(?:\.\d+)?)\s+(-?\d+(?:\.\d+)?)",
        cleaned,
        re.IGNORECASE,
    )
    if not match:
        return None
    return {
        "target_mode": "LAB",
        "target_l": float(match.group(1)),
        "target_a": float(match.group(2)),
        "target_b": float(match.group(3)),
        "target_note": "",
    }


def _expand_note_tokens(tokens: list[str]) -> list[str]:
    digits: list[str] = []
    for token in tokens:
        raw = re.sub(r"\D", "", token or "")
        if not raw:
            continue
        if len(raw) == 1:
            digits.append(raw)
            continue
        digits.extend(list(raw))
    if len(digits) > 8 and digits and digits[0] == "1":
        digits = digits[1:]
    return digits[:8]


def _parse_ymck_note_text(text: str) -> dict[str, Any] | None:
    cleaned = _clean_ocr_text(text)
    
    # 只要由一連串的數字與空白組成，或是具有 YMCK 標籤
    is_ymck = "YMCK" in cleaned.upper()
    tail = cleaned.split(":", 1)[1] if ":" in cleaned else cleaned
    
    # 若沒有 YMCK 標籤，但整串大部分都是數字與空白（大於5個數字）
    tokens = re.findall(r"\d+", tail)
    digits = _expand_note_tokens(tokens)
    if not digits:
        digits = list(re.sub(r"\D", "", tail))
        
    if not is_ymck and len(digits) < 6:
        return None # 不夠像 YMCK 記錄
        
    if len(digits) > 8 and digits[0] == "1":
        digits = digits[1:]
    if len(digits) < 8:
        digits.extend(["0"] * (8 - len(digits)))
    digits = digits[:8]
    return {
        "target_mode": "YMCKBHFm",
        "target_note": " ".join(digits),
    }


def _parse_output_text(text: str) -> dict[str, Any] | None:
    output = _parse_lab_output_text(text)
    if output:
        return output
    return _parse_ymck_note_text(text)


def _parse_color_table_ocr_items(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not items:
        return []

    rgb_items: list[dict[str, Any]] = []
    output_items: list[dict[str, Any]] = []

    for item in items:
        text = item["text"]
        if re.search(r"\bRGB\b", text, re.IGNORECASE):
            rgb_match = re.search(r"RGB[:\s]*([0-9\s]+)", text, re.IGNORECASE)
            rgb = _split_rgb_digits(rgb_match.group(1) if rgb_match else text)
            if rgb:
                rgb_items.append({**item, "rgb": rgb})
            continue

        output = _parse_output_text(text)
        if output:
            output_items.append({**item, "output": output})

    rgb_items.sort(key=lambda item: (item["cy"], item["left"]))
    output_items.sort(key=lambda item: (item["cy"], item["left"]))

    rows = []
    used_output_ids: set[int] = set()
    for rgb_item in rgb_items:
        candidates = [
            out for out in output_items
            if id(out) not in used_output_ids
            and out["left"] > rgb_item["right"]
            and abs(out["cy"] - rgb_item["cy"]) <= 45
        ]
        if not candidates:
            candidates = [
                out for out in output_items
                if id(out) not in used_output_ids
                and abs(out["cy"] - rgb_item["cy"]) <= 55
            ]
        if not candidates:
            continue

        best = min(candidates, key=lambda out: (abs(out["cy"] - rgb_item["cy"]), abs(out["left"] - rgb_item["right"])))
        used_output_ids.add(id(best))
        output = best["output"]
        rgb = rgb_item["rgb"]
        row = {
            "rgb_r": rgb[0],
            "rgb_g": rgb[1],
            "rgb_b": rgb[2],
            "target_mode": output["target_mode"],
            "target_l": output.get("target_l"),
            "target_a": output.get("target_a"),
            "target_b": output.get("target_b"),
            "target_note": output.get("target_note", ""),
        }
        rows.append(row)
    return rows


def _parse_color_table_ocr_lines(lines: list[str]) -> list[dict[str, Any]]:
    if not lines:
        return []

    rgb_rows: list[tuple[int, int, int]] = []
    outputs: list[dict[str, Any]] = []
    for line in lines:
        text = _clean_ocr_text(line)
        if not text:
            continue

        if re.search(r"\bRGB\b", text, re.IGNORECASE):
            rgb_match = re.search(r"RGB[:\s]*([0-9\s]+)", text, re.IGNORECASE)
            rgb = _split_rgb_digits(rgb_match.group(1) if rgb_match else text)
            if rgb:
                rgb_rows.append(rgb)
            continue

        output = _parse_output_text(text)
        if output:
            outputs.append(output)

    rows = []
    for rgb, output in zip(rgb_rows, outputs):
        rows.append({
            "rgb_r": rgb[0],
            "rgb_g": rgb[1],
            "rgb_b": rgb[2],
            "target_mode": output["target_mode"],
            "target_l": output.get("target_l"),
            "target_a": output.get("target_a"),
            "target_b": output.get("target_b"),
            "target_note": output.get("target_note", ""),
        })
    return rows


def _transcribe_color_table_text(image_bytes: bytes) -> str:
    prepared = _prepare_image_for_ocr(image_bytes)
    raw = call_ollama(
        prompt=_COLOR_TABLE_TRANSCRIBE_PROMPT,
        images=[prepared],
        model=_config["ocr_model"],
        temperature=0.0,
        max_tokens=768,
    )
    return _strip_think_tags(raw)


def _extract_color_table_vl_json(image_bytes: bytes) -> list[dict[str, Any]] | None:
    """
    當本地 OCR 不可用或不足時，改用較強的 VL 模型直接讀表。
    這裡特別放大圖片，針對小型截圖提升可讀性。
    """
    prepared = _prepare_image_for_ocr(image_bytes, scale=6)
    candidate_models = [
        "qwen2.5vl:3b",
        _config.get("ocr_model"),
    ]

    for model_name in candidate_models:
        if not model_name:
            continue
        try:
            raw = call_ollama(
                prompt=_COLOR_TABLE_JSON_PROMPT,
                images=[prepared],
                model=model_name,
                temperature=0.0,
                max_tokens=2048,
            )
            data = _extract_json_array(raw)
            if data:
                return data
        except Exception as e:
            logger.warning(f"[ai_service] VL color table JSON fallback 失敗(model={model_name})：{e}")
    return None


def _parse_color_table_ocr_text(raw_text: str) -> list[dict[str, Any]]:
    if not raw_text:
        return []

    rgb_pattern = re.compile(r"RGB[:\s]+(\d{1,3})\s+(\d{1,3})\s+(\d{1,3})", re.IGNORECASE)
    lab_pattern = re.compile(r"LAB[:\s]+(-?\d+(?:\.\d+)?)\s+(-?\d+(?:\.\d+)?)\s+(-?\d+(?:\.\d+)?)", re.IGNORECASE)
    ymck_pattern = re.compile(r"YMCKBHFm[:\s]+([0-9\s]+)", re.IGNORECASE)

    rgb_rows = []
    outputs = []
    for line in raw_text.splitlines():
        lab_match = lab_pattern.search(line)
        if lab_match:
            outputs.append({
                "target_mode": "LAB",
                "target_l": float(lab_match.group(1)),
                "target_a": float(lab_match.group(2)),
                "target_b": float(lab_match.group(3)),
                "target_note": "",
            })
            continue

        ymck_match = ymck_pattern.search(line)
        if ymck_match:
            numbers = re.findall(r"\d+", ymck_match.group(1))
            outputs.append({
                "target_mode": "YMCKBHFm",
                "target_note": " ".join(numbers),
            })
            continue

        rgb_match = rgb_pattern.search(line)
        if rgb_match:
            rgb_rows.append([int(rgb_match.group(i)) for i in range(1, 4)])

    rows = []
    for rgb, output in zip(rgb_rows, outputs):
        rows.append({
            "rgb_r": rgb[0],
            "rgb_g": rgb[1],
            "rgb_b": rgb[2],
            **output,
        })
    return rows


def classify_uploaded_image_local(image_bytes: bytes) -> dict[str, Any]:
    """以本地 OCR/CV 特徵做便宜的圖片分類，必要時再 fallback 到 VL。"""
    try:
        items = _run_local_ocr_items(image_bytes)
    except Exception as e:
        logger.warning(f"[ai_service] 本地圖片分類失敗：{e}")
        return {"image_kind": "unknown", "reason": "local_ocr_failed", "confidence": "low"}

    texts = [item["text"] for item in items]
    joined = " ".join(texts).lower()
    rgb_count = sum(1 for text in texts if "rgb" in text.lower())
    lab_count = sum(1 for text in texts if "lab" in text.lower())
    ymck_count = sum(1 for text in texts if "ymck" in text.lower())
    stock_hits = sum(1 for keyword in ("fabric", "布號", "缸號", "kg", "roll", "疋", "重量", "material") if keyword.lower() in joined)

    if rgb_count >= 4 and (lab_count + ymck_count) >= 4:
        return {
            "image_kind": "color_table",
            "reason": f"local_ocr_detected_rgb={rgb_count}, output={lab_count + ymck_count}",
            "confidence": "high",
        }
    if stock_hits >= 2:
        return {
            "image_kind": "stock_in_label",
            "reason": f"local_ocr_detected_stock_keywords={stock_hits}",
            "confidence": "medium",
        }
    if len(items) >= 8:
        return {
            "image_kind": "document",
            "reason": f"local_ocr_detected_text_lines={len(items)}",
            "confidence": "medium",
        }
    if len(items) <= 2:
        return {
            "image_kind": "sample_photo",
            "reason": "local_ocr_detected_very_little_text",
            "confidence": "medium",
        }
    return {"image_kind": "unknown", "reason": "local_ocr_not_conclusive", "confidence": "low"}


def extract_color_correction_rows(image_bytes: bytes, hint: str | None = None) -> list[dict[str, Any]] | None:
    """以 OCR-first + 規則 parser 抽取顏色校正表列，必要時再 fallback 到 VL JSON。"""
    try:
        ocr_items = _run_local_ocr_items(image_bytes)
        parsed_rows = _parse_color_table_ocr_items(ocr_items)
        if len(parsed_rows) >= 6:
            logger.info("[ai_service] 對色表 local OCR item parser 成功")
            return parsed_rows
        ocr_lines = [item["text"] for item in ocr_items]
        line_rows = _parse_color_table_ocr_lines(ocr_lines)
        if len(line_rows) > len(parsed_rows):
            parsed_rows = line_rows
        if len(parsed_rows) >= 6:
            logger.info("[ai_service] 對色表 local OCR line parser 成功")
            return parsed_rows
        logger.warning(f"[ai_service] local OCR parser 筆數不足，fallback 到 OCR/VL。lines={ocr_lines[:20]}")
    except Exception as e:
        logger.warning(f"[ai_service] local OCR parser 失敗，fallback 到 OCR/VL：{e}")

    try:
        raw_text = _transcribe_color_table_text(image_bytes)
        parsed_rows = _parse_color_table_ocr_text(raw_text)
        if len(parsed_rows) >= 5:
            logger.info("[ai_service] 對色表 OCR-first parser 成功")
            return parsed_rows
        logger.warning(f"[ai_service] OCR-first parser 筆數不足，fallback 到 VL JSON。raw={raw_text[:240]}")
    except Exception as e:
        logger.warning(f"[ai_service] OCR-first parser 失敗，fallback 到 VL JSON：{e}")

    data = None
    prompt = f"""
{hint or "請提取圖片中的顏色換色表格，包含輸入層(Input/RGB)與輸出層(Output/LAB/YMCK)的對應關係。"}
請分析圖片中的表格，並將每一列轉換為 JSON 格式。
輸出格式必須是純 JSON 列表，每一項包含：
- rgb_r, rgb_g, rgb_b (數字)
- target_mode (字串，如 'LAB', 'YMCKBHFm')
- target_l, target_a, target_b (如果是 LAB 模式時的數字)
- target_note (如果是非 LAB 模式時的數值字串或備註)

【重要範例】：若圖片有一行 `RGB 120 157 203` 對應 `62.71 -4.58 -25.46`，且此為 LAB 數值，必須輸出為：
[
  {{
    "rgb_r": 120, "rgb_g": 157, "rgb_b": 203,
    "target_mode": "LAB",
    "target_l": 62.71, "target_a": -4.58, "target_b": -25.46,
    "target_note": ""
  }}
]

只要回傳 JSON 列表即可，不要回傳其他多餘解釋。
"""
    try:
        raw = call_ollama(
            prompt=prompt,
            images=[image_bytes],
            model=_config["ocr_model"],
            temperature=0.0,
            max_tokens=2048,
        )
        data = _extract_json_array(raw)
    except Exception as e:
        logger.warning(f"[ai_service] color table JSON 提取失敗，改走保底路徑：{e}")
    if not data:
        data = _extract_color_table_vl_json(image_bytes)
        if not data:
            return None
        
    # 保底過濾：確保所有返回的行都有實質目標資料，避免回傳空白欄位導致 db update 被繞過
    valid_data = []
    for row in data:
        mode = str(row.get("target_mode") or "").strip().upper()
        if not mode and row.get("target_l") is not None:
             mode = "LAB"
             row["target_mode"] = "LAB"
        
        if "LAB" in mode:
             if row.get("target_l") is None or row.get("target_a") is None or row.get("target_b") is None:
                 continue
        else:
             note_val = (row.get("target_note") or "").strip().lower()
             if not mode and (not note_val or note_val in ("-", "none", "null", "n/a", "無", "empty")):
                 continue
        valid_data.append(row)
        
    return valid_data if valid_data else None


def classify_uploaded_image(image_bytes: bytes) -> dict[str, Any]:
    """判斷上傳圖片屬於樣品圖、對色表、入庫標籤或一般文件。"""
    local_result = classify_uploaded_image_local(image_bytes)
    if local_result.get("confidence") in {"high", "medium"} and local_result.get("image_kind") != "unknown":
        return local_result

    raw = call_ollama(
        prompt=_IMAGE_CLASSIFY_PROMPT,
        images=[image_bytes],
        model=_config["ocr_model"],
        temperature=0.0,
        max_tokens=256,
    )
    data = _extract_json_object(raw) or {"image_kind": "unknown", "reason": "無法解析模型回應", "confidence": "low"}
    data.setdefault("confidence", "low")
    return data


def suggest_sample_title_from_image(image_bytes: bytes) -> dict[str, Any]:
    """根據樣品圖片產生候選標題與關鍵字。"""
    raw = call_ollama(
        prompt=_SAMPLE_TITLE_PROMPT,
        images=[image_bytes],
        model=_config["ocr_model"],
        temperature=0.1,
        max_tokens=256,
    )
    data = _extract_json_object(raw) or {
        "suggested_title": "未命名樣品",
        "keywords": [],
        "confidence": "low",
        "needs_user_confirmation": True,
    }
    data.setdefault("confidence", "low")
    data.setdefault("needs_user_confirmation", data.get("confidence") != "high")
    return data


def extract_stock_in_data_from_image(image_bytes: bytes) -> dict[str, Any]:
    """從標籤或拍照圖片抽取可辨識的入庫欄位。"""
    raw = call_ollama(
        prompt=_STOCK_IN_EXTRACT_PROMPT,
        images=[image_bytes],
        model=_config["ocr_model"],
        temperature=0.0,
        max_tokens=1024,
    )
    data = _extract_json_object(raw)
    if not data:
        return {
            "fabric_code": None,
            "cylinder_no": None,
            "material": None,
            "note": None,
            "confidence": "low",
            "missing_fields": ["fabric_code", "cylinder_no", "rolls"],
            "rolls": [],
        }
    data.setdefault("rolls", [])
    data.setdefault("missing_fields", [])
    if not data.get("fabric_code"):
        data["missing_fields"].append("fabric_code")
    if not data.get("cylinder_no"):
        data["missing_fields"].append("cylinder_no")
    if not data.get("rolls"):
        data["missing_fields"].append("rolls")
    data["missing_fields"] = sorted(set(data["missing_fields"]))
    data.setdefault("confidence", "high" if not data["missing_fields"] else "medium")
    return data


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
            model=_config["ocr_model"],
            temperature=0.0,
            max_tokens=512,
        )
        data = _extract_json_object(raw)
        if data:
            return data
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
                "sentence-transformers 未安裝，請執行：pip install sentence-transformers "
                f"(python={sys.executable})"
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


def upsert_image_vector(
    *,
    db_path: str,
    image_path: str,
    image_bytes: bytes,
    entity_type: str | None = None,
    entity_id: int | None = None,
    ocr_data: dict[str, Any] | None = None,
) -> int | None:
    """
    寫入或更新 image_vectors，供圖像搜尋重用 embedding。
    以 (entity_type, entity_id, image_path) 為優先匹配條件。
    """
    embedding = compute_image_embedding(image_bytes)
    embedding_blob = embedding.tobytes()
    embedding_dim = int(embedding.shape[0])
    ocr_json = json.dumps(ocr_data, ensure_ascii=False) if ocr_data is not None else None

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        existing = None
        if entity_type and entity_id is not None:
            existing = conn.execute(
                "SELECT id FROM image_vectors WHERE entity_type = ? AND entity_id = ? LIMIT 1",
                (entity_type, entity_id),
            ).fetchone()
        if not existing and image_path:
            existing = conn.execute(
                "SELECT id FROM image_vectors WHERE image_path = ? LIMIT 1",
                (image_path,),
            ).fetchone()

        if existing:
            conn.execute(
                """UPDATE image_vectors
                   SET image_path = ?, entity_type = ?, entity_id = ?, ocr_data = ?, embedding = ?, embedding_dim = ?
                   WHERE id = ?""",
                (image_path, entity_type, entity_id, ocr_json, embedding_blob, embedding_dim, existing["id"]),
            )
            conn.commit()
            return int(existing["id"])

        cur = conn.execute(
            """INSERT INTO image_vectors
               (image_path, entity_type, entity_id, ocr_data, embedding, embedding_dim)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (image_path, entity_type, entity_id, ocr_json, embedding_blob, embedding_dim),
        )
        conn.commit()
        return int(cur.lastrowid)
    finally:
        conn.close()


def search_similar_sample_images(
    *,
    image_bytes: bytes,
    db_path: str,
    upload_dir: str,
    top_k: int = 5,
) -> list[dict[str, Any]]:
    """
    先使用 image_vectors 中的 sample 向量做查詢；若快取缺失，回填後再查。
    """
    import os

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            """
            SELECT s.id, s.sample_no, s.title, s.fabric_no, s.preview_path, iv.id AS vector_id
            FROM samples s
            LEFT JOIN image_vectors iv
              ON iv.entity_type = 'sample' AND iv.entity_id = s.id
            WHERE s.preview_path IS NOT NULL AND s.preview_path != ''
            """
        ).fetchall()
    finally:
        conn.close()

    if not rows:
        return []

    missing = [row for row in rows if row["vector_id"] is None]
    for row in missing:
        img_path = os.path.join(upload_dir, row["preview_path"])
        if not os.path.exists(img_path):
            continue
        try:
            with open(img_path, "rb") as f:
                sample_bytes = f.read()
            upsert_image_vector(
                db_path=db_path,
                image_path=row["preview_path"],
                image_bytes=sample_bytes,
                entity_type="sample",
                entity_id=int(row["id"]),
            )
        except Exception as e:
            logger.warning(f"[ai_service] 無法為 sample {row['id']} 建立圖像向量：{e}")

    query_embedding = compute_image_embedding(image_bytes)
    similar = search_similar_images(query_embedding=query_embedding, db_path=db_path, top_k=max(top_k * 3, 10))
    sample_scores = {
        int(item["entity_id"]): item["score"]
        for item in similar
        if item.get("entity_type") == "sample" and item.get("entity_id") is not None
    }
    if not sample_scores:
        return []

    id_order = sorted(sample_scores.keys(), key=lambda sid: sample_scores[sid], reverse=True)
    meta_by_id = {int(row["id"]): row for row in rows}
    results = []
    for sample_id in id_order:
        row = meta_by_id.get(sample_id)
        if not row:
            continue
        results.append({
            "sample_id": sample_id,
            "sample_no": row["sample_no"],
            "title": row["title"],
            "fabric_no": row["fabric_no"],
            "score": sample_scores[sample_id],
        })
        if len(results) >= top_k:
            break
    return results
