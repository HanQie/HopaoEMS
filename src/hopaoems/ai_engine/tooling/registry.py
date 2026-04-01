from __future__ import annotations

import json
import logging
from typing import Any, Callable

from .color_tools import (
    BATCH_RECORD_COLOR_CORRECTIONS_SCHEMA,
    DEDUPLICATE_COLOR_CORRECTIONS_SCHEMA,
    EXTRACT_COLOR_CORRECTION_DATA_SCHEMA,
    exec_batch_record_color_corrections,
    exec_deduplicate_color_corrections,
    exec_extract_color_correction_data,
)
from .common import ToolContext
from .conversation_tools import ASK_USER_SCHEMA, exec_ask_user
from .fabric_tools import (
    DELETE_FABRIC_SCHEMA,
    LOOKUP_FABRIC_SCHEMA,
    LOOKUP_ROLL_SCHEMA,
    REGISTER_FABRIC_ONLY_SCHEMA,
    STOCK_IN_FULL_SCHEMA,
    exec_delete_fabric,
    exec_lookup_fabric,
    exec_lookup_roll,
    exec_register_fabric_only,
    exec_stock_in_full,
)
from .production_tools import LOG_PRODUCTION_SCHEMA, exec_log_production
from .query_tools import QUERY_DATABASE_SCHEMA, exec_query_database
from .image_tools import (
    CLASSIFY_UPLOADED_IMAGE_SCHEMA,
    EXTRACT_STOCK_IN_DATA_FROM_IMAGE_SCHEMA,
    SUGGEST_SAMPLE_TITLE_FROM_IMAGE_SCHEMA,
    exec_classify_uploaded_image,
    exec_extract_stock_in_data_from_image,
    exec_suggest_sample_title_from_image,
)
from .sample_tools import (
    CREATE_SAMPLE_SCHEMA,
    EDIT_SAMPLE_SCHEMA,
    FIND_SAMPLE_CANDIDATES_SCHEMA,
    LIST_SAMPLES_SCHEMA,
    SEARCH_SAMPLE_BY_IMAGE_SCHEMA,
    exec_create_sample,
    exec_edit_sample,
    exec_find_sample_candidates,
    exec_list_samples,
    exec_search_sample_by_image,
)

logger = logging.getLogger(__name__)

TOOL_SCHEMAS = [
    EXTRACT_COLOR_CORRECTION_DATA_SCHEMA,
    BATCH_RECORD_COLOR_CORRECTIONS_SCHEMA,
    DEDUPLICATE_COLOR_CORRECTIONS_SCHEMA,
    CLASSIFY_UPLOADED_IMAGE_SCHEMA,
    QUERY_DATABASE_SCHEMA,
    EXTRACT_STOCK_IN_DATA_FROM_IMAGE_SCHEMA,
    STOCK_IN_FULL_SCHEMA,
    REGISTER_FABRIC_ONLY_SCHEMA,
    LOG_PRODUCTION_SCHEMA,
    LOOKUP_FABRIC_SCHEMA,
    LOOKUP_ROLL_SCHEMA,
    ASK_USER_SCHEMA,
    CREATE_SAMPLE_SCHEMA,
    FIND_SAMPLE_CANDIDATES_SCHEMA,
    SEARCH_SAMPLE_BY_IMAGE_SCHEMA,
    SUGGEST_SAMPLE_TITLE_FROM_IMAGE_SCHEMA,
    LIST_SAMPLES_SCHEMA,
    EDIT_SAMPLE_SCHEMA,
    DELETE_FABRIC_SCHEMA,
]

TOOL_EXECUTORS: dict[str, Callable[[dict[str, Any], ToolContext], dict[str, Any]]] = {
    "query_database": exec_query_database,
    "stock_in_full": exec_stock_in_full,
    "register_fabric_only": exec_register_fabric_only,
    "log_production": exec_log_production,
    "lookup_fabric": exec_lookup_fabric,
    "lookup_roll": exec_lookup_roll,
    "ask_user": exec_ask_user,
    "create_sample": exec_create_sample,
    "find_sample_candidates": exec_find_sample_candidates,
    "search_sample_by_image": exec_search_sample_by_image,
    "list_samples": exec_list_samples,
    "edit_sample": exec_edit_sample,
    "batch_record_color_corrections": exec_batch_record_color_corrections,
    "deduplicate_color_corrections": exec_deduplicate_color_corrections,
    "extract_color_correction_data": exec_extract_color_correction_data,
    "classify_uploaded_image": exec_classify_uploaded_image,
    "extract_stock_in_data_from_image": exec_extract_stock_in_data_from_image,
    "suggest_sample_title_from_image": exec_suggest_sample_title_from_image,
    "delete_fabric": exec_delete_fabric,
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
