"""
intent_dispatcher.py
====================
意圖判斷與登記參數萃取。

流程：
  1. LLM 分類意圖：query | stock_in | production_log | unknown
  2. query      → sql_agent.ask()
  3. stock_in   → 萃取 fabric_code, cylinder_no, rolls[]
  4. production_log → 萃取 task_id/order_no, roll_id/roll_no, length_m
  5. 缺必要欄位 → 以越南語反問（禁止猜測）
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# System Prompt：意圖分類（禁止猜測策略）
# ---------------------------------------------------------------------------
INTENT_CLASSIFY_SYSTEM = """
你是一個工廠管理系統的 AI 助理，負責理解操作員的輸入並分類意圖。

可能的意圖：
- "query"         : 用戶在查詢資訊（庫存、訂單、生產記錄等）
- "stock_in"      : 用戶想要登記布料入庫、新增布料資料、或註冊新布號
- "production_log": 用戶想要登記一筆生產記錄（消耗布匹）
- "unknown"       : 無法判斷或一般對話

回覆格式為純 JSON（不加 markdown 包裝），例如：
{"intent": "stock_in"}
或
{"intent": "query"}

只回覆 JSON，不要任何解釋。
"""

# ---------------------------------------------------------------------------
# System Prompt：入庫參數萃取（嚴格禁止猜測）
# ---------------------------------------------------------------------------
STOCK_IN_EXTRACT_SYSTEM = """
你是工廠管理系統的 AI 助理。任務：協助用戶提取所需的入庫資訊。

必要欄位：
- fabric_code  : 布料代碼（例如 F-001）
- cylinder_no  : 缸號（例如 V-001）
- rolls        : 捲列表，包含捲號 (roll_no) 與重量 (weight_kg)
- note         : 額外資訊或備註（如 NYLON, 黑色, 或用戶提到的特殊要求）

⚠️ 重要規則：
1. **處理部分資訊**：若用戶只給了布號（如 95278），且明確說其他資訊之後再補或不提供，請設 status="need_info" 並在 question_zh 中禮貌地告訴用戶：「已記錄布號 {code}。雖然您目前不需要輸入缸號，但系統最終存檔仍需此資訊。我已先為您開啟登記介面。」
2. **靈活應對**：若用戶文字中包含「不提供」、「不需要」、「之後補」等詞彙，不要只是報錯，要能理解並給予正面回應。
3. **禁止瞎猜**：如果完全沒有布號，絕對禁止自行發明。

回覆格式 (純 JSON)：
{
  "status": "ready" | "need_info",
  "params": { "fabric_code": "...", "cylinder_no": "...", "rolls": [...], "note": "..." },
  "question_zh": "您的回覆內容 (繁體中文)",
  "question_vi": "Nội dung phản hồi (Tiếng Việt)"
}
"""

# ---------------------------------------------------------------------------
# System Prompt：生產登記參數萃取（嚴格禁止猜測）
# ---------------------------------------------------------------------------
PRODUCTION_LOG_EXTRACT_SYSTEM = """
你是工廠管理系統的資料萃取助理。任務：從用戶輸入中萃取生產登記所需的欄位。

必要欄位（**至少**需要其中一個組合）：
- 任務識別：task_id（生產任務 ID）或 order_no（訂單號）
- 捲料識別：roll_id（捲 ID）或 roll_no（捲號）
- length_m  : 消耗長度（公尺，數字）
- note      : 備註資訊

⚠️ 極重要規則（必須嚴格遵守）：
1. 發現任何必要欄位缺失，必須回傳 status="need_info" 並詢問用戶補充。
2. 你擁有權限協助登記生產紀錄，但必須先獲得必要參數。
3. Never hallucinate. Never fill in values not explicitly stated by the user.

回覆格式（純 JSON，無 markdown）：

情況 A — 資料完整：
{
  "status": "ready",
  "params": {
    "task_id": null,
    "order_no": "...",
    "roll_id": null,
    "roll_no": "...",
    "length_m": 0.0,
    "note": "..."
  }
}

情況 B — 資料不足：
{
  "status": "need_info",
  "missing": ["roll_no", "length_m"],
  "question_zh": "請提供捲號 (roll_no) 以及消耗長度 (length_m)。",
  "question_vi": "Vui lòng cung cấp số cuộn vải (roll_no) và chiều dài sử dụng (length_m)."
}
"""


# ---------------------------------------------------------------------------
# 輔助：解析 LLM JSON 輸出
# ---------------------------------------------------------------------------
_JSON_BLOCK = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.DOTALL | re.IGNORECASE)


def _is_color_correction_apply_request(
    text: str,
    image_bytes: bytes | None,
    current_entity: dict[str, Any] | None = None,
) -> bool:
    if not image_bytes:
        return False
    from .image_router import route_image_request

    route = route_image_request(text, image_bytes)
    if route.get("intent") == "color_correction_apply":
        return True

    current_entity = current_entity or {}
    lowered = (text or "").lower()
    apply_words = (
        "填入", "填進", "填寫", "填上", "寫入", "套用", "同步", "登記",
        "補充", "補上", "補齊", "更新", "覆蓋", "改成",
    )
    target_words = (
        "校色", "校色紀錄", "對色", "對色紀錄", "數色", "數色紀錄",
        "目標色", "目標顏色", "目標值", "lab值", "l*a*b",
    )
    search_words = ("搜尋", "搜索", "查找", "找相似", "叫什麼", "名稱", "是哪個")
    if current_entity.get("type") == "sample":
        has_apply = any(word in lowered for word in apply_words)
        has_target = any(word in lowered for word in target_words)
        if route.get("image_kind") == "color_table" and (has_apply or has_target):
            return True
        if has_apply:
            if not any(word in lowered for word in search_words):
                return True
    return False


def _handle_color_correction_apply(
    text: str,
    lang: str,
    image_bytes: bytes,
    current_entity: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    from . import ai_service
    from .image_router import extract_sample_query_candidates
    from ..services import sample_repo

    sample_query = ""
    resolved = None
    current_entity = current_entity or {}
    if current_entity.get("type") == "sample":
        current_sample_id = current_entity.get("id")
        if current_sample_id:
            direct_sample = sample_repo.get_sample(current_sample_id)
            if direct_sample:
                resolved = {
                    "status": "resolved",
                    "id": int(direct_sample["id"]),
                    "sample_no": direct_sample["sample_no"] if "sample_no" in direct_sample.keys() else None,
                    "title": (direct_sample["title"] if "title" in direct_sample.keys() else "") or "",
                }
        if not resolved:
            sample_query = str(
                current_entity.get("sample_no")
                or current_entity.get("title")
                or current_entity.get("id")
                or ""
            ).strip()
    else:
        merged_candidates = []
        seen_ids = set()
        for query in extract_sample_query_candidates(text):
            matches = sample_repo.find_sample_candidates(query, limit=5, min_score=0.55)
            for item in matches:
                if item["id"] in seen_ids:
                    continue
                merged_candidates.append(item)
                seen_ids.add(item["id"])
            if matches and matches[0]["score"] >= 0.92:
                sample_query = matches[0]["sample_no"] or matches[0]["title"]
                break

        merged_candidates.sort(key=lambda item: item.get("score", 0), reverse=True)
        if not sample_query and len(merged_candidates) == 1:
            sample_query = merged_candidates[0]["sample_no"] or merged_candidates[0]["title"]
        elif not sample_query and len(merged_candidates) > 1:
            options = "、".join(f"{item['sample_no']} ({item['title']})" for item in merged_candidates[:5])
            reply = (
                f"找到多個可能的樣品，請先確認要寫入哪一個：{options}"
                if lang == "zh"
                else f"Tìm thấy nhiều mẫu khả dĩ, vui lòng xác nhận mẫu cần ghi: {options}"
            )
            return {"status": "need_info", "intent": "sample", "reply": reply}

    if not resolved and not sample_query:
        reply = (
            "請先指定樣品名稱或打開對應的 sample 詳情頁，再上傳校色圖。"
            if lang == "zh"
            else "Vui lòng chỉ định tên mẫu hoặc mở trang chi tiết sample trước khi tải ảnh bảng màu."
        )
        return {"status": "need_info", "intent": "sample", "reply": reply}

    if not resolved:
        try:
            resolved = sample_repo.resolve_sample_for_ai(sample_query)
        except Exception as e:
            return {"status": "error", "intent": "sample", "reply": str(e)}

    if resolved.get("status") == "ambiguous":
        options = "、".join(f"{item['sample_no']} ({item['title']})" for item in resolved["matches"][:5])
        reply = (
            f"找到多個符合的樣品，請確認要寫入哪一個：{options}"
            if lang == "zh"
            else f"Tìm thấy nhiều mẫu phù hợp, vui lòng xác nhận mẫu cần ghi: {options}"
        )
        return {"status": "need_info", "intent": "sample", "reply": reply}

    rows = ai_service.extract_color_correction_rows(image_bytes)
    if not rows:
        reply = (
            "我無法從圖片中穩定提取校色表，請換一張更清楚的圖片。"
            if lang == "zh"
            else "Tôi không thể trích xuất bảng chỉnh màu ổn định từ ảnh này, vui lòng dùng ảnh rõ hơn."
        )
        return {"status": "error", "intent": "sample", "reply": reply}

    sample_repo.replace_color_corrections(resolved["id"], rows)
    reply = (
        f"已將樣品「{resolved['title']}」的校色紀錄覆蓋為圖片內容，共 {len(rows)} 筆。"
        if lang == "zh"
        else f"Đã ghi đè bảng chỉnh màu của mẫu \"{resolved['title']}\" theo nội dung ảnh, tổng cộng {len(rows)} dòng."
    )
    return {
        "status": "ok",
        "intent": "sample",
        "reply": reply,
        "params": {
            "sample_id": resolved["id"],
            "sample_no": resolved.get("sample_no"),
            "title": resolved["title"],
            "correction_count": len(rows),
            "corrections": rows,
        },
    }


def _manifest_fields_by_name(field_manifest: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    manifest = field_manifest or {}
    fields = manifest.get("fields") or []
    output: dict[str, dict[str, Any]] = {}
    for field in fields:
        if not isinstance(field, dict):
            continue
        name = str(field.get("name") or "").strip()
        if name:
            output[name] = field
    return output


def _field_alias_candidates(field: dict[str, Any]) -> list[str]:
    if not isinstance(field, dict):
        return []
    values = []
    for candidate in [field.get("name"), field.get("label"), field.get("db_field")]:
        if candidate:
            values.append(str(candidate).strip())
    for alias in field.get("aliases") or []:
        if alias:
            values.append(str(alias).strip())

    seen = set()
    ordered: list[str] = []
    for value in sorted(values, key=len, reverse=True):
        token = value.casefold()
        if token and token not in seen:
            seen.add(token)
            ordered.append(value)
    return ordered


def _manifest_group_row_field_names(field_manifest: dict[str, Any] | None) -> set[str]:
    manifest = field_manifest or {}
    groups = manifest.get("groups") or []
    output: set[str] = set()
    for group in groups:
        if not isinstance(group, dict):
            continue
        for field in (group.get("row_fields") or []):
            if not isinstance(field, dict):
                continue
            name = str(field.get("name") or "").strip()
            if name:
                output.add(name)
    return output


def _is_sample_form_context(
    current_entity: dict[str, Any] | None,
    field_manifest: dict[str, Any] | None,
) -> bool:
    entity = current_entity or {}
    manifest = field_manifest or {}
    return entity.get("type") == "sample" and str(manifest.get("page_type") or "").strip().lower() == "sample_form"


def _is_order_form_context(field_manifest: dict[str, Any] | None) -> bool:
    manifest = field_manifest or {}
    return str(manifest.get("page_type") or "").strip().lower() == "order_form"


def _is_stock_in_form_context(field_manifest: dict[str, Any] | None) -> bool:
    manifest = field_manifest or {}
    return str(manifest.get("page_type") or "").strip().lower() == "stock_in_form"


def _parse_printing_filename_fields(raw_text: str) -> dict[str, Any]:
    text = str(raw_text or "").strip()
    if not text:
        return {}

    # 優先抓出像 9528_ACID_360x1200_260317 這種檔名片段
    candidates = re.findall(r"[A-Za-z0-9]+(?:[_-][A-Za-z0-9]+){2,}", text)
    if not candidates:
        compact = re.sub(r"\s+", "", text)
        candidates = re.findall(r"[A-Za-z0-9]+(?:[_-][A-Za-z0-9]+){2,}", compact)
    if not candidates:
        tokens = [token.strip() for token in re.split(r"[\s|]+", text) if token.strip()]
        if len(tokens) >= 4:
            numeric_prefix = next((token for token in tokens if re.fullmatch(r"\d{3,5}", token)), "")
            alpha_token = next((token for token in tokens if re.fullmatch(r"[A-Za-z]{2,12}", token)), "")
            size_token = next((token for token in tokens if re.fullmatch(r"\d{2,5}x\d{2,5}", token, flags=re.IGNORECASE)), "")
            date_token = next((token for token in tokens if re.fullmatch(r"\d{6,8}", token)), "")
            if numeric_prefix and alpha_token and size_token and date_token:
                candidates = [f"{numeric_prefix}_{alpha_token}_{size_token}_{date_token}"]
    if not candidates:
        return {}

    best = max(candidates, key=len).strip("._-")
    parts = [part for part in re.split(r"[_-]+", best) if part]
    fields: dict[str, Any] = {
        "printing_file_name": best,
    }
    if len(parts) >= 2 and re.fullmatch(r"[A-Za-z]+", parts[1]):
        fields["printing_environment"] = parts[1].upper()
    if parts and re.fullmatch(r"\d{3,}", parts[0]):
        fields["fabric_no"] = parts[0]
    return fields


def _normalize_ocr_date(raw_text: str) -> str | None:
    text = str(raw_text or "").strip()
    if not text:
        return None
    match = re.search(r"(\d{2,4})[/-](\d{1,2})[/-](\d{1,2})", text)
    if not match:
        return None
    year = int(match.group(1))
    month = int(match.group(2))
    day = int(match.group(3))
    if year < 100:
        year += 2000
    if not (1 <= month <= 12 and 1 <= day <= 31):
        return None
    return f"{year:04d}-{month:02d}-{day:02d}"


def _extract_labeled_value(raw_text: str, labels: list[str]) -> str:
    text = str(raw_text or "")
    for label in labels:
        pattern = rf"{re.escape(label)}\s*[:：]\s*([^\n|]+)"
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            return _clean_assignment_value(match.group(1))
    return ""


def _parse_fabric_code_from_text(raw_text: str) -> str:
    text = str(raw_text or "")
    patterns = [
        r"\bJN[-\s]?(\d{4,5})\b",
        r"\b(\d{4,5})\b",
    ]
    for pattern in patterns:
        matches = re.findall(pattern, text, flags=re.IGNORECASE)
        for value in matches:
            code = str(value).strip()
            if len(code) >= 4:
                return code
    return ""


def _resolve_sample_match_from_text(raw_text: str, fabric_no: str = "") -> dict[str, Any] | None:
    from ..services import sample_repo

    text = str(raw_text or "")
    normalized_fabric = str(fabric_no or "").strip()
    candidate_entries: list[tuple[str, str, float]] = []

    tp_match = re.search(r"(TP\d{4,8})", text, flags=re.IGNORECASE)
    if tp_match:
        tp_code = tp_match.group(1).upper()
        candidate_entries.append((tp_code, "tp_code", 1.0))

    for line in text.splitlines():
        cleaned = str(line or "").strip()
        if not cleaned:
            continue
        if re.search(r"TP\d{4,8}", cleaned, flags=re.IGNORECASE):
            candidate_entries.append((cleaned, "ocr_line", 0.92))
            title_match = re.search(r"([\u4e00-\u9fff]{2,12})\s*TP\d{4,8}", cleaned)
            if title_match:
                candidate_entries.append((title_match.group(1), "zh_title", 0.82))
            english_match = re.search(r"TP\d{4,8}\s+([A-Za-z0-9][A-Za-z0-9\s_-]{2,40})", cleaned, flags=re.IGNORECASE)
            if english_match:
                candidate_entries.append((english_match.group(1).strip(), "en_title", 0.74))

    seen_queries: set[str] = set()
    best_match: dict[str, Any] | None = None
    best_rank = (-1.0, -1.0)
    for candidate, source, priority in candidate_entries:
        token = candidate.casefold()
        if not token or token in seen_queries:
            continue
        seen_queries.add(token)
        try:
            resolved = sample_repo.resolve_sample_for_ai(candidate, min_score=0.35)
        except Exception:
            continue

        chosen: dict[str, Any] | None = None
        if resolved.get("status") == "resolved":
            chosen = dict(resolved)
        elif resolved.get("status") == "ambiguous":
            matches = resolved.get("matches") or []
            if matches:
                chosen = {"status": "ambiguous_pick", **matches[0], "matches": matches}
        if not chosen:
            continue

        if normalized_fabric and str(chosen.get("fabric_no") or "").strip() not in {"", normalized_fabric}:
            continue

        score = float(chosen.get("score") or 0.0)
        rank = (priority, score)
        if rank > best_rank:
            best_rank = rank
            best_match = {
                "id": int(chosen["id"]),
                "sample_no": chosen.get("sample_no"),
                "title": chosen.get("title"),
                "fabric_no": chosen.get("fabric_no"),
                "score": score,
                "query": candidate,
                "source": source,
                "status": chosen.get("status"),
            }
    return best_match


def _resolve_sample_id_from_text(raw_text: str, fabric_no: str = "") -> int | None:
    match = _resolve_sample_match_from_text(raw_text, fabric_no=fabric_no)
    return int(match["id"]) if match else None


def _summarize_order_note(raw_text: str) -> str:
    parts = []
    mapping = [
        ("卡號", ["卡号", "卡號"]),
        ("客戶", ["客户", "客戶"]),
        ("缸號", ["缸号", "缸號"]),
        ("品名", ["品名"]),
        ("染整單號", ["染整單号", "染整單號"]),
    ]
    for label, aliases in mapping:
        value = _extract_labeled_value(raw_text, aliases)
        if value:
            parts.append(f"{label}: {value}")
    return " | ".join(parts[:5])


def _parse_order_qty_from_text(raw_text: str, sample_match: dict[str, Any] | None = None) -> float | int | None:
    lines = [str(line or "").strip() for line in str(raw_text or "").splitlines()]
    if not lines:
        return None

    target_indexes: list[int] = []
    if sample_match:
        sample_no = str(sample_match.get("sample_no") or "")
        title = str(sample_match.get("title") or "")
        for idx, line in enumerate(lines):
            lowered = line.lower()
            if sample_no and sample_no.split()[0].lower() in lowered:
                target_indexes.append(idx)
            if title and title[:2] and title[:2] in line:
                target_indexes.append(idx)

    for idx, line in enumerate(lines):
        if re.search(r"成品量.*yd", line, flags=re.IGNORECASE):
            target_indexes.append(idx)

    checked: set[int] = set()
    for anchor in target_indexes:
        if anchor in checked:
            continue
        checked.add(anchor)
        window = lines[max(0, anchor - 1): min(len(lines), anchor + 6)]
        numeric_tokens: list[float | int] = []
        for line in window:
            value = _numeric_text_value(line)
            if value is None:
                continue
            numeric_tokens.append(value)
        integers = [value for value in numeric_tokens if isinstance(value, int) and 10 <= value <= 5000]
        if integers:
            return integers[-1]

    return None


def _parse_order_document_fields(raw_text: str) -> dict[str, Any]:
    text = str(raw_text or "")
    order_no = (
        _extract_labeled_value(text, ["打单编号", "打單編號", "訂單編號"])
        or _extract_labeled_value(text, ["訂單", "订单", "言量", "計劃訂單"])
    )
    received_date = (
        _normalize_ocr_date(_extract_labeled_value(text, ["初單日期", "訂單日期"]))
        or _normalize_ocr_date(_extract_labeled_value(text, ["列印日"]))
    )
    due_date = _normalize_ocr_date(_extract_labeled_value(text, ["交货日期", "交貨日期"]))
    note = _summarize_order_note(text)
    fabric_no = _parse_fabric_code_from_text(text)
    sample_match = _resolve_sample_match_from_text(text, fabric_no=fabric_no)
    sample_id = int(sample_match["id"]) if sample_match else None
    qty_value = _parse_order_qty_from_text(text, sample_match=sample_match)
    warnings: list[str] = []
    item_note_parts = []
    title_value = _extract_labeled_value(text, ["色名", "樣品", "品名"])
    if title_value:
        item_note_parts.append(title_value)
    if note:
        item_note_parts.append(note)
    if sample_match:
        item_note_parts.append(f"樣品: {sample_match.get('sample_no') or sample_match.get('title')}")
    else:
        warnings.append("無法穩定匹配樣品，sample_id 未自動帶入。")

    if qty_value is not None:
        item_note_parts.append(f"成品量Yd: {qty_value}")
    elif not re.search(r"(數量|qty|成品量|胚量)", text, flags=re.IGNORECASE):
        warnings.append("未找到可直接映射到 order item qty 的穩定欄位。")
    else:
        warnings.append("此訂單圖含多個數量欄位，qty 仍需人工確認後再填。")

    fields = {}
    if order_no:
        fields["order_no"] = order_no
    if received_date:
        fields["received_date"] = received_date
    if due_date:
        fields["due_date"] = due_date
    if note:
        fields["note"] = note

    item: dict[str, Any] = {}
    if fabric_no:
        item["fabric_no"] = fabric_no
    if sample_id:
        item["sample_id"] = sample_id
    if qty_value is not None:
        item["qty"] = qty_value
    if item_note_parts:
        item["note"] = " | ".join(item_note_parts[:3])

    return {
        "fields": fields,
        "order_items": [item] if item else [],
        "sample_match": sample_match,
        "warnings": warnings,
    }


def _numeric_text_value(text: str) -> float | int | None:
    raw = str(text or "").strip()
    if not raw:
        return None
    if re.fullmatch(r"\d+\.\d+", raw):
        return float(raw)
    if re.fullmatch(r"\d+", raw):
        return int(raw)
    return None


def _parse_stock_in_rows_from_ocr_items(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not items:
        return []

    numeric_items = []
    for item in items:
        text = str(item.get("text") or "").strip()
        value = _numeric_text_value(text)
        if value is None:
            continue
        numeric_items.append({**item, "numeric_value": value})

    if not numeric_items:
        return []

    numeric_items.sort(key=lambda item: (float(item.get("cy") or 0), float(item.get("cx") or 0)))
    row_groups: list[list[dict[str, Any]]] = []
    tolerance = 85.0
    for item in numeric_items:
        if not row_groups:
            row_groups.append([item])
            continue
        last_group = row_groups[-1]
        avg_cy = sum(float(x.get("cy") or 0) for x in last_group) / len(last_group)
        if abs(float(item.get("cy") or 0) - avg_cy) <= tolerance:
            last_group.append(item)
        else:
            row_groups.append([item])

    rows_with_pos: list[dict[str, Any]] = []
    for group in row_groups:
        ordered = sorted(group, key=lambda item: float(item.get("cx") or 0))
        integers = [item for item in ordered if isinstance(item["numeric_value"], int)]
        decimals = [item for item in ordered if isinstance(item["numeric_value"], float)]
        if len(integers) < 2 or len(decimals) < 1:
            continue

        row_index_candidates = [
            int(item["numeric_value"])
            for item in integers
            if 1 <= int(item["numeric_value"]) <= 20
        ]
        roll_candidates = sorted(
            {
                int(item["numeric_value"])
                for item in integers
                if 20 <= int(item["numeric_value"]) <= 999
            },
            reverse=True,
        )
        weight_candidates = sorted(
            [
                round(float(item["numeric_value"]), 1)
                for item in decimals
                if 5.0 <= float(item["numeric_value"]) <= 40.0
            ]
        )
        if not roll_candidates or not weight_candidates:
            continue

        row_index = min(row_index_candidates) if row_index_candidates else None
        roll_no = str(roll_candidates[0])
        weight_kg = weight_candidates[0]
        length_candidates = sorted(
            {
                int(item["numeric_value"])
                for item in integers
                if 20 <= int(item["numeric_value"]) <= 999
                and str(int(item["numeric_value"])) != roll_no
            },
            reverse=True,
        )
        length_m = float(length_candidates[0]) if length_candidates else None

        rows_with_pos.append({
            "row_index": row_index,
            "roll_no": roll_no,
            "weight_kg": weight_kg,
            "length_m": length_m,
            "remark": "",
            "_cy": sum(float(item.get("cy") or 0) for item in group) / len(group),
        })

    known_indexes = [int(row["row_index"]) for row in rows_with_pos if row["row_index"] is not None]
    if rows_with_pos and known_indexes:
        expected = set(range(1, len(rows_with_pos) + 1))
        missing_indexes = sorted(expected - set(known_indexes))
        if len(missing_indexes) == 1:
            for row in sorted(rows_with_pos, key=lambda entry: entry["_cy"]):
                if row["row_index"] is None:
                    row["row_index"] = missing_indexes[0]
                    break

    rows_with_pos.sort(key=lambda row: (row["row_index"] is None, row["row_index"] or 0, row["_cy"]))
    rows: list[dict[str, Any]] = []
    for row in rows_with_pos:
        row.pop("_cy", None)
        rows.append(row)
    return rows


def _parse_stock_in_document_fields(image_bytes: bytes, raw_text: str) -> dict[str, Any]:
    from . import ai_service
    from ..services import fabric_repo

    fabric_code = _parse_fabric_code_from_text(raw_text)
    cylinder_no = _extract_labeled_value(raw_text, ["缸号", "缸號"])
    note = _summarize_order_note(raw_text)
    fabric = fabric_repo.get_fabric_by_code(fabric_code) if fabric_code else None
    fields: dict[str, Any] = {
        "cylinder_mode": "new",
    }
    if fabric:
        fields["fabric_id"] = fabric["id"]
    if cylinder_no:
        fields["cylinder_no"] = cylinder_no

    items = ai_service._run_local_ocr_items(image_bytes)
    rows = _parse_stock_in_rows_from_ocr_items(items)
    if note and rows:
        for row in rows:
            row["remark"] = note

    return {
        "fields": fields,
        "stock_in_rows": rows,
    }


def _handle_sample_form_text_actions(
    text: str,
    lang: str,
    current_entity: dict[str, Any] | None = None,
    field_manifest: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    if not _is_sample_form_context(current_entity, field_manifest):
        return None

    raw_text = str(text or "")
    if not raw_text:
        return None

    delete_match = re.search(r"(刪除|删除|清空|移除|重設|重置|reset|clear)", raw_text, flags=re.IGNORECASE)
    color_match = re.search(r"(校色|對色|对色|數色|数色|顏色|颜色|色表|目標色|目标色)", raw_text, flags=re.IGNORECASE)
    if delete_match and color_match:
        reply = (
            "已清空目前樣品表單中的校色草稿，請確認後再送出，或重新上傳圖片填入。"
            if lang == "zh"
            else "Đã xóa nháp chỉnh màu trên biểu mẫu mẫu hiện tại. Vui lòng kiểm tra trước khi lưu hoặc tải ảnh lên lại."
        )
        return {
            "status": "ready",
            "intent": "sample_form",
            "reply": reply,
            "params": {
                "sample_id": (current_entity or {}).get("id"),
                "sample_fields": {},
                "color_corrections": [],
                "clear_color_corrections": True,
            },
        }
    return None


def _clean_assignment_value(raw_value: str) -> str:
    value = str(raw_value or "").strip().strip("：: =")
    value = value.strip("「」『』\"'")
    value = re.sub(r"(嗎|可以嗎|好嗎|謝謝|谢谢|一下)$", "", value).strip()
    return value


def _extract_form_fields_from_text(
    text: str,
    field_manifest: dict[str, Any] | None,
) -> dict[str, Any]:
    manifest = field_manifest or {}
    fields_by_name = _manifest_fields_by_name(manifest)
    extracted: dict[str, Any] = {}

    # 先吃 deterministic 檔名格式
    for key, value in _parse_printing_filename_fields(text).items():
        if key in fields_by_name and value not in (None, ""):
            extracted[key] = value

    assign_verbs = (
        "改成", "改為", "設成", "設為", "設定成", "設定為",
        "填入", "填進", "填寫", "填上", "填成",
        "寫入", "更新為", "補上", "補成", "補充為",
        "是", "為", "=",
    )

    for name, field in fields_by_name.items():
        if name in extracted:
            continue
        aliases = _field_alias_candidates(field)
        for alias in aliases:
            alias_pat = re.escape(alias)
            verb_pat = "|".join(re.escape(verb) for verb in assign_verbs)
            patterns = [
                rf"(?:把|將)?\s*{alias_pat}\s*(?:幫我|請)?\s*(?:{verb_pat})\s*(?P<value>[^\n，。,；;]+)",
                rf"(?:把|將)?\s*{alias_pat}\s*[:：]\s*(?P<value>[^\n，。,；;]+)",
            ]
            matched_value = ""
            for pattern in patterns:
                match = re.search(pattern, text, flags=re.IGNORECASE)
                if match:
                    matched_value = _clean_assignment_value(match.group("value"))
                    if matched_value:
                        extracted[name] = matched_value
                        break
            if name in extracted:
                break

    return extracted


def _handle_current_form_fill_from_text(
    text: str,
    lang: str,
    field_manifest: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    manifest = field_manifest or {}
    page_type = str(manifest.get("page_type") or "").strip()
    if not text or not (manifest.get("fields") or []) or not page_type:
        return None

    extracted = _extract_form_fields_from_text(text, manifest)
    if not extracted:
        return None

    labels = []
    for name, field in _manifest_fields_by_name(manifest).items():
        if name in extracted:
            labels.append(str(field.get("label") or name))

    reply = (
        f"已根據目前頁面的欄位定義整理出 {len(extracted)} 個可填寫欄位：{'、'.join(labels)}。請確認後送出。"
        if lang == "zh"
        else f"Đã nhận diện {len(extracted)} trường có thể điền theo biểu mẫu hiện tại: {', '.join(labels)}. Vui lòng kiểm tra trước khi lưu."
    )
    return {
        "status": "ready",
        "intent": "form_fill",
        "reply": reply,
        "params": {
            "fields": extracted,
            "page_type": page_type,
        },
    }


def _handle_sample_form_fill_from_image(
    text: str,
    lang: str,
    image_bytes: bytes | None,
    current_entity: dict[str, Any] | None = None,
    field_manifest: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    if not image_bytes or not _is_sample_form_context(current_entity, field_manifest):
        return None

    from . import ai_service
    from .image_router import route_image_request

    manifest = field_manifest or {}
    current = current_entity or {}
    field_names = _manifest_fields_by_name(manifest)
    row_field_names = _manifest_group_row_field_names(manifest)
    route = route_image_request(text, image_bytes)

    # 1. 數色圖優先回表單草稿，不直接寫 DB
    if route.get("image_kind") == "color_table" and any(name in row_field_names for name in ("cc_l", "cc_a", "cc_b2")):
        rows = ai_service.extract_color_correction_rows(image_bytes)
        if rows:
            reply = (
                f"已從圖片整理出 {len(rows)} 筆校色資料，並準備填入目前樣品表單。請確認後送出。"
                if lang == "zh"
                else f"Đã trích xuất {len(rows)} dòng chỉnh màu và điền vào biểu mẫu mẫu hiện tại. Vui lòng kiểm tra trước khi lưu."
            )
            return {
                "status": "ready",
                "intent": "sample_form",
                "reply": reply,
                "params": {
                    "sample_id": current.get("id"),
                    "sample_fields": {},
                    "color_corrections": rows,
                },
            }

    # 2. 小圖/檔名圖優先做 deterministic parser
    local_text = ai_service.extract_text_from_image_local(image_bytes)
    parsed_fields = _parse_printing_filename_fields(local_text)
    if parsed_fields:
        allowed_fields = {
            key: value for key, value in parsed_fields.items()
            if key in field_names
        }
        if allowed_fields:
            reply = (
                "已從圖片文字整理出可填寫欄位，並填入目前樣品表單。請確認後送出。"
                if lang == "zh"
                else "Đã trích xuất các trường có thể điền từ ảnh và điền vào biểu mẫu mẫu hiện tại. Vui lòng kiểm tra trước khi lưu."
            )
            return {
                "status": "ready",
                "intent": "sample_form",
                "reply": reply,
                "params": {
                    "sample_id": current.get("id"),
                    "sample_fields": allowed_fields,
                    "color_corrections": [],
                    "ocr_text": local_text,
                },
            }

    return None


def _handle_order_form_fill_from_image(
    text: str,
    lang: str,
    image_bytes: bytes | None,
    field_manifest: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    if not image_bytes or not _is_order_form_context(field_manifest):
        return None
    from . import ai_service

    raw_text = ai_service.extract_text_from_image_local(image_bytes)
    parsed = _parse_order_document_fields(raw_text)
    if not parsed.get("fields") and not parsed.get("order_items"):
        return None

    warnings = [warning for warning in parsed.get("warnings", []) if warning]
    sample_match = parsed.get("sample_match") or {}
    sample_hint = ""
    if sample_match.get("id"):
        sample_hint = f" 已匹配樣品「{sample_match.get('title')}」({sample_match.get('sample_no')})。"
    if warnings:
        sample_hint += " " + " ".join(warnings[:2])

    reply = (
        f"已從訂單圖片整理出可填寫欄位，並準備填入目前訂單表單。請確認後送出。{sample_hint}".strip()
        if lang == "zh"
        else "Đã trích xuất các trường có thể điền từ ảnh đơn hàng và chuẩn bị điền vào biểu mẫu hiện tại. Vui lòng kiểm tra trước khi lưu."
    )
    return {
        "status": "ready",
        "intent": "order_form",
        "reply": reply,
        "params": {
            "fields": parsed.get("fields", {}),
            "order_items": parsed.get("order_items", []),
            "ocr_text": raw_text,
            "sample_match": sample_match,
            "warnings": warnings,
        },
    }


def _handle_stock_in_form_fill_from_image(
    text: str,
    lang: str,
    image_bytes: bytes | None,
    field_manifest: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    if not image_bytes or not _is_stock_in_form_context(field_manifest):
        return None
    from . import ai_service

    raw_text = ai_service.extract_text_from_image_local(image_bytes)
    parsed = _parse_stock_in_document_fields(image_bytes, raw_text)
    if not parsed.get("fields") and not parsed.get("stock_in_rows"):
        return None

    reply = (
        f"已從入庫單圖片整理出 {len(parsed.get('stock_in_rows', []))} 筆布疋資料，並準備填入目前入庫表單。請確認後送出。"
        if lang == "zh"
        else f"Đã trích xuất {len(parsed.get('stock_in_rows', []))} dòng nhập kho từ ảnh và chuẩn bị điền vào biểu mẫu hiện tại. Vui lòng kiểm tra trước khi lưu."
    )
    return {
        "status": "ready",
        "intent": "stock_in_form",
        "reply": reply,
        "params": {
            "fields": parsed.get("fields", {}),
            "stock_in_rows": parsed.get("stock_in_rows", []),
            "ocr_text": raw_text,
        },
    }


def _parse_json(text: str) -> dict[str, Any] | None:
    """
    嘗試從 LLM 輸出中解析 JSON 物件。
    採用較強韌的「尋找最外層花括號」策略，避免受 Markdown 或雜訊干擾。
    """
    if not text:
        return None

    # Step 1: 移除思維標籤
    from .ai_service import _strip_think_tags
    text = _strip_think_tags(text)

    # Step 2: 尋找第一個 '{' 和最後一個 '}'
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1:
        logger.warning(f"[Dispatcher] 未能於回應中找到 JSON 物件: {text[:200]}...")
        return None

    raw_json = text[start : end + 1]

    # Step 3: 解析 JSON
    try:
        # 預處理：處理常見的 LLM JSON 錯誤 (如單引號或尾隨逗號)
        # 注意：此處僅做基本嘗試，若仍失敗則由 json.loads 拋出異常
        return json.loads(raw_json)
    except json.JSONDecodeError as e:
        # 進階嘗試：有些模型會輸出單引號 JSON，嘗試修正
        try:
            # 僅用於簡單的修正嘗試
            fixed = raw_json.replace("'", '"')
            return json.loads(fixed)
        except Exception:
            pass

        logger.error(f"[Dispatcher] JSON 解析失敗！原因: {e}")
        print(f"\n[AI DEBUG] 原始回應解析失敗內容:\n{text}\n")
        return None


# ---------------------------------------------------------------------------
# 公開 API
# ---------------------------------------------------------------------------

def dispatch(
    text: str,
    lang: str,
    db_path: str,
    processor,          # AIProcessor instance
    username: str = "operator",
    image_bytes: bytes | None = None,
    history: list[dict[str, str]] | None = None,
    current_entity: dict[str, Any] | None = None,
    field_manifest: dict[str, Any] | None = None,
    conversation_id: str = "default",
    route_text: str | None = None,
) -> dict[str, Any]:
    """
    主要入口：使用 Agent 架構（Ollama Tool Calling）處理用戶請求。
    若 Agent 失敗，降級到舊的意圖分類邏輯。
    """
    routing_text = route_text if route_text is not None else text

    sample_text_action = _handle_sample_form_text_actions(
        text=routing_text,
        lang=lang,
        current_entity=current_entity,
        field_manifest=field_manifest,
    )
    if sample_text_action:
        logger.info("[Dispatcher] 命中 sample form 文字操作路由")
        return sample_text_action

    if not image_bytes:
        text_form_fill = _handle_current_form_fill_from_text(
            text=routing_text,
            lang=lang,
            field_manifest=field_manifest,
        )
        if text_form_fill:
            logger.info("[Dispatcher] 命中 current form 文字填表路由")
            return text_form_fill

    order_form_fill = _handle_order_form_fill_from_image(
        text=routing_text,
        lang=lang,
        image_bytes=image_bytes,
        field_manifest=field_manifest,
    )
    if order_form_fill:
        logger.info("[Dispatcher] 命中 order form 圖片填表路由")
        return order_form_fill

    stock_in_form_fill = _handle_stock_in_form_fill_from_image(
        text=routing_text,
        lang=lang,
        image_bytes=image_bytes,
        field_manifest=field_manifest,
    )
    if stock_in_form_fill:
        logger.info("[Dispatcher] 命中 stock in form 圖片填表路由")
        return stock_in_form_fill

    form_fill = _handle_sample_form_fill_from_image(
        text=routing_text,
        lang=lang,
        image_bytes=image_bytes,
        current_entity=current_entity,
        field_manifest=field_manifest,
    )
    if form_fill:
        logger.info("[Dispatcher] 命中 sample form 圖片填表路由")
        return form_fill

    if _is_color_correction_apply_request(routing_text, image_bytes, current_entity=current_entity):
        try:
            hard_routed = _handle_color_correction_apply(
                text=routing_text,
                lang=lang,
                image_bytes=image_bytes,
                current_entity=current_entity,
            )
            if hard_routed:
                logger.info("[Dispatcher] 命中校色圖片硬路由")
                return hard_routed
        except Exception as e:
            logger.warning(f"[Dispatcher] 校色圖片硬路由失敗，回退 Agent：{e}", exc_info=True)

    try:
        # 優先使用 Agent 架構
        from .agent import AgentRunner
        runner = AgentRunner(
            processor=processor,
            db_path=db_path,
            lang=lang,
            username=username,
            image_bytes=image_bytes,
            history=history,
            current_entity=current_entity,
            field_manifest=field_manifest,
            conversation_id=conversation_id,
        )
        result = runner.run(text)
        logger.info(f"[Dispatcher] Agent 完成：status={result.get('status')}, intent={result.get('intent')}")
        return result

    except Exception as e:
        logger.warning(f"[Dispatcher] Agent 架構失敗，降級到舊邏輯：{e}", exc_info=True)
        # 降級路徑：使用舊的 fallback chat
        return _fallback_chat(text, lang, processor)


def _get_empty_fallback(lang: str) -> str:
    """當回應為空時的保底字串。"""
    return (
        "抱歉，我現在無法完整處理您的請求。請提供更多細節（如布號、缸號等），或稍後再試。"
        if lang == "zh"
        else "Xin lỗi, tôi không thể xử lý yêu cầu lúc này. Vui lòng cung cấp thêm thông tin."
    )


def _fallback_chat(text: str, lang: str, processor) -> dict[str, Any]:
    """當解析失敗或意圖不明時的降級對話。"""
    chat_system_prompt = (
        "你是一個工廠管理系統的 AI 助理。請用專業、友善的語氣直接協助用戶。"
        "如果用戶想要登記資料（如新增布號、入庫等），請引導他們提供必要資訊（布號、缸號、重量等）。"
        "若用戶的語言是繁體中文請用繁體中文，若是越南文則用越南文。\n"
        "若你需要思考，請先將思考過程完全包裝在 <thinking> 和 </thinking> 標籤之內。"
    )
    reply = processor.generate(
        prompt=text,
        system_prompt=chat_system_prompt,
        max_tokens=1024,
        temperature=0.7
    )
    from .ai_service import _strip_think_tags
    cleaned = _strip_think_tags(reply)
    if not cleaned:
        cleaned = _get_empty_fallback(lang)
    return {"status": "ok", "intent": "unknown", "reply": cleaned}


def _handle_stock_in(
    text: str, lang: str, processor
) -> dict[str, Any]:
    """處理入庫登記意圖。"""
    raw = processor.generate(
        prompt=text,
        system_prompt=STOCK_IN_EXTRACT_SYSTEM,
        max_tokens=1024,
        temperature=0.0,
    )
    result = _parse_json(raw)

    if not result:
        return {"status": "error", "raw": raw}

    if result.get("status") == "need_info":
        reply_text = result.get("question_zh" if lang == "zh" else "question_vi")
        if not reply_text:
            # 嘗試從 raw 中提取
            from .ai_service import _strip_think_tags
            reply_text = _strip_think_tags(raw)
        
        return {
            "status": "need_info",
            "intent": "stock_in",
            "reply": reply_text or _get_empty_fallback(lang),
        }

    if result.get("status") == "ready":
        return {
            "status": "ready",
            "intent": "stock_in",
            "params": result.get("params", {}),
            "reply": reply_text or ("入庫登記資訊已備齊，請確認後送出。" if lang == "zh" else "Thông tin nhập kho đã đầy đủ."),
        }

    return {"status": "error", "raw": raw}


def _handle_production_log(
    text: str, lang: str, processor
) -> dict[str, Any]:
    """處理生產登記意圖。"""
    raw = processor.generate(
        prompt=text,
        system_prompt=PRODUCTION_LOG_EXTRACT_SYSTEM,
        max_tokens=1024,
        temperature=0.0,
    )
    result = _parse_json(raw)

    if not result:
        return {"status": "error", "raw": raw}

    reply_text = result.get("question_zh" if lang == "zh" else "question_vi")

    if result.get("status") == "need_info":
        if not reply_text:
            from .ai_service import _strip_think_tags
            reply_text = _strip_think_tags(raw)
            
        return {
            "status": "need_info",
            "intent": "production_log",
            "reply": reply_text or _get_empty_fallback(lang),
        }

    if result.get("status") == "ready":
        return {
            "status": "ready",
            "intent": "production_log",
            "params": result.get("params", {}),
            "reply": reply_text or ("生產登記資訊已備齊，請確認後送出。" if lang == "zh" else "Thông tin đã đầy đủ."),
        }

    return {"status": "error", "raw": raw}


def _parse_error(lang: str) -> dict[str, Any]:
    """降級錯誤回應。"""
    reply = ("系統暫時無法處理您的請求，請重試。" if lang == "zh" else "Lỗi hệ thống, vui lòng thử lại.")
    return {"status": "error", "intent": "unknown", "reply": reply}
