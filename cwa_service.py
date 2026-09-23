"""
cwa_service.py - 中央氣象署 (CWA) Open Data API 服務模組
採用 O-A0003-001 資料集：自動氣象站氣象觀測資料 (即時現在天氣)
包含全台 360+ 個氣象站之即時氣溫、今日最高/最低溫、相對濕度、即時天氣現況與精準 GPS 座標。
"""

import os
import sys
import json
import ssl
import urllib.request
from datetime import datetime
from typing import List, Dict, Any, Optional

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

ENV_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
DATASET_ID = "O-A0003-001"


def load_cwa_api_key() -> str:
    """從環境變數或專案 .env 檔案讀取 CWA API Key"""
    api_key = os.environ.get("CWA_API_KEY", "")
    if api_key:
        return api_key.strip()
    
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
    呼叫 CWA Open Data REST API 取得 O-A0003-001 (自動氣象站觀測資料)
    """
    key = api_key or load_cwa_api_key()
    if not key:
        print("[警告] 未設定 CWA API Key，啟用內建示範數據生成器。")
        return generate_mock_observation_data()
        
    url = f"https://opendata.cwa.gov.tw/api/v1/rest/datastore/{DATASET_ID}?Authorization={key}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AIoT_Weather/2.0"
    }
    
    req = urllib.request.Request(url, headers=headers)
    
    try:
        ctx = ssl.create_default_context()
        with urllib.request.urlopen(req, context=ctx, timeout=12) as response:
            raw_text = response.read().decode("utf-8")
            return json.loads(raw_text)
    except Exception:
        try:
            unverified_ctx = ssl._create_unverified_context()
            with urllib.request.urlopen(req, context=unverified_ctx, timeout=12) as response:
                raw_text = response.read().decode("utf-8")
                return json.loads(raw_text)
        except Exception as e:
            print(f"[API 錯誤] 呼叫 CWA O-A0003-001 失敗: {e}，切換為備用模擬數據。")
            return generate_mock_observation_data()


def parse_weather_json(raw_json: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    解析 O-A0003-001 回傳的 Station 階層結構
    萃取：測站代碼、測站名稱、縣市名稱、鄉鎮區、即時氣溫、今日最高溫、今日最低溫、相對濕度、天氣、雨量、WGS84座標
    """
    records = []
    try:
        stations = raw_json.get("records", {}).get("Station", [])
        
        for s in stations:
            station_id = s.get("StationId", "")
            station_name = s.get("StationName", "")
            geo = s.get("GeoInfo", {})
            county_name = geo.get("CountyName", "未分類")
            town_name = geo.get("TownName", "")
            
            # 取得 WGS84 經緯度座標
            coords_list = geo.get("Coordinates", [])
            wgs_coord = next((c for c in coords_list if c.get("CoordinateName") == "WGS84"), coords_list[0] if coords_list else {})
            lat = float(wgs_coord.get("StationLatitude", 0.0))
            lon = float(wgs_coord.get("StationLongitude", 0.0))
            
            # 觀測時間
            obs_time = s.get("ObsTime", {}).get("DateTime", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
            
            # 氣象要素
            we = s.get("WeatherElement", {})
            
            # 即時氣溫
            raw_temp = we.get("AirTemperature")
            if raw_temp in [None, "-99", "-999", -99, -999]:
                continue  # 忽略無效感測器讀數
            air_temp = float(raw_temp)
            
            # 相對濕度
            raw_hum = we.get("RelativeHumidity")
            rel_humidity = float(raw_hum) if raw_hum not in [None, "-99", "-999", -99, -999] else None
            
            # 即時天氣現況
            weather_desc = we.get("Weather", "良好")
            
            # 今日最高溫與最低溫 (DailyExtreme)
            daily_ext = we.get("DailyExtreme", {})
            high_info = daily_ext.get("DailyHigh", {}).get("TemperatureInfo", {}).get("AirTemperature")
            low_info = daily_ext.get("DailyLow", {}).get("TemperatureInfo", {}).get("AirTemperature")
            
            max_t = float(high_info) if high_info not in [None, "-99", "-999", -99, -999] else air_temp
            min_t = float(low_info) if low_info not in [None, "-99", "-999", -99, -999] else air_temp
            
            # 確保 maxT >= minT
            if max_t < min_t:
                max_t, min_t = min_t, max_t
                
            # 雨量
            raw_precip = we.get("Now", {}).get("Precipitation", 0.0)
            precipitation = float(raw_precip) if raw_precip not in [None, "-99", "-999", -99, -999] else 0.0
            
            records.append({
                "stationId": station_id,
                "stationName": station_name,
                "countyName": county_name,
                "townName": town_name,
                "obsTime": obs_time,
                "airTemp": air_temp,
                "minT": min_t,
                "maxT": max_t,
                "relativeHumidity": rel_humidity,
                "weather": weather_desc,
                "precipitation": precipitation,
                "lat": lat,
                "lon": lon,
                # 相容性欄位
                "regionName": county_name,
                "dataDate": obs_time.replace("T", " ")[:16]
            })
            
    except Exception as e:
        print(f"[解析錯誤] 解析 O-A0003-001 時發生異常: {e}")
        
    return records


def generate_mock_observation_data() -> Dict[str, Any]:
    """生成符合 O-A0003-001 結構的模擬氣象站觀測數據"""
    sample_stations = [
        {"id": "466920", "name": "臺北", "county": "臺北市", "town": "中正區", "lat": 25.0375, "lon": 121.5148, "temp": 28.5},
        {"id": "C0A980", "name": "天母", "county": "臺北市", "town": "士林區", "lat": 25.1166, "lon": 121.5367, "temp": 27.8},
        {"id": "466880", "name": "板橋", "county": "新北市", "town": "板橋區", "lat": 24.9976, "lon": 121.4420, "temp": 28.2},
        {"id": "C0AD40", "name": "三峽", "county": "新北市", "town": "三峽區", "lat": 24.9287, "lon": 121.3789, "temp": 29.0},
        {"id": "467490", "name": "臺中", "county": "臺中市", "town": "北區", "lat": 24.1457, "lon": 120.6837, "temp": 29.4},
        {"id": "467410", "name": "臺南", "county": "臺南市", "town": "中西區", "lat": 22.9933, "lon": 120.2038, "temp": 30.1},
        {"id": "467440", "name": "高雄", "county": "高雄市", "town": "前鎮區", "lat": 22.5660, "lon": 120.3157, "temp": 30.8},
        {"id": "466990", "name": "花蓮", "county": "花蓮縣", "town": "花蓮市", "lat": 23.9752, "lon": 121.6133, "temp": 27.2},
        {"id": "467080", "name": "宜蘭", "county": "宜蘭縣", "town": "宜蘭市", "lat": 24.7640, "lon": 121.7565, "temp": 26.9},
        {"id": "467660", "name": "臺東", "county": "臺東縣", "town": "臺東市", "lat": 22.7522, "lon": 121.1546, "temp": 28.0}
    ]
    
    now_str = datetime.now().strftime("%Y-%m-%dT%H:%M:00+08:00")
    stations_payload = []
    
    for s in sample_stations:
        base_t = s["temp"]
        stations_payload.append({
            "StationId": s["id"],
            "StationName": s["name"],
            "ObsTime": {"DateTime": now_str},
            "GeoInfo": {
                "CountyName": s["county"],
                "TownName": s["town"],
                "Coordinates": [
                    {"CoordinateName": "WGS84", "StationLatitude": str(s["lat"]), "StationLongitude": str(s["lon"])}
                ]
            },
            "WeatherElement": {
                "AirTemperature": str(base_t),
                "RelativeHumidity": "72",
                "Weather": "多雲",
                "Now": {"Precipitation": "0.0"},
                "DailyExtreme": {
                    "DailyHigh": {"TemperatureInfo": {"AirTemperature": str(round(base_t + 2.5, 1))}},
                    "DailyLow": {"TemperatureInfo": {"AirTemperature": str(round(base_t - 4.0, 1))}}
                }
            }
        })
        
    return {
        "success": "true",
        "records": {
            "Station": stations_payload
        }
    }


if __name__ == "__main__":
    print(f"正在測試 CWA 服務模組 (資料集: {DATASET_ID})...")
    key = load_cwa_api_key()
    print(f"載入 API Key: {'已找到' if key else '未找到'}")
    raw = fetch_weather_data()
    parsed = parse_weather_json(raw)
    print(f"成功解析出 {len(parsed)} 個氣象觀測站之即時數據！")
    if parsed:
        p0 = parsed[0]
        print(f"測站範例：{p0['countyName']}{p0['townName']} - {p0['stationName']} (氣溫: {p0['airTemp']}°C, 濕度: {p0['relativeHumidity']}%, 今日最高: {p0['maxT']}°C, 最低: {p0['minT']}°C)")
