from __future__ import annotations

from typing import Any

from .common import ToolContext


CREATE_SAMPLE_SCHEMA = {
    "type": "function",
    "function": {
        "name": "create_sample",
        "description": (
            "建立新的樣品文字記錄。"
            "適合在用戶已提供樣號與名稱時使用；圖片檔案本身由其他流程處理，這個工具只寫文字欄位。"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "sample_no": {"type": "string", "description": "樣品編號，例如 S-001。"},
                "title": {"type": "string", "description": "樣品名稱或標題。"},
                "fabric_no": {"type": "string", "description": "關聯布號。"},
                "remark": {"type": "string", "description": "備註。"},
            },
            "required": ["sample_no", "title"],
        },
    },
}

FIND_SAMPLE_CANDIDATES_SCHEMA = {
    "type": "function",
    "function": {
        "name": "find_sample_candidates",
        "description": (
            "根據樣號、標題、近似詞或錯字搜尋樣品候選。"
            "當用戶提到樣品名稱，無論是否精準，都應先呼叫此工具。"
            "若 result.status=resolved（最佳候選明顯領先），可直接採用 best_match；"
            "若 result.status=ambiguous，請再呼叫 ask_user 讓用戶選擇。"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "樣品名稱、樣號或模糊關鍵詞。"},
                "top_k": {"type": "integer", "description": "回傳候選數量，預設 5。"},
            },
            "required": ["query"],
        },
    },
}

SEARCH_SAMPLE_BY_IMAGE_SCHEMA = {
    "type": "function",
    "function": {
        "name": "search_sample_by_image",
        "description": (
            "使用用戶上傳的圖片搜尋最相似的樣品。"
            "當用戶貼圖、上傳 sample 圖、詢問這張圖叫什麼時使用。"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "top_k": {"type": "integer", "description": "最多回傳幾筆候選結果，預設 5。"},
                "image_id": {
                    "type": "string",
                    "description": "微庫中的圖片ID。若要讀取之前的圖片請提供此值。若為當前上傳的新圖則可省略。",
                }
            },
        },
    },
}

LIST_SAMPLES_SCHEMA = {
    "type": "function",
    "function": {
        "name": "list_samples",
        "description": "按樣號或標題列出樣品。當用戶要找樣品清單、搜尋樣品、確認樣號時使用。",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "樣品編號或標題的關鍵字。"},
            },
        },
    },
}

EDIT_SAMPLE_SCHEMA = {
    "type": "function",
    "function": {
        "name": "edit_sample",
        "description": (
            "修改樣品資料，例如標題、布號或備註。"
            "如果用戶要求清空備註，需把 remark 明確設為空字串。"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "要修改的樣品編號或標題。"},
                "title": {"type": "string", "description": "新標題。"},
                "fabric_no": {"type": "string", "description": "新的關聯布號。"},
                "remark": {"type": "string", "description": "新備註；若要清空請傳空字串。"},
            },
            "required": ["query"],
        },
    },
}


def exec_create_sample(args: dict[str, Any], ctx: ToolContext) -> dict[str, Any]:
    from ...services import sample_repo
    from ...services.db import query_db

    sample_no = args["sample_no"]
    title = args["title"]
    fabric_no = args.get("fabric_no", "")
    remark = args.get("remark", "")

    existing = query_db(
        "SELECT id, sample_no, title FROM samples WHERE sample_no = ?",
        (sample_no,),
        one=True,
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


def exec_find_sample_candidates(args: dict[str, Any], ctx: ToolContext) -> dict[str, Any]:
    from ...services import sample_repo

    query = (args.get("query") or "").strip()
    top_k = int(args.get("top_k", 5) or 5)
    if not query:
        return {"error": "Missing query"}

    candidates = sample_repo.find_sample_candidates(query, limit=max(1, min(top_k, 10)))
    if not candidates:
        return {
            "status": "not_found",
            "query": query,
            "count": 0,
            "samples": [],
            "message": f"找不到符合 '{query}' 的樣品。",
        }

    best = candidates[0]
    second = candidates[1] if len(candidates) > 1 else None
    resolved = best["score"] >= 0.92 and (second is None or best["score"] - second["score"] >= 0.08)
    return {
        "status": "resolved" if resolved else "ambiguous",
        "query": query,
        "count": len(candidates),
        "samples": candidates,
        "best_match": best,
        "needs_user_clarification": not resolved,
        "message": f"找到 {len(candidates)} 個樣品候選。",
    }


def exec_search_sample_by_image(args: dict[str, Any], ctx: ToolContext) -> dict[str, Any]:
    image_bytes = ctx.get_image(args.get("image_id"))
    if not image_bytes:
        return {"error": "沒有收到圖片或指定微庫檔案不存在。請上傳一張圖片再試。"}

    top_k = args.get("top_k", 5)
    try:
        from flask import current_app

        from .. import ai_service

        results = ai_service.search_similar_sample_images(
            image_bytes=image_bytes,
            db_path=current_app.config["DATABASE"],
            top_k=top_k,
            upload_dir=current_app.config.get("SAMPLES_UPLOAD_DIR", ""),
        )
        if not results:
            return {"count": 0, "samples": [], "message": "系統中沒有含預覽圖的樣品。"}
        return {
            "count": len(results[:top_k]),
            "samples": results[:top_k],
            "message": f"找到 {len(results[:top_k])} 個相似樣品。",
        }
    except ImportError as e:
        return {"error": f"缺少必要的依賴套件：{e}。請安裝 sentence-transformers。"}
    except Exception as e:
        return {"error": str(e)}


def exec_list_samples(args: dict[str, Any], ctx: ToolContext) -> dict[str, Any]:
    from ...services import sample_repo

    query = args.get("query", "")
    if query:
        samples = sample_repo.find_sample_candidates(query, limit=20, min_score=0.25)
        results = [
            {
                "sample_id": row["id"],
                "sample_no": row["sample_no"],
                "title": row["title"],
                "fabric_no": row.get("fabric_no", ""),
                "preview_path": row.get("preview_path", ""),
                "score": row.get("score"),
            }
            for row in samples
        ]
    else:
        samples = sample_repo.list_samples(q=None)
        results = []
        for row in (samples or [])[:20]:
            results.append(
                {
                    "sample_id": row["id"],
                    "sample_no": row["sample_no"],
                    "title": row["title"],
                    "fabric_no": row.get("fabric_no", ""),
                    "preview_path": row.get("preview_path", ""),
                }
            )
    return {"count": len(results), "samples": results}


def exec_edit_sample(args: dict[str, Any], ctx: ToolContext) -> dict[str, Any]:
    from ...services import sample_repo

    query = args.get("query")
    if not query:
        return {"error": "Missing query parameter (sample_no or title)"}

    try:
        result = sample_repo.update_sample_by_ai(
            query=query,
            title=args.get("title"),
            fabric_no=args.get("fabric_no"),
            remark=args.get("remark"),
        )
        if result.get("status") == "ambiguous":
            return {
                "status": "ambiguous",
                "message": f"找到了多個符合 '{query}' 的樣品，請確認是哪一個？",
                "options": [f"編號 {item['sample_no']} ({item['title']})" for item in result["matches"]],
            }
        return {
            "status": "updated",
            "title": result["title"],
            "message": f"樣品 '{result['title']}' 已更新。",
        }
    except Exception as e:
        return {"error": str(e)}
