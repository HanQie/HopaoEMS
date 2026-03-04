# HopaoEMS v2 系統架構與開發約束 (Architecture & Constraints)

HopaoEMS v2 是一套基於 Python Flask、SQLite 與 Jinja2 打造的現代化企業管理系統。為確保系統長期穩定、UI 一致且具備高度可維護性，本系統嚴格遵守以下架構規範與開發合約。

## 1. 核心技術棧 (Tech Stack)
- **後端**: Python 3.x, Flask (Blueprint 路由架構)
- **資料庫**: SQLite (使用純 SQL 進行查詢與異動，不依賴龐大的 ORM)
- **前端生成**: Server-Side Rendering (SSR) via Jinja2
- **前端互動**: Vanilla JavaScript (無 React/Vue 依賴)
- **樣式系統**: CSS Modules / 自定義 Utility (嚴格採用預設合約樣式)

## 2. UI 開發合約 (UI Contract)
所有頁面開發**必須**遵守以下嚴格規則，禁止任何例外：
- **Macro-Only 規則**: 所有的 UI 元件（表單、按鈕、表格、徽章、導航）必須使用 `src/hopaoems/templates/macros/` 底下的 Jinja2 Macros 進行渲染。
- **禁止 Inline CSS**: 禁止在 HTML 中寫 `style="..."`。
- **禁止任意 HTML 注入**: 前端 JavaScript **嚴禁**使用 `innerHTML`，所有 DOM 更新須透過 DOM API (如 `createElement`, `textContent`)，以防範 XSS 並確保架構清晰。
- **佈局合約**: 所有視圖必須繼承 `base.html` 並使用兩欄式佈局或標準 Dashboard 格式。

## 3. 前端 JavaScript 合約 (JavaScript Contract)
- **職責分離**: JS 僅負責「漸進式增強 (Progressive Enhancement)」，如 Modal 交互、客戶端表單驗證、動態行列增減。
- **無狀態化**: 不在前端維護與後端重疊的狀態，資料唯一來源為伺服器。
- **事件委派**: 盡量使用 Event Delegation，避免在動態生成的元素上直接綁定事件。

## 4. 國際化與語系合約 (i18n)
- **全面支援**: 系統全面實施 i18n，**嚴禁**在 HTML 模板、Python 程式碼或 JavaScript 中寫死中文或英文文字。
- **調用方式**: 
  - 模板中：使用 `{{ t('key.name') }}`
  - 後端中：使用 `from ..services.i18n import t`
  - 前端中：由後端透過 JSON/Data 屬性將翻譯文案傳遞給 JS。
- **種子檔**: 所有語系定義必須記錄於 `src/hopaoems/i18n/seed.{lang}.json`。

## 5. 角色與存取控制 (RBAC)
系統區分兩種核心角色：
1. **Viewer (唯讀使用者)**: 
   - 僅可瀏覽儀表板、清單與明細。
   - **防線一 (UI)**: 所有 Edit/Delete/New 按鈕對 Viewer 隱藏。
   - **防線二 (API)**: 任何 POST 或修改狀態的 Route 皆會依賴 `@auth_service.operator_required` 阻斷請求。
2. **Operator (操作員)**: 
   - 具備所有的 CRUD 與狀態變更權限。
   - 原 admin 角色已合併至 operator，簡化權限模型。

## 6. 資料庫存取哲學
- **Service & Repo Layer**: Route 不可直接執行 SQL。必須呼叫 `services/*_repo.py` 處理商業邏輯與資料庫存取。
- **No ORM**: 為了效能與可控性，完全使用 `sqlite3.Row` 及原生 SQL 語法。
