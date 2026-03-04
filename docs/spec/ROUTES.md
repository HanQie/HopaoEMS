# 系統路由設計 (Routes Architecture)

本文件列出所有的 Blueprint endpoints、其對應的功能與權限要求。所有路由預設回傳 HTML 頁面（若失敗則使用 Flash 重新導向），部分支援 POST 操作作為表單提交通道。

## Blueprint: Auth (`/auth`)
| Route | Method | 角色權限 | 目的 | 主要輸入/輸出 | 關聯資料 (Table) |
| --- | --- | --- | --- | --- | --- |
| `/login` | GET, POST | 公開 | 使用者登入 | Form: `username`, `password` | `users` |
| `/logout` | POST | 登入者 | 登出並清除會話 | N/A | N/A |

## Blueprint: Main (`/`)
| Route | Method | 角色權限 | 目的 | 主要輸入/輸出 | 關聯資料 (Table) |
| --- | --- | --- | --- | --- | --- |
| `/` | GET | Viewer+ | 首頁 / Dashboard | N/A | 各模組統整 |
| `/i18n/set/<lang>` | GET | 公開 | 切換使用語系 | Query: `next` URL | N/A |
| `/data/uploads/samples/<path>` | GET | 登入者 | 獲取樣品上傳圖檔 | URL param: `filename` | N/A (File System) |
| `/data/swatches/<hex_code>.png` | GET | 登入者 | 生成色塊圖片 | URL param: `hex_code` | N/A |

## Blueprint: Fabric (`/fabric`)
| Route | Method | 角色權限 | 目的 | 主要輸入/輸出 | 關聯資料 (Table) |
| --- | --- | --- | --- | --- | --- |
| `/` | GET | Viewer+ | 布種清單 | N/A | `fabrics` |
| `/explorer` | GET | Viewer+ | 布種樹狀探索器 | N/A | `fabrics`, `cylinders`, `rolls` |
| `/new` | GET, POST | Operator | 建立新布種 | Form: `fabric_code`, `width_cm`, etc. | `fabrics` |
| `/<id>/edit` | GET, POST | Operator | 編輯布種資訊 | Form: 布種欄位 | `fabrics` |
| `/cylinder/<id>/edit` | GET, POST | Operator | 編輯缸號 | Form: `cylinder_no` | `cylinders` |
| `/roll/<id>/edit` | GET, POST | Operator | 編輯布卷長度/狀態 | Form: `lengths`, `status`, `remark` | `rolls`, `roll_history` |
| `/roll/<id>/adjust-stock` | GET, POST | Operator | 手動增減布卷庫存 | Form: `adjustment`, `note` | `rolls`, `roll_history` |
| `/roll/<id>/deplete` | GET, POST | Operator | 標記布卷為耗盡 | Form: (確認用) | `rolls`, `roll_history` |
| `/stock-in` | GET | Operator | 批次入庫介面 | N/A | N/A |
| `/stock-in/commit` | POST | Operator | 提交入庫資料 (UI) | Form: `items[...]` | `fabrics`, `cylinders`, `rolls` |
| `/stock-in/import-xlsx` | POST | Operator | 解析 Excel 批次上傳 | File: `file` -> JSON 回傳 | N/A (Parser) |

## Blueprint: Sample (`/sample`)
| Route | Method | 角色權限 | 目的 | 主要輸入/輸出 | 關聯資料 (Table) |
| --- | --- | --- | --- | --- | --- |
| `/` | GET | Viewer+ | 樣品清單 | Query: `q`, `page` | `samples` |
| `/new` | GET, POST | Operator | 建立樣品 | Form: 樣品欄位, `asset` 檔案 | `samples` |
| `/<id>` | GET | Viewer+ | 樣品報告 (唯讀) | N/A | `samples`, `sample_color_map` |
| `/<id>/edit` | GET, POST | Operator | 編輯樣品 (多欄) | Form: `metadata`, `colors` | `samples`, `sample_color_map` |
| `/<id>/delete` | GET, POST | Operator | 刪除樣品與圖檔 | N/A | `samples`, `sample_color_map` |
| `/<id>/pick-color` | POST | Operator | 記錄選中點顏色 | JSON: `x`, `y`, `r`, `g`, `b`, `hex` | `sample_color_map` |

## Blueprint: Order (`/order`)
| Route | Method | 角色權限 | 目的 | 主要輸入/輸出 | 關聯資料 (Table) |
| --- | --- | --- | --- | --- | --- |
| `/` | GET | Viewer+ | 訂單清單 | Query: `status`, `q`, `page` | `orders` |
| `/new` | GET, POST | Operator | 建單與品項 | Form: 訂單主檔, `items[...]` | `orders`, `order_items`, `production_tasks` |
| `/<id>` | GET | Viewer+ | 訂單詳情 (Dossier) | N/A | `orders`, `order_items`, `tasks` |
| `/<id>/edit` | GET, POST | Operator | 編輯訂單 | Form: 訂單主檔, `items[...]` | `orders`, `order_items` |
| `/<id>/delete` | GET, POST | Operator | 刪除訂單 | N/A | `orders` |
| `/item/<id>/delete` | GET, POST | Operator | 刪除單一品項 | N/A | `order_items`, `production_tasks` |
| `/task/<id>/reopen` | POST | Operator | 重開已完成之任務 | N/A | `production_tasks` |

## Blueprint: Production (`/production`)
| Route | Method | 角色權限 | 目的 | 主要輸入/輸出 | 關聯資料 (Table) |
| --- | --- | --- | --- | --- | --- |
| `/` | GET | Viewer+ | 生產看板 (任務隊列) | Query: `page` | `production_tasks` |
| `/task/<id>` | GET | Viewer+ | 任務工作站 (執行頁) | N/A | `production_tasks`, `production_logs` |
| `/task/<id>/produce` | GET, POST | Operator | 記錄列印消耗 (打卡) | Form: `roll_id`, `printed_length` | `production_logs`, `rolls` |
| `/task/<id>/done` | POST | Operator | 標記任務完工 | N/A | `production_tasks` |
| `/log/<id>/edit` | GET, POST | Operator | 編輯生產紀錄長度/備註 | Form: `length`, `note`, `force_undo`  | `production_logs`, `rolls` |
| `/log/<id>/delete` | GET, POST | Operator | 刪除紀錄並退回布長 | Form: (確認用) | `production_logs`, `rolls` |
| `/test-consume` | GET, POST | Operator | 試車消耗紀錄 | Form: `roll_id`, `length`, `mark_empty` | `rolls`, `roll_history` |

## Blueprint: Wash (`/wash`)
| Route | Method | 角色權限 | 目的 | 主要輸入/輸出 | 關聯資料 (Table) |
| --- | --- | --- | --- | --- | --- |
| `/` | GET | Viewer+ | 水洗工作站 (缸聚合) | N/A | `production_logs` |
| `/register/<vat_code>` | GET | Operator | 打包成缸確認頁 | N/A | `production_logs` |
| `/commit` | POST | Operator | 送入水洗 (入session) | Form: `vat_code`, `log_ids[]` | `wash_sessions`, `production_logs` |
| `/history` | GET | Viewer+ | 水洗歷史清單 | Query: `q`, `page` | `wash_sessions` |
| `/session/<id>` | GET | Viewer+ | 缸紀錄詳情 | N/A | `wash_sessions`, `logs` |
| `/revoke/<id>` | GET, POST | Operator | 撤銷成缸 | N/A | `wash_sessions`, `production_logs` |
| `/log/<id>/undo` | GET, POST | Operator | 單卷解鎖 (從缸中抽出) | Query/Form: `next` URL | `wash_sessions`, `production_logs` |

## Blueprint: Ink (`/ink`) & Settings (`/settings`)
| Route | Method | 角色權限 | 目的 | 主要輸入/輸出 | 關聯資料 (Table) |
| --- | --- | --- | --- | --- | --- |
| `/ink/` | GET | Viewer+ | 墨水庫存清單 | N/A | `inks` |
| `/ink/new` | GET, POST | Operator | 新增墨水收支 | Form: 墨水欄位 | `inks` |
| `/ink/<id>/edit` | GET, POST | Operator | 編輯收支 | Form: 墨水欄位 | `inks` |
| `/settings/` | GET | Viewer+ | 參數設定 (首頁) | N/A | N/A |
| `/settings/activity` | GET | Viewer+ | 系統操作日誌 | Query: `page` | `audit_logs` |
