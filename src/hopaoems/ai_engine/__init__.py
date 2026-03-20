"""
ai_engine package (Agent Architecture + Ollama)
=================================================
提供 HopaoEMS AI 助理的核心功能：
  - OllamaProcessor : Ollama API 封裝（支持文字 + 圖片 + Tool Calling）
  - AgentRunner     : Agent 核心循環（使用 Ollama Function Calling）
  - Tools           : 可調用的工具集（資料庫查詢、入庫、生產登記等）
  - SQLAgent        : Text-to-SQL 查詢代理（唯讀，動態 schema）

使用單例模式：整個 Flask 應用生命週期只初始化一次，
由 init_ai_engine(app) 在 create_app() 中呼叫。

模型策略：
  - text_model（決策大腦）：qwen2.5:7b — 用於 Agent Tool Calling
  - vl_model（視覺模型）：qwen3-vl:4b — 用於圖片 OCR
  - 啟動時自動檢查並下載缺失的模型（支持斷點續傳）
"""

from __future__ import annotations

import logging
import sys
import time
from typing import TYPE_CHECKING

# 設定 AI 引擎套件的日誌等級為 INFO，確保控制台可見
logging.getLogger("hopaoems.ai_engine").setLevel(logging.INFO)

if TYPE_CHECKING:
    from flask import Flask

_processor = None   # OllamaProcessor singleton

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 模型自動下載（含進度條 + 速率顯示）
# ---------------------------------------------------------------------------
def _ensure_model_available(client, model_name: str) -> bool:
    """
    檢查 Ollama 是否已安裝指定模型，若缺失則自動下載。
    
    特性：
    - 顯示進度條與下載速率
    - Ollama pull 原生支持斷點續傳（中斷後重啟會從上次進度繼續）
    - 下載失敗不阻塞應用啟動
    
    Returns: True 表示模型可用，False 表示不可用
    """
    # 檢查模型是否已存在
    try:
        model_list = client.list()
        available = [m.model for m in model_list.models]
        
        # 精確匹配或前綴匹配
        model_base = model_name.split(":")[0]
        if any(a == model_name or a.startswith(model_base + ":") for a in available):
            return True
    except Exception as e:
        logger.error(f"[AI ENGINE] 無法檢查模型列表：{e}")
        return False

    # 模型不存在 → 開始下載
    print(f"\n{'='*60}")
    print(f"  ⬇️  模型 [{model_name}] 未找到，正在自動下載...")
    print(f"  （支持斷點續傳，中斷後重啟會繼續下載）")
    print(f"{'='*60}\n")

    try:
        last_status = ""
        last_completed = 0
        last_time = time.time()
        last_speed_display = ""

        for progress in client.pull(model=model_name, stream=True):
            status = progress.get("status", "")
            total = progress.get("total") or 0
            completed = progress.get("completed") or 0

            if status != last_status:
                if last_status:
                    # 上一個階段結束，換行
                    print()
                last_status = status
                last_completed = 0
                last_time = time.time()

            if total and total > 0 and completed is not None:
                # 計算進度百分比
                pct = completed / total * 100
                
                # 計算下載速率
                now = time.time()
                elapsed = now - last_time
                if elapsed > 0.5:  # 每 0.5 秒更新一次速率
                    bytes_delta = completed - last_completed
                    speed = bytes_delta / elapsed
                    if speed > 1_000_000:
                        last_speed_display = f"{speed / 1_000_000:.1f} MB/s"
                    elif speed > 1_000:
                        last_speed_display = f"{speed / 1_000:.1f} KB/s"
                    else:
                        last_speed_display = f"{speed:.0f} B/s"
                    last_completed = completed
                    last_time = now

                # 進度條
                bar_len = 30
                filled = int(bar_len * completed / total)
                bar = "█" * filled + "░" * (bar_len - filled)
                
                # 大小顯示
                completed_mb = completed / 1_000_000
                total_mb = total / 1_000_000
                size_str = f"{completed_mb:.1f}MB/{total_mb:.1f}MB"
                
                # 輸出到同一行
                sys.stdout.write(
                    f"\r  [{bar}] {pct:5.1f}% | {size_str} | {last_speed_display:>12s} | {status}"
                )
                sys.stdout.flush()
            else:
                sys.stdout.write(f"\r  {status}...")
                sys.stdout.flush()

        print(f"\n\n  ✅ 模型 [{model_name}] 下載完成！\n")
        return True

    except KeyboardInterrupt:
        print(f"\n\n  ⏸️  下載已暫停（下次啟動時會繼續下載）")
        return False
    except Exception as e:
        print(f"\n\n  ❌ 模型下載失敗：{e}")
        logger.error(f"[AI ENGINE] 模型下載失敗：{e}", exc_info=True)
        return False


def init_ai_engine(app: "Flask") -> None:
    """
    在 Flask application context 中初始化 AI 引擎。
    從 app.config 讀取 Ollama 配置，自動下載缺失模型，連接失敗時降級運行。
    """
    global _processor

    from . import ai_service
    from .processor import OllamaProcessor

    # 讀取配置（可在 instance/config.py 中覆蓋）
    base_url = app.config.get("OLLAMA_BASE_URL", "http://localhost:11434")
    text_model = app.config.get("OLLAMA_MODEL", "qwen2.5:7b")
    vl_model = app.config.get("OLLAMA_VL_MODEL", "qwen3-vl:4b")

    app.logger.info(
        f"[AI ENGINE] 初始化 Ollama 後端 → "
        f"base_url={base_url}, text_model={text_model}, vl_model={vl_model}"
    )

    # 配置 ai_service 全域參數
    ai_service.configure(
        base_url=base_url,
        text_model=text_model,
        vl_model=vl_model,
    )

    # 自動檢查並下載模型
    try:
        import ollama as _ollama_sdk
        client = _ollama_sdk.Client(host=base_url)
        
        # 檢查文字模型（Agent 決策大腦）
        if not _ensure_model_available(client, text_model):
            app.logger.warning(
                f"[AI ENGINE] 文字模型 [{text_model}] 不可用，"
                f"Agent 功能將降級。請手動執行：ollama pull {text_model}"
            )
        
        # 檢查視覺模型（如果不同於文字模型）
        if vl_model != text_model:
            if not _ensure_model_available(client, vl_model):
                app.logger.warning(
                    f"[AI ENGINE] 視覺模型 [{vl_model}] 不可用，"
                    f"圖片 OCR 功能將降級。請手動執行：ollama pull {vl_model}"
                )
    except ImportError:
        app.logger.warning("[AI ENGINE] ollama SDK 未安裝，跳過模型檢查")
    except Exception as e:
        app.logger.warning(f"[AI ENGINE] Ollama 服務不可用，跳過模型檢查：{e}")

    try:
        _processor = OllamaProcessor()
        app.logger.info("[AI ENGINE] OllamaProcessor 初始化完成。")
    except Exception as e:
        import traceback
        app.logger.error(f"[AI ENGINE] 初始化失敗：{e}")
        app.logger.error(traceback.format_exc())
        app.logger.warning("[AI] AI 引擎初始化失敗，將以降級模式運行。")
        _processor = None


def get_processor():
    """取得全域 OllamaProcessor 單例；若未初始化則回傳 None。"""
    return _processor
