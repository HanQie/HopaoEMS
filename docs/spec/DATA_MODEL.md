# 資料模型與關係 (Data Model & ERD)

HopaoEMS v2 的核心資料庫架構設計依賴關聯式結構，確保生產追蹤中每個布卷、任務及操作皆具備一致的溯源能力 (Traceability)。

## 1. 核心實體層次 (Entities Hierarchy)

### 布料與庫存系統 (Inventory)
- **`fabrics` (布種)**: 定義一種布料規格 (布號、材質、幅寬、碼重)。
- **`cylinders` (布缸)**: 隸屬於特定布種，代表同一批次染整或加工的一群布卷。
- **`rolls` (布卷)**: 基礎物理庫存單位。每卷具備獨一無二的長度與狀態。
  - **約束 (Invariant)**: `(cylinder_id, roll_no)` 必須是唯一組合 (`UNIQUE INDEX`)。

### 訂單與任務分發 (Order & Planning)
- **`orders` (訂單主檔)**: 客戶下發的生產訂單，包含交期與整體狀態。
- **`order_items` (訂單品項)**: 指定要用何種布種 (搭配哪一版`sample`) 印多少目標長度。
- **`production_tasks` (生產任務)**: 系統自動根據 `order_items` 生成的工作包。這是一線操作員的主畫面標的。

### 執行與後處理 (Execution & Post-Processing)
- **`production_logs` (生產日誌 / 打卡)**: 操作員於印花機台上完成一卷列印時建立。其將**物理庫存的「布卷」**與**邏輯計劃的「任務」**連結在一起。
  - 這張表會同時扣減 `rolls.length` 並增加 `tasks.printed_length`。
- **`wash_sessions` (水洗缸集)**: 生產下來的布卷依照缸號聚合的批次處理作業。
- **`roll_history` (卷宗軌跡)**: 記錄庫存調撥、消耗、試跑等歷史節點。

---

## 2. 核心實體關聯圖 (ER Diagram Concept)

```text
[ Sample ] <----(1:N)---- [ OrderItem ] ----(N:1)----> [ Order ]
   ^                             |
   |                             | (1:1)
   v                             v
[ ColorMap ]              [ ProductionTask ]
                                 ^
                                 | (1:N)
                                 |
[ Fabric ]                [ ProductionLog ]
   ^                             |
   | (1:N)                       | (N:1)    +-------------------+
   v                             v          |                   v
[ Cylinder ] <--(1:N)---> [ Roll (庫存) ]   |           [ WashSession ]
                             |              |
                             v              |
                      [ RollHistory ] <-----+
```

---

## 3. 關鍵商業邏輯約束 (Business Logic Invariants)

為保資料一致性，在 Service 層需要遵守下列鐵律：

1. **不可修改性規則 (Immutability of Logs)**: 
   - 一旦 `production_logs` 被綁定到 `wash_sessions` (即 `washed_at` 不為 NULL)，該生產日誌**將被永久鎖死** (`is_editable = false`)。不允許直接修改或刪除。若需修改，必須先在水洗站執行「退洗 (Undo)」。
2. **完工檢查鎖 (Completion Guard)**:
   - 標記一個 `ProductionTask` 為 `done` 的前置條件：必須有至少一條生產紀錄 `>= 1`、累積長度達標、且**沒有任何紀錄處於 "unwashed" 狀態**。
3. **布卷耗盡機制 (Roll Depletion)**:
   - 若打卡時勾選 `roll_depleted`，該捲布的庫存長度會被清零(`0`)，且狀態會變更為 `empty`。
4. **刪除級聯與防禦 (Deletion Defense)**:
   - 若訂單已經擁有執行中的日誌記錄 (`logs`)，該訂單與其所屬任務不允許被硬刪除。
   - `sqlite` 未使用 FOREIGN KEY CASCADE 以防在 UI 上誤點。所有刪除前必須經程式碼層檢驗 (例如 `order_repo.can_delete_order()`)。
