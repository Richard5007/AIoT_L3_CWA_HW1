"""
fetch_data.py - 自動擷取中央氣象署資料並寫入 SQLite 資料庫
執行指令：python fetch_data.py
涵蓋工作流程 Steps 4, 5, 6, 7, 8, 9, 10
"""

import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from cwa_service import fetch_weather_data, parse_weather_json, load_cwa_api_key
from database import init_db, save_forecasts, get_total_records_count, get_all_regions


def sync_weather_data():
    print("=" * 55)
    print("[INFO] 開始執行中央氣象署 (CWA) 氣溫資料同步程序...")
    print("=" * 55)
    
    # 1. 檢查 API 金鑰
    api_key = load_cwa_api_key()
    if api_key:
        print(f"[步驟 3 & 4] 讀取到 API Key (結尾: ...{api_key[-6:]})")
    else:
        print("[步驟 3 & 4] 未偵測到 API Key，將使用模擬氣象數據。")
        
    # 2. 擷取資料 (Step 4)
    print(">> 正在呼叫 CWA Open Data API 取得最新預報資料 (JSON)...")
    raw_data = fetch_weather_data(api_key)
    
    # 3. 解析資料 (Step 5 & 6)
    print(">> 正在解析 JSON 樹狀結構並提取最高溫 (MaxT) 與最低溫 (MinT)...")
    records = parse_weather_json(raw_data)
    print(f">> 成功提取 {len(records)} 筆結構化氣溫紀錄。")
    
    if not records:
        print("[錯誤] 未能提取有效氣溫資料，同步程序終止。")
        sys.exit(1)
        
    # 4. 寫入 SQLite 資料庫 (Step 8 & 9 & 20)
    print(">> 正在寫入 SQLite 資料庫 (data.db)，執行防重複插入 (Idempotency) 保障...")
    init_db()
    saved_count = save_forecasts(records)
    total_count = get_total_records_count()
    
    # 5. 驗證資料庫內容 (Step 10)
    regions = get_all_regions()
    print("-" * 55)
    print("[SUCCESS] 資料同步成功完成！")
    print(f"- 本次處理筆數: {saved_count} 筆")
    print(f"- 資料庫目前總筆數: {total_count} 筆")
    print(f"- 涵蓋地區數量: {len(regions)} 個地區")
    print(f"- 地區範例: {', '.join(regions[:6])} ...")
    print("=" * 55)


if __name__ == "__main__":
    sync_weather_data()
