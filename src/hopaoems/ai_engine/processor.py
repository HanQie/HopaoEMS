"""
processor.py (Ollama Version)
==============================
AI 處理器核心 — 使用 Ollama 本地服務取代 Transformers (PyTorch)。

架構：
  - OllamaProcessor 提供與原 AIProcessor 相同的 generate() 介面
  - 內部調用 ai_service.call_ollama()
  - AIProcessor = OllamaProcessor（向後相容別名）
  - 首次啟動若 ollama SDK 未安裝，自動執行 pip install
"""

from __future__ import annotations

import logging
import subprocess
import sys
from typing import Optional

from . import ai_service

logger = logging.getLogger(__name__)


def _ensure_ollama_installed() -> bool:
    """
    確保 ollama SDK 已安裝。若未安裝，自動執行 pip install ollama。
    回傳 True 表示安裝成功或已有安裝，False 表示安裝失敗。
    """
    try:
        import ollama  # noqa: F401
        return True
    except ImportError:
        pass

    logger.warning("[OllamaProcessor] ollama SDK 未安裝，正在自動安裝...")
    try:
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", "ollama>=0.2.0"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        import importlib
        importlib.invalidate_caches()
        import ollama  # noqa: F401
        logger.info("[OllamaProcessor] ollama SDK 安裝成功。")
        return True
    except Exception as e:
        logger.error(f"[OllamaProcessor] ollama SDK 自動安裝失敗：{e}")
        return False


class OllamaProcessor:
    """
    Ollama 封裝類，提供與原 AIProcessor 相同的 generate() 介面。
    """

    def __init__(self) -> None:
        # 自動安裝 ollama SDK（若尚未安裝）
        _ensure_ollama_installed()
        self._test_connection()

    def _test_connection(self) -> None:
        """啟動時測試 Ollama 連線，顯示詳細狀態訊息。"""
        base_url   = ai_service._config["base_url"]
        text_model = ai_service._config["text_model"]
        vl_model   = ai_service._config["vl_model"]

        def _log(msg: str):
            # 同時印到終端機與 logger
            print(msg)
            logger.info(msg)

        _log("=" * 55)
        _log("[AI ENGINE] ▶ Ollama 連線診斷")
        _log(f"  服務器地址 : {base_url}")
        _log(f"  文字模型   : {text_model}")
        _log(f"  視覺模型   : {vl_model}")
        _log("=" * 55)

        try:
            import ollama as _sdk
            client = _sdk.Client(host=base_url)
            model_list = client.list()

            # 取出所有可用模型名稱
            available = [m.model for m in model_list.models]
            _log(f"  ✅ Ollama 連線成功")
            _log(f"  📦 已安裝模型（共 {len(available)} 個）：")
            for name in available:
                _log(f"       - {name}")

            # 確認目標模型是否存在
            def _model_available(target: str) -> bool:
                return any(
                    a == target or a.startswith(target.split(":")[0])
                    for a in available
                )

            if _model_available(text_model):
                _log(f"  ✅ 文字模型 [{text_model}] 已就緒")
            else:
                _log(f"  ⚠️  文字模型 [{text_model}] 未找到！")
                _log(f"     請執行：ollama pull {text_model}")

            if vl_model != text_model:
                if _model_available(vl_model):
                    _log(f"  ✅ 視覺模型 [{vl_model}] 已就緒")
                else:
                    _log(f"  ⚠️  視覺模型 [{vl_model}] 未找到！")
                    _log(f"     請執行：ollama pull {vl_model}")

        except ImportError:
            _log("  ❌ ollama SDK 未安裝（自動安裝應已嘗試，請重啟應用）")
        except Exception as e:
            _log(f"  ❌ 無法連接 Ollama 服務：{e}")
            _log(f"     請確認 Ollama 已啟動：ollama serve")
            _log(f"     服務器地址：{base_url}")
        finally:
            _log("=" * 55)

    def generate(
        self,
        prompt: str,
        system_prompt: str = "",
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        top_p: Optional[float] = None,
        top_k: Optional[int] = None,
        repetition_penalty: Optional[float] = None,
        images: Optional[list[bytes]] = None,
    ) -> str:
        """
        調用 Ollama 生成文字回應。

        Parameters
        ----------
        prompt             : 用戶訊息
        system_prompt      : 系統角色 Prompt
        max_tokens         : 最大生成 token 數
        temperature        : 採樣溫度
        top_p / top_k      : 採樣參數（傳遞給 Ollama options，目前版本透過 num_predict 和 temperature 支援）
        repetition_penalty : 重複懲罰（Ollama 對應 repeat_penalty）
        images             : 圖片 bytes 列表（傳入時使用 VL 模型）

        Returns
        -------
        str : 模型回應文字（已去除 <think> 區塊）
        """
        logger.info(f"[Processor] 開始生成 (prompt: {prompt[:30]}...)")
        res = ai_service.call_ollama(
            prompt=prompt,
            system_prompt=system_prompt,
            images=images,
            max_tokens=max_tokens,
            temperature=temperature,
        )
        logger.info(f"[Processor] 生成結束 (結果回傳至 UI)")
        return res

    def chat_with_tools(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
        max_tokens: int | None = None,
        temperature: float | None = None,
    ):
        """
        Tool-calling 介面：回傳完整 Ollama response（含 tool_calls）。

        Parameters
        ----------
        messages    : 完整的聊天訊息列表
        tools       : Ollama tools schema 列表
        max_tokens  : 最大生成 token 數
        temperature : 採樣溫度

        Returns
        -------
        Ollama ChatResponse 物件
        """
        logger.info(f"[Processor] chat_with_tools (messages: {len(messages)}, tools: {len(tools or [])})")
        return ai_service.call_ollama_with_tools(
            messages=messages,
            tools=tools,
            max_tokens=max_tokens,
            temperature=temperature,
        )


# 向後相容別名
AIProcessor = OllamaProcessor
