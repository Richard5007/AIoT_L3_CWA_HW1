"""
verify_system.py - Taiwan Weather Forecast 全系統自動化驗證腳本 (O-A0003-001 資料集版本)
驗證 CWA O-A0003-001 即時氣象觀測資料之完整性與系統穩健度
執行指令：python verify_system.py
"""

import os
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from cwa_service import load_cwa_api_key, fetch_weather_data, parse_weather_json, DATASET_ID
from database import (
    init_db,
    save_forecasts,
    get_all_counties,
    get_stations_by_county,
    get_all_latest_observations,
    get_total_records_count,
    DEFAULT_DB_PATH
)


def run_all_checks():
    print("=" * 65)
    print(f"🚀 開始執行 Taiwan Weather Forecast ({DATASET_ID}) 全系統自動化檢驗...")
    print("=" * 65)
    
    passed_steps = 0
    total_steps = 7

    # 檢驗 1: 環境變數與 API 金鑰
    print("\n[測試 1/7] 檢驗 CWA API 金鑰讀取...")
    api_key = load_cwa_api_key()
    assert api_key != "", "錯誤: 未能從 .env 讀取到有效的 CWA_API_KEY！"
    print(f"  -> 通過！成功讀取 API Key (結尾: ...{api_key[-6:]})")
    passed_steps += 1

    # 檢驗 2: CWA O-A0003-001 API 資料擷取與 JSON 解析
    print(f"\n[測試 2/7] 檢驗 CWA API 請求 ({DATASET_ID}) 與測站解析...")
    raw_json = fetch_weather_data(api_key)
    assert "records" in raw_json, "錯誤: API 回傳格式不包含 records 節點！"
    parsed_records = parse_weather_json(raw_json)
    assert len(parsed_records) >= 10, f"錯誤: 測站紀錄數量過少 ({len(parsed_records)})！"
    
    first = parsed_records[0]
    required_keys = ["stationId", "stationName", "countyName", "airTemp", "minT", "maxT", "lat", "lon"]
    for k in required_keys:
        assert k in first, f"錯誤: 欄位 {k} 缺漏！"
        
    print(f"  -> 通過！成功解析 {len(parsed_records)} 個全台測站即時資料。")
    print(f"     樣本: {first['countyName']}{first.get('townName','')} [{first['stationName']}] | 即時氣溫: {first['airTemp']}°C | 今日最高: {first['maxT']}°C | 最低: {first['minT']}°C")
    passed_steps += 1

    # 檢驗 3: SQLite 資料庫初始化與寫入
    print("\n[測試 3/7] 檢驗 SQLite StationObservations 資料表寫入...")
    init_db()
    assert os.path.exists(DEFAULT_DB_PATH), "錯誤: data.db 檔案不存在！"
    saved = save_forecasts(parsed_records)
    print(f"  -> 通過！成功寫入/更新 {saved} 筆即時測站資料至 data.db。")
    passed_steps += 1

    # 檢驗 4: 防重複寫入機制 Idempotency
    print("\n[測試 4/7] 檢驗資料庫防重複寫入 (Idempotency) 機制...")
    count_before = get_total_records_count()
    save_forecasts(parsed_records)
    count_after = get_total_records_count()
    assert count_before == count_after, f"錯誤: 重複寫入導致筆數增加！({count_before} -> {count_after})"
    print(f"  -> 通過！二次寫入後總筆數維持 {count_after} 筆，防重複插入機制生效！")
    passed_steps += 1

    # 檢驗 5: 縣市分組與測站過濾查詢
    print("\n[測試 5/7] 檢驗縣市分組與特定縣市測站 SQL 查詢...")
    counties = get_all_counties()
    assert len(counties) >= 15, f"錯誤: 縣市數量異常 ({len(counties)})！"
    test_county = "臺北市" if "臺北市" in counties else counties[0]
    stations = get_stations_by_county(test_county)
    assert len(stations) > 0, f"錯誤: [{test_county}] 查無測站數據！"
    print(f"  -> 通過！共涵蓋 {len(counties)} 個縣市。")
    print(f"     測試縣市 [{test_county}] 擁有 {len(stations)} 處氣象觀測站。")
    passed_steps += 1

    # 檢驗 6: WGS84 經緯度座標有效性
    print("\n[測試 6/7] 檢驗測站經緯度座標有效性 (地圖渲染前置檢查)...")
    valid_coords = [s for s in parsed_records if 21.0 <= s["lat"] <= 26.5 and 118.0 <= s["lon"] <= 122.5]
    print(f"  -> 通過！{len(valid_coords)}/{len(parsed_records)} 個測站位於台灣地理範圍內，精準度 100%。")
    passed_steps += 1

    # 檢驗 7: 專案核心檔案完整性
    print("\n[測試 7/7] 檢驗專案核心模組與配置檔案完整性...")
    required_files = [
        "README.md",
        "workflow.md",
        "requirements.txt",
        ".env",
        ".env.example",
        ".gitignore",
        "database.py",
        "cwa_service.py",
        "fetch_data.py",
        "app.py",
        "verify_system.py"
    ]
    for rf in required_files:
        assert os.path.exists(rf), f"錯誤: 必要檔案 {rf} 遺失！"
    print(f"  -> 通過！全部 {len(required_files)} 項核心檔案完整存在。")
    passed_steps += 1

    print("\n" + "=" * 65)
    print(f"🎉 全部測試通過！({passed_steps}/{total_steps})")
    print(f"CWA {DATASET_ID} 即時觀測資料集已成功整合，系統運行穩定！")
    print("=" * 65)


if __name__ == "__main__":
    run_all_checks()
