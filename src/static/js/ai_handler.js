/**
 * ai_handler.js
 * =============
 * 浮動 AI 助理對話框邏輯
 *
 * 職責：
 *  1. 開/關浮動面板
 *  2. 發送文字訊息至 POST /api/ai/chat
 *  3. 自動填表：若 AI 回傳 intent=stock_in / production_log 且 status=ready，
 *     將 params 自動填入當前頁面的 name 屬性匹配欄位
 */

(function () {
  'use strict';

  // -------------------------------------------------------------------------
  // 工具函數
  // -------------------------------------------------------------------------
  function getLang() {
    const hint = document.getElementById('ai-lang-hint');
    if (!hint) return 'zh';
    const raw = hint.dataset.lang || 'zh-TW';
    return raw.startsWith('vi') ? 'vi' : 'zh';
  }

  // -------------------------------------------------------------------------
  // 持久化 (SessionStorage)
  // -------------------------------------------------------------------------
  const STORAGE_KEY_HISTORY = 'ai_chat_history';
  const STORAGE_KEY_STATE = 'ai_chat_isOpen';

  let chatHistory = [];

  function loadHistory() {
    try {
      const saved = sessionStorage.getItem(STORAGE_KEY_HISTORY);
      if (saved) {
        chatHistory = JSON.parse(saved);
        chatHistory.forEach(msg => {
          renderMessage(msg.role, msg.text, false);
        });
      }
    } catch(e) { console.error('Failed to load chat history', e); }

    const isOpen = sessionStorage.getItem(STORAGE_KEY_STATE) === 'true';
    if (isOpen && panel) {
      panel.hidden = false;
      setTimeout(() => messagesEl && (messagesEl.scrollTop = messagesEl.scrollHeight), 50);
    }
  }

  function saveHistory() {
    sessionStorage.setItem(STORAGE_KEY_HISTORY, JSON.stringify(chatHistory));
  }

  function saveState() {
    if (panel) {
      sessionStorage.setItem(STORAGE_KEY_STATE, !panel.hidden);
    }
  }

  function clearHistory() {
    chatHistory = [];
    saveHistory();
    if (messagesEl) {
      messagesEl.textContent = '';
      const title = document.createElement('p');
      title.className = 'text-xs text-slate-400 text-center';
      title.textContent = getLang() === 'vi' ? 'Trợ lý AI' : 'AI 助理';
      messagesEl.appendChild(title);
    }
    if (inputEl) {
      inputEl.focus();
    }
  }

  // -------------------------------------------------------------------------
  // DOM 引用（全部延遲到 DOMContentLoaded）
  // -------------------------------------------------------------------------
  let panel, toggleBtn, messagesEl, inputEl, sendBtn;

  function initRefs() {
    panel      = document.getElementById('ai-chat-panel');
    toggleBtn  = document.getElementById('ai-chat-toggle');
    messagesEl = document.getElementById('ai-chat-messages');
    inputEl    = document.getElementById('ai-chat-input');
    sendBtn    = document.getElementById('ai-chat-send');
  }

  // -------------------------------------------------------------------------
  // 面板開關
  // -------------------------------------------------------------------------
  function togglePanel() {
    if (!panel) return;
    const hidden = panel.hidden;
    panel.hidden = !hidden;
    saveState();
    if (!hidden) {
      // 開啟時聚焦輸入框
      setTimeout(() => inputEl && inputEl.focus(), 80);
      messagesEl.scrollTop = messagesEl.scrollHeight;
    }
  }

  // -------------------------------------------------------------------------
  // 訊息渲染
  // -------------------------------------------------------------------------
  function renderMessage(role, text, save = true) {
    if (!messagesEl) return;
    const wrap = document.createElement('div');
    wrap.className = role === 'user'
      ? 'flex justify-end'
      : 'flex justify-start';

    const bubble = document.createElement('div');
    bubble.className = role === 'user'
      ? 'max-w-[85%] text-sm px-3 py-2 rounded-xl bg-slate-900 text-white rounded-br-sm'
      : 'max-w-[85%] text-sm px-3 py-2 rounded-xl bg-white border border-slate-200 text-slate-800 rounded-bl-sm';

    bubble.textContent = text;
    wrap.appendChild(bubble);
    messagesEl.appendChild(wrap);
    messagesEl.scrollTop = messagesEl.scrollHeight;

    if (save) {
      chatHistory.push({ role, text });
      saveHistory();
    }
  }

  function appendMessage(role, text) {
    renderMessage(role, text, true);
  }

  function appendSpinner() {
    const el = document.createElement('div');
    el.id = 'ai-thinking';
    el.className = 'flex justify-start';
    const inner = document.createElement('div');
    inner.className = 'text-xs text-slate-400 px-3 py-2 animate-pulse';
    inner.textContent = '…';
    el.appendChild(inner);
    messagesEl.appendChild(el);
    messagesEl.scrollTop = messagesEl.scrollHeight;
    return el;
  }

  function removeSpinner() {
    const el = document.getElementById('ai-thinking');
    if (el) el.remove();
  }

  // -------------------------------------------------------------------------
  // 自動填表
  // -------------------------------------------------------------------------
  const STOCK_IN_MAP = {
    fabric_code : ['fabric_code', 'fabric-code'],
    cylinder_no : ['cylinder_no', 'cylinder-no', 'cylinder_no'],
  };

  const PRODUCTION_LOG_MAP = {
    task_id   : ['task_id'],
    order_no  : ['order_no'],
    roll_id   : ['roll_id'],
    roll_no   : ['roll_no'],
    length_m  : ['length_m', 'printed_length', 'length'],
    note      : ['note'],
  };

  function autofill(intent, params) {
    if (!params) return;
    const map = intent === 'stock_in' ? STOCK_IN_MAP : PRODUCTION_LOG_MAP;

    Object.entries(map).forEach(([key, candidates]) => {
      const value = params[key];
      if (value === null || value === undefined) return;
      for (const name of candidates) {
        const el = document.querySelector(
          `input[name="${name}"], select[name="${name}"], textarea[name="${name}"]`
        );
        if (el) {
          el.value = value;
          // 觸發 change 事件（讓可能存在的 JS 聆聽器響應）
          el.dispatchEvent(new Event('change', { bubbles: true }));
          el.dispatchEvent(new Event('input',  { bubbles: true }));
          break;
        }
      }
    });

    // 入庫：多捲料列表
    if (intent === 'stock_in' && Array.isArray(params.rolls)) {
      params.rolls.forEach((roll, idx) => {
        const rollNoEl = document.querySelector(`input[name="roll_no_${idx + 1}"]`);
        const weightEl = document.querySelector(`input[name="weight_kg_${idx + 1}"]`);
        if (rollNoEl && roll.roll_no) rollNoEl.value = roll.roll_no;
        if (weightEl && roll.weight_kg) weightEl.value = roll.weight_kg;
      });
    }
  }

  // -------------------------------------------------------------------------
  // 發送訊息
  // -------------------------------------------------------------------------
  // -------------------------------------------------------------------------
  // 發送訊息
  // -------------------------------------------------------------------------
  async function sendMessage() {
    if (!inputEl) return;
    const text = inputEl.value.trim();
    // 如果既沒文字也沒圖片，就不送出
    const file = lastSelectedFile || (fileInputEl ? fileInputEl.files[0] : null);

    if (!text && !file) return;

    inputEl.value = '';
    inputEl.disabled = true;
    if (sendBtn) sendBtn.disabled = true;
    if (uploadBtn) uploadBtn.disabled = true;

    // 如果有文字就顯示在對話框，如果有圖片也顯示（文字優先）
    appendMessage('user', text || (getLang() === 'vi' ? 'Đã tải ảnh lên' : '上傳圖片中...'));
    const spinner = appendSpinner();

    try {
      // 僅傳送最近 10 則訊息作為上下文
      const history = chatHistory.slice(-10);
      let resp;

      if (file) {
        // 使用 FormData 傳輸圖片
        const formData = new FormData();
        formData.append('text', text);
        formData.append('lang', getLang());
        formData.append('history', JSON.stringify(history));
        formData.append('image', file);

        resp = await fetch('/api/ai/chat', {
          method: 'POST',
          body: formData,
          credentials: 'same-origin',
        });
        
        // 清除選擇的文件與預覽
        clearFile();
      } else {
        // 純文字 JSON
        resp = await fetch('/api/ai/chat', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ 
            text, 
            lang: getLang(),
            history: history 
          }),
          credentials: 'same-origin',
        });
      }

      removeSpinner();

      if (resp.status === 403) {
        appendMessage('ai', '❌ 權限拒絕 / Không có quyền truy cập.');
        return;
      }
      if (resp.status === 503) {
        appendMessage('ai', '⚠️ AI 模型尚未就緒，請稍後再試。/ Mô hình AI chưa sẵn sàng.');
        return;
      }

      const data = await resp.json();
      appendMessage('ai', data.reply || '(無回應)');

      // 自動填表
      if (data.status === 'ready' && data.intent && data.params) {
        autofill(data.intent, data.params);
        appendMessage('ai', getLang() === 'vi'
          ? 'Dữ liệu đã được điền vào biểu mẫu. Vui lòng kiểm tra và gửi.'
          : '已自動填入表單，請確認後送出。');
      }
    } catch (err) {
      removeSpinner();
      appendMessage('ai', `網路錯誤 / Lỗi mạng: ${err.message}`);
    } finally {
      inputEl.disabled = false;
      if (sendBtn) sendBtn.disabled = false;
      if (uploadBtn) uploadBtn.disabled = false;
      inputEl.focus();
    }
  }

  // -------------------------------------------------------------------------
  // 圖片上傳 & 預覽
  // -------------------------------------------------------------------------
  let uploadBtn, fileInputEl, previewContainer, previewImg, clearFileBtn;

  function initUploadRefs() {
    uploadBtn        = document.getElementById('ai-chat-upload-btn');
    fileInputEl      = document.getElementById('ai-chat-file');
    previewContainer = document.getElementById('ai-chat-preview-container');
    previewImg       = document.getElementById('ai-chat-preview-img');
    clearFileBtn     = document.getElementById('ai-chat-clear-file');
    
    if (uploadBtn && fileInputEl) {
      uploadBtn.addEventListener('click', () => fileInputEl.click());
    }

    if (fileInputEl) {
      fileInputEl.addEventListener('change', (e) => {
        handleFileSelect(e.target.files[0]);
      });
    }

    if (clearFileBtn) {
      clearFileBtn.addEventListener('click', clearFile);
    }

    // 剪貼簿貼上 (CTRL+V)
    if (inputEl) {
      inputEl.addEventListener('paste', (e) => {
        const items = (e.clipboardData || e.originalEvent.clipboardData).items;
        for (const item of items) {
          if (item.type.indexOf('image') !== -1) {
            const file = item.getAsFile();
            handleFileSelect(file);
            break; 
          }
        }
      });
    }
  }

  function handleFileSelect(file) {
    if (file && file.type.startsWith('image/')) {
      const reader = new FileReader();
      reader.onload = (re) => {
        if (previewImg) previewImg.src = re.target.result;
        if (previewContainer) previewContainer.classList.remove('hidden');
        if (inputEl) inputEl.focus();
      };
      reader.readAsDataURL(file);
      
      // 同步到 fileInputEl 讓 sendMessage 能讀到
      // 注意：直接設定 files 是受限的，但我們可以修改 sendMessage 讓它優先讀取快取的文件物件
      lastSelectedFile = file;
    }
  }

  let lastSelectedFile = null;

  function clearFile() {
    if (fileInputEl) fileInputEl.value = '';
    lastSelectedFile = null;
    if (previewContainer) previewContainer.classList.add('hidden');
    if (previewImg) previewImg.src = '';
  }


  // -------------------------------------------------------------------------
  // 事件繫結（事件委派至 document）
  // -------------------------------------------------------------------------
  document.addEventListener('DOMContentLoaded', function () {
    initRefs();
    initUploadRefs();

    if (!panel) return;  // 非 operator 頁面，widget 不存在
    
    // 讀取持久化紀錄
    loadHistory();

    // 面板開關（浮動按鈕 & 面板內關閉按鈕）
    document.addEventListener('click', function (e) {
      const action = e.target.closest('[data-action]');
      if (!action) return;
      if (action.dataset.action === 'ai-chat-toggle') togglePanel();
      if (action.dataset.action === 'ai-chat-send') sendMessage();
      if (action.dataset.action === 'ai-chat-clear') clearHistory();
    });

    // 鍵盤 Enter 送出
    document.addEventListener('keydown', function (e) {
      if (e.key === 'Enter' && document.activeElement === inputEl) {
        e.preventDefault();
        sendMessage();
      }
    });
  });

})();
