# 頁面與 UI 佈局規範 (Pages Architecture)

HopaoEMS v2 的 UI 設計旨在提供專業、高密度的資訊呈現。所有的 HTML UI 都必須遵守 `ui_components.html` 內的巨集標準，禁止各頁面自行刻畫 CSS。

## 1. 核心頁面佈局規則
- **雙欄式結構 (Split Pane)**: 適用於建立/編輯頁面。左側放置預覽圖標 (Image Viewer/Tree)，右側放置資料表單。
- **單頁寬版 (Full-width Document)**: 適用於 Dossier (案卷) 頁面與數據密集型報表 (如 Dashboard, History)。
- **工具列 (Toolbar)**: 所有列表或明細頁面頂部都必須有統一的 Toolbar (使用 `ui_page_header` 或 `ui_toolbar` 巨集)。包含標題、搜尋框與主要操作按鈕 (Primary Button)。

---

## 2. 獨立模組頁面詳解

### 布種探索器 (Fabric Explorer)
- **URL**: `/fabric/explorer`
- **目的**: 以樹狀結構展現布種 (Fabric) -> 缸號 (Cylinder) -> 布卷 (Roll) 的階層關係。
- **Layout**: 全寬度卡片列表，採內嵌式對話框風格。
- **核心操作**:
  - Stock In (入庫)
  - 手動庫存校正 (Adjust Stock)
  - 檢視卷歷史 (History Badge)
- **RBAC**: Viewer 無法看到新增、修改與操作按鈕。
- **i18n**: 全面使用 `fabric.explorer.*` 鍵值。

### 樣品控制台 (Sample Dashboard & View)
- **URL**: `/sample/<id>`
- **目的**: 唯讀的「打樣規格與對色」卷宗指南 (Dossier)。
- **Layout**: **頂部分區**：基本中繼資料；**中部分區**：高解析度打樣圖 (支援 Pinch-to-zoom) 與 Color Pick 指示；**底部分區**：色彩對比資料表 (L*a*b* 演算法比較)。
- **核心操作**: Viewer 模式僅能瀏覽；若從 `/sample/<id>/edit` 進入，則可拖拉更換預覽圖，並點擊圖片紀錄顏色。

### 訂單中心 (Order Form & Dossier)
- **URL**: `/order/<id>`
- **目的**: 匯總顯示單一訂單下的所有子任務進度、狀態分析，並提供刪除、狀態重新整理。
- **Layout**: 
  1. Header：訂單號碼、狀態徽章與接收/預計日期。
  2. Summary Cards：統計生產/水洗/出貨進度指標。
  3. Items List：明細列表，包含子任務進度條。
- **核心操作**: 若子任務「未出現在洗清」中被修改，可以觸發 Undo。
- **RBAC**: Viewer 僅能觀看報表，不能增刪品項。

### 生產工作站 (Production Task Workstation)
- **URL**: `/production/task/<id>`
- **目的**: 機台操作員的主要工作畫面。負責綁定布卷並紀錄列印長度。
- **Layout**:
  - 左側：任務明細與要求打卡規格。
  - 右下：快速產生耗材表單 (`/produce` 內嵌表單)。
  - 右上：歷史生產記錄 (`Production Logs`)。
- **核心操作**: 
  - Produce (打卡消耗)：掃描/選擇布卷與輸入米數。
  - Done (完工)：鎖定該任務。防呆機制：剩餘目標必須為 0 且未水洗布卷清理完畢。
- **RBAC**: Operator 限定。

### 水洗集散地 (Wash Station)
- **URL**: `/wash/`
- **目的**: 將零散的 `production_logs` 依布缸 (Vat Code) 群組化打包成缸進行後方化學處理。
- **Layout**: 動態分組式卡片集群 (Masonry Layout)。
- **核心操作**: 
  - Group Selection (全選該缸的卷數)
  - Send to Wash (Commit Session)
  - 歷史列表中的 Undo (撤銷水洗狀態)
- **RBAC**: Viewer 可看清單，但無法打勾打包。

---

## 3. UI 巨集 (Macros) 速查表
- `ui_page_header(title, actions=None, badges=None)`: 頁面大標題。
- `ui_card(title, body)`: 白底圓角卡片。
- `ui_table(headers, rows, empty_text)`: 統一風格的資料表。
- `ui_badge(text, variant)`: 狀態標籤 (success, warning, info, danger, text-muted)。
- `ui_progress_bar(pct, variant)`: 任務進度條組件。
- `ui_empty_state(icon, title, desc)`: 無資料時的佔位區域。
