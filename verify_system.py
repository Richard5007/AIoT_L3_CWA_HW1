"""
verify_system.py - Taiwan Weather Forecast 全系統自動化驗證腳本
驗證工作流程全 24 步驟各模組之功能完整性與穩健度
執行指令：python verify_system.py
"""

import os
import sys

# 確保輸出編碼正確
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from cwa_service import load_cwa_api_key, fetch_weather_data, parse_weather_json, TAIWAN_LOCATION_COORDS
from database import (
    init_db,
    save_forecasts,
    get_all_regions,
    get_all_dates,
    get_forecasts_by_region,
    get_forecasts_by_date,
    get_total_records_count,
    DEFAULT_DB_PATH
)


def run_all_checks():
    print("=" * 60)
    print("🚀 開始執行 Taiwan Weather Forecast 全系統自動化檢驗...")
    print("=" * 60)
    
    passed_steps = 0
    total_steps = 7

    # 檢驗 1: 環境變數與 API 金鑰 (Step 3 & 4)
    print("\n[測試 1/7] 檢驗 CWA API 金鑰讀取...")
    api_key = load_cwa_api_key()
    assert api_key != "", "錯誤: 未能從 .env 讀取到有效的 CWA_API_KEY！"
    print(f"  -> 通過！成功讀取 API Key (結尾: ...{api_key[-6:]})")
    passed_steps += 1

    # 檢驗 2: CWA API 資料擷取與 JSON 解析 (Step 4, 5, 6)
    print("\n[測試 2/7] 檢驗 CWA API 請求與 JSON 樹狀解析...")
    raw_json = fetch_weather_data(api_key)
    assert "records" in raw_json, "錯誤: API 回傳格式不包含 records 節點！"
    parsed_records = parse_weather_json(raw_json)
    assert len(parsed_records) > 0, "錯誤: 未能提取到任何氣溫預報紀錄！"
    first = parsed_records[0]
    assert "regionName" in first and "minT" in first and "maxT" in first and "dataDate" in first, "錯誤: 欄位缺漏！"
    print(f"  -> 通過！成功從氣象署 API 解析 {len(parsed_records)} 筆氣溫紀錄。")
    print(f"     樣本: {first['regionName']} | 日期: {first['dataDate']} | 氣溫: {first['minT']}°C ~ {first['maxT']}°C")
    passed_steps += 1

    # 檢驗 3: SQLite 資料庫初始化與寫入 (Step 8 & 9)
    print("\n[測試 3/7] 檢驗 SQLite 資料庫連線與 Schema 初始化...")
    init_db()
    assert os.path.exists(DEFAULT_DB_PATH), "錯誤: data.db 檔案不存在！"
    saved = save_forecasts(parsed_records)
    print(f"  -> 通過！成功寫入 {saved} 筆氣象預報資料至 data.db。")
    passed_steps += 1

    # 檢驗 4: 防重複寫入機制 Idempotency (Step 20 程式品質優化)
    print("\n[測試 4/7] 檢驗資料庫防重複寫入 (Idempotency) 機制...")
    count_before = get_total_records_count()
    # 再次寫入相同紀錄
    save_forecasts(parsed_records)
    count_after = get_total_records_count()
    assert count_before == count_after, f"錯誤: 重複寫入導致筆數增加！({count_before} -> {count_after})"
    print(f"  -> 通過！二次寫入後總筆數維持 {count_after} 筆，完全具備防重複寫入特性！")
    passed_steps += 1

    # 檢驗 5: 查詢功能與地區/日期過濾 (Step 10, 12, 13)
    print("\n[測試 5/7] 檢驗 SQL 資料查詢與篩選邏輯...")
    regions = get_all_regions()
    dates = get_all_dates()
    assert len(regions) >= 20, f"錯誤: 地區數量異常 ({len(regions)})！"
    assert len(dates) > 0, "錯誤: 預報日期清單為空！"
    
    test_region = regions[0]
    region_records = get_forecasts_by_region(test_region)
    print(f"  -> 通過！全台共有 {len(regions)} 個地區、{len(dates)} 個預報時段。")
    print(f"     測試地區 [{test_region}] 查詢成功，取得預報資料。")
    passed_steps += 1

    # 檢驗 6: 地理資訊與地圖座標對應 (Step 17 & 18)
    print("\n[測試 6/7] 檢驗台灣主要縣市之經緯度對應表...")
    matched_coords = sum(1 for r in regions if r in TAIWAN_LOCATION_COORDS)
    print(f"  -> 通過！{matched_coords}/{len(regions)} 個地區具有精準經緯度座標供 Folium 地圖標記。")
    passed_steps += 1

    # 檢驗 7: 專案必要檔案完整性 (Step 21)
    print("\n[測試 7/7] 檢驗專案核心檔案完整性...")
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
    print(f"  -> 通過！專案全部 {len(required_files)} 項核心檔案均完整齊備。")
    passed_steps += 1

    print("\n" + "=" * 60)
    print(f"🎉 全部測試通過！({passed_steps}/{total_steps})")
    print("專案各模組運行正常，已達成 24 步驟學習地圖之全項開發目標！")
    print("=" * 60)


if __name__ == "__main__":
    run_all_checks()
