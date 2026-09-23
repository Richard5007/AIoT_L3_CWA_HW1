"""
fetch_data.py - 自動擷取中央氣象署 O-A0003-001 資料並寫入 SQLite 資料庫
執行指令：python fetch_data.py
"""

import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from cwa_service import fetch_weather_data, parse_weather_json, load_cwa_api_key, DATASET_ID
from database import init_db, save_forecasts, get_total_records_count, get_all_counties


def sync_weather_data():
    print("=" * 60)
    print(f"[INFO] 開始執行中央氣象署 ({DATASET_ID}) 氣溫觀測資料同步程序...")
    print("=" * 60)
    
    # 1. 檢查 API 金鑰
    api_key = load_cwa_api_key()
    if api_key:
        print(f">> 讀取到 API Key (結尾: ...{api_key[-6:]})")
    else:
        print("[警告] 未偵測到 API Key，將使用模擬氣象數據。")
        
    # 2. 擷取資料
    print(f">> 正在呼叫 CWA API ({DATASET_ID}) 取得全台氣象測站即時觀測資料 (JSON)...")
    raw_data = fetch_weather_data(api_key)
    
    # 3. 解析資料
    print(">> 正在解析 JSON 樹狀結構並提取即時氣溫 (AirTemp)、今日高低溫與測站資訊...")
    records = parse_weather_json(raw_data)
    print(f">> 成功提取 {len(records)} 個氣象觀測站之結構化紀錄。")
    
    if not records:
        print("[錯誤] 未能提取有效觀測資料，同步程序終止。")
        sys.exit(1)
        
    # 4. 寫入 SQLite 資料庫 (Idempotency 保障)
    print(">> 正在寫入 SQLite 資料庫 (data.db)，執行防重複插入 (Idempotency) 保障...")
    init_db()
    saved_count = save_forecasts(records)
    total_count = get_total_records_count()
    
    # 5. 驗證資料庫內容
    counties = get_all_counties()
    print("-" * 60)
    print("[SUCCESS] 資料同步成功完成！")
    print(f"- 本次處理筆數: {saved_count} 筆")
    print(f"- 資料庫目前總筆數: {total_count} 筆")
    print(f"- 涵蓋縣市數量: {len(counties)} 個縣市")
    print(f"- 縣市範例: {', '.join(counties[:6])} ...")
    print("=" * 60)


if __name__ == "__main__":
    sync_weather_data()
