"""
sql_agent.py (Dynamic Schema Version)
=======================================
Text-to-SQL 查詢代理。

改進：
- 動態讀取資料庫 Schema（不再硬編碼 SCHEMA_PROMPT）
- KNOWN_TABLES 從動態 schema 自動提取（不再硬編碼）
- 使用 ai_service.call_ollama() 直接調用（透過 processor 封裝）

安全機制：
1. ReadOnlyDB — SQLite URI 以 ro 模式開啟
2. Python 層攔截所有非 SELECT 語句
3. 幻覺校驗 — 比對表名與實際存在的表
"""

from __future__ import annotations

import json
import re
import sqlite3
import logging
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 寫入操作攔截
# ---------------------------------------------------------------------------
_WRITE_PATTERN = re.compile(
    r"\b(INSERT|UPDATE|DELETE|DROP|CREATE|ALTER|REPLACE|UPSERT|TRUNCATE|ATTACH|DETACH)\b",
    re.IGNORECASE,
)

# 提取 SQL 中所有表名（FROM / JOIN 後面的識別碼）
_TABLE_REF_PATTERN = re.compile(
    r'\b(?:FROM|JOIN|INTO|UPDATE)\s+([`"\[]?[a-zA-Z_][a-zA-Z0-9_]*[`"\]]?)',
    re.IGNORECASE,
)


class ReadOnlyDB:
    """
    唯讀 SQLite 連接封裝。
    - 以 URI mode=ro 開啟（資料庫層保護）
    - Python 層攔截非 SELECT 語句（雙重保護）
    - 幻覺校驗：比對生成 SQL 中的表名與已知表
    """

    def __init__(self, db_path: str, known_tables: frozenset[str] | None = None) -> None:
        uri = f"file:{db_path}?mode=ro"
        self._conn = sqlite3.connect(uri, uri=True, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._known_tables = known_tables or frozenset()

    def execute(self, sql: str, params: tuple = ()) -> list[dict[str, Any]]:
        """執行 SQL 並返回 dict 列表。"""
        # 1. 攔截寫入語句
        if _WRITE_PATTERN.search(sql):
            raise PermissionError(
                f"唯讀模式：禁止執行非查詢語句。SQL: {sql[:80]}…"
            )

        # 2. 幻覺校驗（僅在 known_tables 非空時執行）
        if self._known_tables:
            referenced = {
                m.group(1).strip('`"[]').lower()
                for m in _TABLE_REF_PATTERN.finditer(sql)
            }
            unknown = referenced - self._known_tables
            if unknown:
                raise ValueError(
                    f"SQL 含有未知資料表，已拒絕執行：{unknown}。請重新生成。"
                )

        cur = self._conn.execute(sql, params)
        rows = cur.fetchall()
        return [dict(row) for row in rows]

    def close(self) -> None:
        self._conn.close()


# ---------------------------------------------------------------------------
# SQL 提取
# ---------------------------------------------------------------------------
_SQL_BLOCK = re.compile(r"```sql\s*(.*?)\s*```", re.DOTALL | re.IGNORECASE)


def _extract_sql(llm_output: str) -> str | None:
    """從 LLM 輸出中提取第一個 ```sql ... ``` 區塊。"""
    # think 標籤由 ai_service 已處理，但此處再次確認安全性
    from .ai_service import _strip_think_tags
    llm_output = _strip_think_tags(llm_output)

    m = _SQL_BLOCK.search(llm_output)
    if m:
        return m.group(1).strip()
    # fallback：找 SELECT 起始的語句
    m2 = re.search(r"(SELECT\s+.+?;?)\s*$", llm_output, re.DOTALL | re.IGNORECASE)
    if m2:
        return m2.group(1).strip()
    return None


# ---------------------------------------------------------------------------
# Prompt 模板
# ---------------------------------------------------------------------------
_SCHEMA_SYSTEM_TMPL = """\
你是一個 ERP 資料庫查詢專家。以下是系統的 SQLite 資料庫結構：

```sql
{schema}
```

規則：
1. 只能生成 SELECT 語句，嚴禁 INSERT / UPDATE / DELETE / DROP / CREATE / ALTER。
2. 輸出格式：先寫 ```sql ... ``` 程式碼區塊，再用一句話說明 SQL 的作用。
3. 若問題無法用已知表回答，直接說「無法回答」，不要捏造表或欄位。
4. 支持中文或越南語提問，請用對應語言說明。
"""

_RESPONSE_PROMPT_ZH = """\
根據以下 SQL 查詢結果，用簡潔的**繁體中文**回答用戶的問題。
若結果為空，說明沒有找到相關記錄。不要重複顯示原始 SQL。

用戶問題：{question}
SQL 結果（JSON 格式）：{results}
"""

_RESPONSE_PROMPT_VI = """\
Dựa trên kết quả truy vấn SQL dưới đây, hãy trả lời câu hỏi của người dùng bằng **tiếng Việt** ngắn gọn.
Nếu kết quả rỗng, hãy nói rằng không tìm thấy bản ghi liên quan. Không lặp lại SQL gốc.

Câu hỏi của người dùng: {question}
Kết quả SQL (định dạng JSON): {results}
"""


# ---------------------------------------------------------------------------
# 公開 API
# ---------------------------------------------------------------------------

def ask(
    question: str,
    lang: str,
    db_path: str,
    processor,
    max_result_rows: int = 50,
) -> str:
    """
    自然語言問題 → 動態讀取 Schema → 生成 SQL → 執行 → 人類語言回答。

    Parameters
    ----------
    question        : 用戶問題（中文或越南語）
    lang            : 'zh' 或 'vi'，決定回覆語言
    db_path         : SQLite 資料庫絕對路徑
    processor       : OllamaProcessor 實例（提供 generate() 介面）
    max_result_rows : 最多回傳幾行 SQL 結果
    """
    from . import ai_service

    # Step 1: 動態讀取 Schema
    schema_sql = ai_service.get_db_schema(db_path)
    if not schema_sql:
        return (
            "無法讀取資料庫結構，請聯繫管理員。"
            if lang == "zh"
            else "Không thể đọc cấu trúc cơ sở dữ liệu. Vui lòng liên hệ quản trị viên."
        )

    # Step 2: 動態提取已知表名（用於幻覺校驗）
    known_tables = ai_service.get_table_names_from_schema(schema_sql)

    # Step 3: LLM 生成 SQL
    system_prompt = _SCHEMA_SYSTEM_TMPL.format(schema=schema_sql)
    logger.debug(f"[SQLAgent] 問題：{question[:80]}")

    llm_sql_output = processor.generate(
        prompt=question,
        system_prompt=system_prompt,
        max_tokens=2048,
        temperature=0.0,
    )
    logger.debug(f"[SQLAgent] LLM SQL 輸出：{llm_sql_output[:200]}")

    # Step 4: 提取 SQL
    sql = _extract_sql(llm_sql_output)
    if not sql:
        return (
            "無法從 AI 回應中解析出有效的 SQL 查詢，請換一種方式提問。"
            if lang == "zh"
            else "Không thể phân tích câu truy vấn SQL từ phản hồi AI. Vui lòng thử cách đặt câu hỏi khác."
        )

    # Step 5: 幻覺校驗 + 執行
    db = ReadOnlyDB(db_path, known_tables=known_tables)
    try:
        rows = db.execute(sql)
    except PermissionError as e:
        logger.warning(f"[SQLAgent] 安全攔截：{e}")
        return (
            "安全限制：AI 嘗試執行非查詢操作，已被攔截。"
            if lang == "zh"
            else "Giới hạn bảo mật: AI đã cố thực hiện thao tác không phải truy vấn, đã bị chặn."
        )
    except ValueError as e:
        logger.warning(f"[SQLAgent] 幻覺校驗失敗：{e}")
        return (
            f"AI 產生了無效的 SQL（包含未知資料表）：{e}"
            if lang == "zh"
            else f"AI tạo ra SQL không hợp lệ (bảng không tồn tại): {e}"
        )
    except Exception as e:
        logger.error(f"[SQLAgent] SQL 執行錯誤：{e}")
        return (
            f"SQL 執行錯誤：{e}"
            if lang == "zh"
            else f"Lỗi thực thi SQL: {e}"
        )
    finally:
        db.close()

    # Step 6: 組成人類語言回答
    truncated = rows[:max_result_rows]
    results_json = json.dumps(truncated, ensure_ascii=False, default=str)
    response_prompt = (
        _RESPONSE_PROMPT_ZH if lang == "zh" else _RESPONSE_PROMPT_VI
    ).format(question=question, results=results_json)

    answer = processor.generate(
        prompt=response_prompt,
        max_tokens=1024,
        temperature=0.2,
    )
    return answer
