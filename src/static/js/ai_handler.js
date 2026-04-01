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

  function getCurrentEntity() {
    const hint = document.getElementById('ai-current-entity');
    if (!hint) return null;
    const { entityType, entityId, sampleNo, title } = hint.dataset;
    if (!entityType || !entityId) return null;
    return {
      type: entityType,
      id: Number(entityId),
      sample_no: sampleNo || '',
      title: title || '',
    };
  }

  function cssEscape(value) {
    if (window.CSS && typeof window.CSS.escape === 'function') {
      return window.CSS.escape(value);
    }
    return String(value).replace(/["\\]/g, '\\$&');
  }

  function findFieldLabel(el) {
    if (!el) return '';
    const elId = el.getAttribute('id');
    if (elId) {
      const byFor = document.querySelector(`label[for="${cssEscape(elId)}"]`);
      if (byFor && byFor.textContent) return byFor.textContent.trim();
    }

    const closestLabel = el.closest('label');
    if (closestLabel && closestLabel.textContent) return closestLabel.textContent.trim();

    const wrappers = ['[data-hook*="field"]', '.ui-field', '.form-field', '.field'];
    for (const selector of wrappers) {
      const wrapper = el.closest(selector);
      if (!wrapper) continue;
      const label = wrapper.querySelector('label');
      if (label && label.textContent) return label.textContent.trim();
    }

    const prev = el.previousElementSibling;
    if (prev && prev.tagName === 'LABEL' && prev.textContent) {
      return prev.textContent.trim();
    }

    return '';
  }

  function getFieldManifest() {
    const manifestEl = document.getElementById('ai-field-manifest');
    if (manifestEl) {
      try {
        const raw = manifestEl.textContent || '{}';
        const parsed = JSON.parse(raw);
        if (parsed && typeof parsed === 'object') return parsed;
      } catch (e) {
        console.error('Failed to parse ai-field-manifest', e);
      }
    }

    const form = document.querySelector('form');
    if (!form) return null;
    const fields = [];
    form.querySelectorAll('input[name], select[name], textarea[name]').forEach((el) => {
      const name = (el.getAttribute('name') || '').trim();
      const type = (el.getAttribute('type') || el.tagName || '').toLowerCase();
      if (!name || type === 'hidden' || type === 'file') return;
      const label = findFieldLabel(el) || el.getAttribute('aria-label') || el.getAttribute('placeholder') || name;
      const aliases = [label, name.replace(/_/g, ' ')];
      const placeholder = (el.getAttribute('placeholder') || '').trim();
      if (placeholder && placeholder !== name) aliases.push(placeholder);
      fields.push({
        name,
        label,
        type,
        aliases: aliases.filter(Boolean),
      });
    });
    if (!fields.length) return null;
    return { page_type: 'generic_form', fields, groups: [] };
  }

  // -------------------------------------------------------------------------
  // 持久化 (SessionStorage)
  // -------------------------------------------------------------------------
  const STORAGE_KEY_HISTORY = 'ai_chat_history';
  const STORAGE_KEY_STATE = 'ai_chat_isOpen';
  const STORAGE_KEY_CONVERSATION = 'ai_chat_conversation_id';

  let chatHistory = [];

  function createConversationId() {
    if (window.crypto && typeof window.crypto.randomUUID === 'function') {
      return window.crypto.randomUUID();
    }
    return `conv_${Date.now()}_${Math.random().toString(36).slice(2, 10)}`;
  }

  function getConversationId() {
    let id = sessionStorage.getItem(STORAGE_KEY_CONVERSATION);
    if (!id) {
      id = createConversationId();
      sessionStorage.setItem(STORAGE_KEY_CONVERSATION, id);
    }
    return id;
  }

  function resetConversation() {
    const id = createConversationId();
    sessionStorage.setItem(STORAGE_KEY_CONVERSATION, id);
    return id;
  }

  function loadHistory() {
    try {
      const saved = sessionStorage.getItem(STORAGE_KEY_HISTORY);
      if (saved) {
        chatHistory = JSON.parse(saved);
        chatHistory.forEach(msg => {
          renderMessage(msg.role, msg.text, false, msg.meta || null);
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
    resetConversation();
    saveHistory();
    clearFile();
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
  function renderMessage(role, text, save = true, meta = null) {
    if (!messagesEl) return;
    const hasReasoning = Boolean(meta && meta.reasoning_summary && meta.reasoning_summary.trim());
    const hasToolTrace = Boolean(meta && Array.isArray(meta.tool_trace) && meta.tool_trace.length);
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

    if (role !== 'user' && (hasReasoning || hasToolTrace)) {
      const debugBox = document.createElement('details');
      debugBox.className = 'mt-2 max-w-[85%] rounded-xl border border-amber-200 bg-amber-50/70 px-3 py-2 text-xs text-slate-700';

      const summaryEl = document.createElement('summary');
      summaryEl.className = 'cursor-pointer font-medium text-amber-900';
      summaryEl.textContent = getLang() === 'vi' ? 'Debug reasoning' : 'Debug 推理摘要';
      debugBox.appendChild(summaryEl);

      if (hasReasoning) {
        const reasoningEl = document.createElement('pre');
        reasoningEl.className = 'mt-2 whitespace-pre-wrap break-words text-xs text-slate-700';
        reasoningEl.textContent = meta.reasoning_summary;
        debugBox.appendChild(reasoningEl);
      }

      if (hasToolTrace) {
        const traceEl = document.createElement('pre');
        traceEl.className = 'mt-2 whitespace-pre-wrap break-words text-[11px] text-slate-600';
        traceEl.textContent = meta.tool_trace.map((item, idx) =>
          `${idx + 1}. ${item.tool}\nargs: ${JSON.stringify(item.args, null, 2)}\nresult: ${JSON.stringify(item.result, null, 2)}`
        ).join('\n\n');
        debugBox.appendChild(traceEl);
      }

      wrap.appendChild(debugBox);
    }

    messagesEl.appendChild(wrap);
    messagesEl.scrollTop = messagesEl.scrollHeight;

    if (save) {
      chatHistory.push({ role, text, meta });
      saveHistory();
    }
  }

  function appendMessage(role, text, meta = null) {
    renderMessage(role, text, true, meta);
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

  function autofillSampleForm(params) {
    if (!params) return false;
    let changed = autofillFields(params.sample_fields || {});

    if (autofillFields(params.fields || {})) {
      changed = true;
    }

    if (Array.isArray(params.color_corrections) && params.color_corrections.length) {
      document.dispatchEvent(new CustomEvent('hopao:sample-ai-autofill', {
        detail: {
          color_corrections: params.color_corrections,
          clear_color_corrections: Boolean(params.clear_color_corrections),
        },
      }));
      changed = true;
    }

    if (params.clear_color_corrections && !Array.isArray(params.color_corrections)) {
      document.dispatchEvent(new CustomEvent('hopao:sample-ai-autofill', {
        detail: { color_corrections: [], clear_color_corrections: true },
      }));
      changed = true;
    }

    return changed;
  }

  function autofillFields(fields) {
    if (!fields || typeof fields !== 'object') return false;
    let changed = false;
    Object.entries(fields).forEach(([name, value]) => {
      if (value === null || value === undefined || value === '') return;
      const el = document.querySelector(
        `input[name="${name}"], select[name="${name}"], textarea[name="${name}"]`
      );
      if (!el) return;
      el.value = value;
      el.dispatchEvent(new Event('change', { bubbles: true }));
      el.dispatchEvent(new Event('input', { bubbles: true }));
      changed = true;
    });
    return changed;
  }

  function setNamedFieldValue(name, value, triggerEvents = true) {
    if (value === null || value === undefined || value === '') return false;
    const el = document.querySelector(
      `input[name="${name}"], select[name="${name}"], textarea[name="${name}"]`
    );
    if (!el) return false;
    el.value = value;
    if (triggerEvents) {
      el.dispatchEvent(new Event('change', { bubbles: true }));
      el.dispatchEvent(new Event('input', { bubbles: true }));
    }
    return true;
  }

  function ensureOrderItemRows(count) {
    const root = document.querySelector('[data-hook="order-form-root"]');
    if (!root) return [];
    const container = root.querySelector('[data-hook="items-container"]');
    const addBtn = root.querySelector('[data-action="add-item"]');
    if (!container) return [];
    let rows = Array.from(container.querySelectorAll('[data-hook="order-item-row"]'));
    while (rows.length < count && addBtn) {
      addBtn.click();
      rows = Array.from(container.querySelectorAll('[data-hook="order-item-row"]'));
    }
    return rows;
  }

  function autofillOrderForm(params) {
    if (!params) return false;
    let changed = autofillFields(params.fields || {});
    const items = Array.isArray(params.order_items) ? params.order_items : [];
    if (!items.length) return changed;

    const rows = ensureOrderItemRows(items.length);
    items.forEach((item, idx) => {
      const prefix = `items[${idx}]`;
      if (setNamedFieldValue(`${prefix}[fabric_no]`, item.fabric_no)) changed = true;
      if (setNamedFieldValue(`${prefix}[sample_id]`, item.sample_id)) changed = true;
      if (setNamedFieldValue(`${prefix}[qty]`, item.qty)) changed = true;
      if (setNamedFieldValue(`${prefix}[note]`, item.note)) changed = true;
    });
    return changed;
  }

  function ensureStockInRows(count) {
    const form = document.querySelector('[data-hook="fabric-stockin-form"]');
    if (!form) return [];
    const addBtn = document.querySelector('[data-action="stockin-add-1"]');
    let rows = Array.from(form.querySelectorAll('[data-hook="fabric-stockin-row"]'));
    while (rows.length < count && addBtn) {
      addBtn.click();
      rows = Array.from(form.querySelectorAll('[data-hook="fabric-stockin-row"]'));
    }
    return rows;
  }

  function autofillStockInForm(params) {
    if (!params) return false;
    let changed = false;

    const fields = params.fields || {};
    Object.entries(fields).forEach(([name, value]) => {
      const trigger = name !== 'fabric_id';
      if (setNamedFieldValue(name, value, trigger)) changed = true;
    });

    const rows = Array.isArray(params.stock_in_rows) ? params.stock_in_rows : [];
    if (!rows.length) return changed;

    ensureStockInRows(rows.length);
    rows.forEach((row, idx) => {
      const n = idx + 1;
      if (setNamedFieldValue(`roll_no_${n}`, row.roll_no)) changed = true;
      if (setNamedFieldValue(`weight_kg_${n}`, row.weight_kg)) changed = true;
      if (setNamedFieldValue(`length_m_${n}`, row.length_m)) changed = true;
      if (setNamedFieldValue(`remark_${n}`, row.remark)) changed = true;
      const weightEl = document.querySelector(`input[name="weight_kg_${n}"]`);
      if (weightEl) {
        weightEl.dispatchEvent(new Event('input', { bubbles: true }));
      }
    });
    return changed;
  }

  function autofill(intent, params) {
    if (!params) return;
    if (intent === 'form_fill' && autofillFields(params.fields || {})) {
      return;
    }
    if (intent === 'order_form' && autofillOrderForm(params)) {
      return;
    }
    if (intent === 'stock_in_form' && autofillStockInForm(params)) {
      return;
    }
    if (intent === 'sample_form' || intent === 'sample') {
      if (autofillSampleForm(params)) return;
    }
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
      const currentEntity = getCurrentEntity();
      const fieldManifest = getFieldManifest();
      let resp;

      if (file) {
        // 使用 FormData 傳輸圖片
        const formData = new FormData();
        formData.append('text', text);
        formData.append('lang', getLang());
        formData.append('conversation_id', getConversationId());
        formData.append('history', JSON.stringify(history));
        if (currentEntity) formData.append('current_entity', JSON.stringify(currentEntity));
        if (fieldManifest) formData.append('field_manifest', JSON.stringify(fieldManifest));
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
            conversation_id: getConversationId(),
            history: history,
            current_entity: currentEntity,
            field_manifest: fieldManifest,
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
      let data = null;
      const contentType = resp.headers.get('content-type') || '';
      if (contentType.includes('application/json')) {
        data = await resp.json();
      } else {
        const rawText = await resp.text();
        const shortText = rawText.replace(/<[^>]+>/g, ' ').replace(/\s+/g, ' ').trim();
        appendMessage('ai', `伺服器錯誤 / Lỗi máy chủ: ${shortText.slice(0, 180) || resp.statusText || 'Unexpected response'}`);
        return;
      }

      if (!resp.ok) {
        appendMessage('ai', data.reply || data.message || `伺服器錯誤 / Lỗi máy chủ: ${resp.status}`);
        return;
      }

      appendMessage('ai', data.reply || '(無回應)', {
        reasoning_summary: data.reasoning_summary || data.thinking_process || '',
        tool_trace: data.tool_trace || [],
      });

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
