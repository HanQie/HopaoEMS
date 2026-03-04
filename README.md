# HopaoEMS v2

HopaoEMS v2 是一個為紡織/染整業量身打造的現代化生產管理系統，涵蓋從布布建檔、樣品對色、訂單建立、生產任務派發到後處理（水洗）的完整生命週期追蹤。

## 技術棧 (Tech Stack)
- **後端**: Python (Flask) + SQLite
- **前端**: Server-Side Rendering (Jinja2) + Vanilla JS (DOM Manipulation)
- **樣式**: Vanilla CSS (基於自定義的組件設計系統)

## 快速上手 (Quick Start)

### 啟動應用程式
請確保已經建立並進入 Python 虛擬環境 (`.venv`)，或系統已安裝必要的相依套件 (`pip install -r requirements.txt`)。

直接點擊或在終端機執行：
```cmd
boot.bat
```
伺服器將會啟動並運行於 `http://localhost:5000`。
*注意：本應用程式依賴本機 `instance/` 資料夾來儲存 SQLite 資料與上傳檔案。*

### 執行品質閘門測試 (Quality Gates)
本專案具有極高的品質要求，包含嚴格的 UI 約束、i18n 校驗以及端到端 (E2E) 測試。要驗證系統完整性，請執行：
```cmd
gate.bat
```
如果 `gate.bat` 執行結果為 `Exit code: 0`，代表系統通過了所有合約校驗、巨集相容性與核心業務流程測試。

## 核心模組導覽

1. **Dashboard (首頁)**: 提供當前生產指標、未完成任務總覽與快速跳轉。
2. **Fabric (布匹管理)**: 管理原料庫存。包含布種建檔 (Stock-in)、缸號綁定、與布捲 (Roll) 庫存。
3. **Sample (樣品管理)**: 打樣紀錄與電子檔案夾。追蹤樣品規格並記錄客戶回饋與顏色校正 (Pick Color / L*a*b*)。
4. **Order (訂單管理)**: 建立客戶訂單，綁定布種與樣品，並自動生成下游客的生產任務。
5. **Production (生產作業)**: 生產線執行看板。記錄每一卷布的打印長度，並生成生產日誌。
6. **Wash (水洗處理)**: 後處理工作站。將生產完畢的布卷打包成缸 (Vat) 進行水洗，並記錄狀態。
7. **Ink (墨水管理)**: 記錄庫存墨水的消耗與進貨。
8. **Settings (系統設定)**: 切換多國語系介面，並可查閱操作日誌 (Activity Audit Logs)。

## 開發守則與合約摘要
請開發者務必閱讀 `docs/spec/` 下的詳細規格文件。確保所有開發皆遵守：
- **Macro-Only UI**: 禁止直接撰寫 HTML 表格或按鈕，必須調用 `ui_components.html` 內的巨集。
- **i18n Only**: 所有字串必須支援國際化映射，嚴禁 Hardcode 文字。
- **Progressive Enhancement**: JS 僅用於輔助互動，不依賴龐大的客戶端框架。

> 欲了解更多底層實作細節，請參閱：
> - `docs/spec/ARCHITECTURE.md` (技術架構與約束)
> - `docs/spec/DATA_MODEL.md` (資料庫 ER 模型)
> - `docs/spec/ROUTES.md` (詳細路由與權限)
> - `docs/spec/PAGES.md` (頁面結構與操作流程)
