import json
import os

langs = ["en", "zh-TW", "vi"]
base_dir = "src/hopaoems/i18n"
new_keys = {
    "common.search_placeholder": "Search...",
    "ink.search.placeholder": "Search ink...",
    "order.search.placeholder": "Search orders...",
    "production.empty.no_active_tasks": "No active tasks",
    "production.fields.task_info": "Task Info",
    "production.status.ready": "Ready"
}

for lang in langs:
    file_path = os.path.join(base_dir, f"seed.{lang}.json")
    if os.path.exists(file_path):
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        for k, v in new_keys.items():
            if k not in data:
                data[k] = v
                
        # Handle dict sorting. The first key might be "__sources__"
        sources = data.pop("__sources__", {})
        sorted_keys = sorted(data.keys())
        final_dict = {"__sources__": sources}
        for k in sorted_keys:
            final_dict[k] = data[k]
            
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(final_dict, f, ensure_ascii=False, indent=2)

print("Added keys to seed files.")
