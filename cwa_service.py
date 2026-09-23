"""
cwa_service.py - 中央氣象署 (CWA) Open Data API 服務模組
負責取得氣象預報資料、JSON 階層解析與氣溫資料提取。
符合專案工作流程 Steps 3, 4, 5, 6, 7, 20 之規範。
"""

import os
import sys
import json
import ssl
import urllib.request
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

ENV_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")

# 台灣主要縣市之經緯度座標 (供 Folium 地圖視覺化使用 Step 17 & 18)
TAIWAN_LOCATION_COORDS = {
    "臺北市": [25.0375, 121.5637],
    "新北市": [25.0118, 121.4658],
    "基隆市": [25.1276, 121.7392],
    "桃園市": [24.9936, 121.3010],
    "新竹市": [24.8138, 120.9675],
    "新竹縣": [24.8387, 121.0177],
    "苗栗縣": [24.5602, 120.8214],
    "臺中市": [24.1477, 120.6736],
    "彰化縣": [24.0518, 120.5161],
    "南投縣": [23.9609, 120.9719],
    "雲林縣": [23.7092, 120.4313],
    "嘉義市": [23.4800, 120.4491],
    "嘉義縣": [23.4518, 120.2559],
    "臺南市": [22.9997, 120.2270],
    "高雄市": [22.6273, 120.3014],
    "屏東縣": [22.5519, 120.5487],
    "宜蘭縣": [24.7021, 121.7377],
    "花蓮縣": [23.9872, 121.6016],
    "臺東縣": [22.7583, 121.1444],
    "澎湖縣": [23.5711, 119.5793],
    "金門縣": [24.4493, 118.3766],
    "連江縣": [26.1505, 119.9499],
    # 區域大範圍座標
    "北部地區": [25.0375, 121.5637],
    "中部地區": [24.1477, 120.6736],
    "南部地區": [22.6273, 120.3014],
    "東北部地區": [24.7021, 121.7377],
    "東部地區": [23.9872, 121.6016],
    "東南部地區": [22.7583, 121.1444]
}


def load_cwa_api_key() -> str:
    """
    從環境變數或專案 .env 檔案讀取 CWA API Key
    """
    # 優先讀取系統環境變數
    api_key = os.environ.get("CWA_API_KEY", "")
    if api_key:
        return api_key.strip()
    
    # 讀取 .env 檔案
    if os.path.exists(ENV_PATH):
        try:
            with open(ENV_PATH, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line.startswith("CWA_API_KEY=") and not line.startswith("#"):
                        return line.split("=", 1)[1].strip().strip('"').strip("'")
        except Exception:
            pass
            
    return ""


def fetch_weather_data(api_key: Optional[str] = None) -> Dict[str, Any]:
    """
    使用 Requests / Urllib 呼叫 CWA Open Data REST API (Step 4)
    資料集：F-C0032-001 (一般天氣預報-今明36小時天氣預報)
    若發生網路或憑證錯誤，則具備優雅處理與重試機制 (Step 20)。
    """
    key = api_key or load_cwa_api_key()
    if not key:
        print("[警告] 未設定 CWA API Key，啟用內建示範數據生成器。")
        return generate_mock_weather_data()
        
    url = f"https://opendata.cwa.gov.tw/api/v1/rest/datastore/F-C0032-001?Authorization={key}"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AIoT_Weather/1.0"
    }
    
    req = urllib.request.Request(url, headers=headers)
    
    # 建立 SSL 上下文 (解決 Windows 本機憑證路徑問題)
    try:
        ctx = ssl.create_default_context()
        with urllib.request.urlopen(req, context=ctx, timeout=12) as response:
            raw_text = response.read().decode("utf-8")
            return json.loads(raw_text)
    except Exception as ssl_err:
        # 回退至未驗證 SSL 上下文
        try:
            unverified_ctx = ssl._create_unverified_context()
            with urllib.request.urlopen(req, context=unverified_ctx, timeout=12) as response:
                raw_text = response.read().decode("utf-8")
                return json.loads(raw_text)
        except Exception as e:
            print(f"[API 錯誤] 呼叫 CWA API 失敗: {e}，切換為備用模擬數據。")
            return generate_mock_weather_data()


def parse_weather_json(raw_json: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    解析 CWA 回傳的 JSON 結構 (Step 5 & 6)
    定位 locationName 與 weatherElement 中的 MinT (最低溫) 和 MaxT (最高溫)
    並提取乾淨的結構化紀錄。
    """
    records = []
    try:
        locations = raw_json.get("records", {}).get("location", [])
        
        for loc in locations:
            region_name = loc.get("locationName", "")
            elements = loc.get("weatherElement", [])
            
            mint_times = []
            maxt_times = []
            
            for elem in elements:
                elem_name = elem.get("elementName")
                if elem_name == "MinT":
                    mint_times = elem.get("time", [])
                elif elem_name == "MaxT":
                    maxt_times = elem.get("time", [])
            
            # 整合時間區段與氣溫
            for min_info, max_info in zip(mint_times, maxt_times):
                start_time_str = min_info.get("startTime", "")
                data_date = start_time_str.split(" ")[0] if " " in start_time_str else start_time_str
                
                # 區分時段標記 (如: 06:00 或 18:00)
                time_period = start_time_str.split(" ")[1][:5] if " " in start_time_str else ""
                display_date = f"{data_date} ({time_period})" if time_period else data_date
                
                min_val = float(min_info.get("parameter", {}).get("parameterName", 20.0))
                max_val = float(max_info.get("parameter", {}).get("parameterName", 28.0))
                
                records.append({
                    "regionName": region_name,
                    "dataDate": display_date,
                    "minT": min_val,
                    "maxT": max_val
                })
                
    except Exception as e:
        print(f"[解析錯誤] JSON 解析過程發生異常: {e}")
        
    return records


def generate_mock_weather_data() -> Dict[str, Any]:
    """
    當無網路連線或 API Key 異常時之標準 JSON 模擬生成器 (Step 20 穩健性)
    提供符合 F-C0032-001 格式之完整台灣預報數據。
    """
    sample_regions = [
        "臺北市", "新北市", "桃園市", "臺中市", "臺南市", "高雄市",
        "基隆市", "新竹市", "新竹縣", "苗栗縣", "彰化縣", "南投縣",
        "雲林縣", "嘉義市", "嘉義縣", "屏東縣", "宜蘭縣", "花蓮縣",
        "臺東縣", "澎湖縣", "金門縣", "連江縣",
        "北部地區", "中部地區", "南部地區", "東北部地區", "東部地區", "東南部地區"
    ]
    
    today = datetime.now()
    dates = [
        (today + timedelta(days=i)).strftime("%Y-%m-%d")
        for i in range(7)
    ]
    
    locations_payload = []
    
    import random
    random.seed(42) # 保持固定隨機種子以確保一致性
    
    for region in sample_regions:
        # 依地區產生合理的台灣氣候基礎溫度
        base_min = 20.0 if "北" in region else (23.0 if "南" in region else 21.5)
        
        mint_times = []
        maxt_times = []
        
        for d in dates:
            for period in ["06:00:00", "18:00:00"]:
                time_str = f"{d} {period}"
                min_t = round(base_min + random.uniform(-2, 3), 1)
                max_t = round(min_t + random.uniform(6, 11), 1)
                
                mint_times.append({
                    "startTime": time_str,
                    "endTime": time_str,
                    "parameter": {"parameterName": str(min_t), "parameterUnit": "C"}
                })
                maxt_times.append({
                    "startTime": time_str,
                    "endTime": time_str,
                    "parameter": {"parameterName": str(max_t), "parameterUnit": "C"}
                })
                
        locations_payload.append({
            "locationName": region,
            "weatherElement": [
                {"elementName": "MinT", "time": mint_times},
                {"elementName": "MaxT", "time": maxt_times}
            ]
        })
        
    return {
        "success": "true",
        "records": {
            "datasetDescription": "三十六小時天氣預報 (模擬生成)",
            "location": locations_payload
        }
    }


if __name__ == "__main__":
    print("正在測試 CWA 服務模組...")
    key = load_cwa_api_key()
    print(f"載入 API Key: {'已找到' if key else '未找到'}")
    raw = fetch_weather_data()
    parsed = parse_weather_json(raw)
    print(f"成功解析出 {len(parsed)} 筆氣溫紀錄！")
    if parsed:
        print("前 3 筆範例：", parsed[:3])
