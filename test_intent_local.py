# -*- coding: utf-8 -*-
import sys
import os

sys.path.insert(0, os.path.abspath('.'))

from src.hopaoems.ai_engine import intent_dispatcher
from src.hopaoems.ai_engine.processor import AIProcessor

try:
    print("Loading model...")
    # Use the expected local path
    model_path = r"C:\Users\hopao\Desktop\HopaoEmsAI\models\Qwen3-7B-Instruct" 
    if not os.path.exists(model_path):
        model_path = r"C:\Users\hopao\Desktop\HopaoEmsAI\models\Qwen3-4B-Instruct"
        
    proc = AIProcessor(model_path)
    print("Model loaded.")
    
    text = "現在有多少樣品在資料庫裡"
    print(f"Testing text: {text}")
    
    raw = proc.generate(
        prompt=text,
        system_prompt=intent_dispatcher.INTENT_CLASSIFY_SYSTEM,
        max_tokens=512,
        temperature=0.3,
        top_p=0.8
    )
    
    print("\n" + "="*40)
    print("RAW OUTPUT:")
    print(repr(raw))
    print("="*40 + "\n")
    
    parsed = intent_dispatcher._parse_json(raw)
    print("PARSED OUTPUT:")
    print(repr(parsed))

except Exception as e:
    import traceback
    traceback.print_exc()
