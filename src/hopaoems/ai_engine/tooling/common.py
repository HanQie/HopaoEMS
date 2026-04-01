from __future__ import annotations


class ToolContext:
    """Tool 執行時的上下文環境。"""

    def __init__(
        self,
        db_path: str,
        lang: str,
        username: str,
        conversation_id: str,
        processor,
        image_bytes: bytes | None = None,
        current_entity: dict | None = None,
    ):
        self.db_path = db_path
        self.lang = lang
        self.username = username
        self.conversation_id = conversation_id
        self.processor = processor
        self.image_bytes = image_bytes
        self.current_entity = current_entity or {}

    def get_image(self, image_id: str | None = None) -> bytes | None:
        """
        取得圖片二進位資料。
        若指定 image_id，則從用戶專屬的微庫資料夾讀取對應的檔案。
        若無指定 image_id：
            已上傳新圖：回傳 self.image_bytes
            未上傳新圖：嘗試抓取微庫中最新的一張圖（作為 Fallback）
        """
        import os
        from flask import current_app

        temp_dir = os.path.join(
            current_app.root_path,
            "static",
            "uploads",
            "temp_ai",
            self.username,
            self.conversation_id,
        )

        # 1. 指定 ID 讀取
        if image_id:
            safe_id = os.path.basename(image_id)  # 防禦目錄遍歷
            file_path = os.path.join(temp_dir, safe_id)
            if os.path.isfile(file_path):
                try:
                    with open(file_path, "rb") as f:
                        return f.read()
                except Exception as e:
                    current_app.logger.warning(f"無法讀取微庫圖片 {image_id}: {e}")
            return None

        # 2. 沒指定 ID 但本次上傳了新圖片
        if self.image_bytes:
            return self.image_bytes

        # 3. 沒指定且沒上傳，Fallback 到最新的一張圖片
        if os.path.isdir(temp_dir):
            try:
                files = [f for f in os.listdir(temp_dir) if f.lower().endswith(('.jpg', '.jpeg', '.png'))]
                if files:
                    # 檔名格式為 img_{timestamp}.jpg，直接對檔名排序取最後一個即為最新
                    files.sort()
                    latest_file = files[-1]
                    file_path = os.path.join(temp_dir, latest_file)
                    with open(file_path, "rb") as f:
                        return f.read()
            except Exception as e:
                current_app.logger.warning(f"無法讀取最新的微庫圖片: {e}")

        return None
