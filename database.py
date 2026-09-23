"""
database.py - SQLite 資料庫操作模組 (支援 CWA O-A0003-001 即時氣象觀測)
負責 StationObservations 資料表維護、防重複寫入 (Idempotency) 與多維度 SQL 查詢。
"""

import sqlite3
import os
from typing import List, Dict, Any, Optional

try:
    import pandas as pd
except ImportError:
    pd = None

DEFAULT_DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data.db")


def get_db_connection(db_path: str = DEFAULT_DB_PATH) -> sqlite3.Connection:
    """建立並取得 SQLite 資料庫連線"""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(db_path: str = DEFAULT_DB_PATH) -> None:
    """
    初始化資料表結構：
    建立 StationObservations 資料表，並設定 (stationId, obsTime) 唯一約束以實現防重複插入 (Idempotency)。
    同時保留 TemperatureForecasts 相容表。
    """
    conn = get_db_connection(db_path)
    cursor = conn.cursor()
    
    # 建立氣象站即時觀測資料表 (O-A0003-001)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS StationObservations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        stationId TEXT NOT NULL,
        stationName TEXT NOT NULL,
        countyName TEXT NOT NULL,
        townName TEXT,
        obsTime TEXT NOT NULL,
        airTemp REAL NOT NULL,
        minT REAL NOT NULL,
        maxT REAL NOT NULL,
        relativeHumidity REAL,
        weather TEXT,
        precipitation REAL DEFAULT 0.0,
        lat REAL,
        lon REAL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(stationId, obsTime)
    );
    """)
    
    # 建立加速查詢索引
    cursor.execute("""
    CREATE INDEX IF NOT EXISTS idx_county_station 
    ON StationObservations (countyName, stationName);
    """)
    
    cursor.execute("""
    CREATE INDEX IF NOT EXISTS idx_obs_time 
    ON StationObservations (obsTime);
    """)

    # 舊有預報相容表
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS TemperatureForecasts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        regionName TEXT NOT NULL,
        dataDate TEXT NOT NULL,
        minT REAL NOT NULL,
        maxT REAL NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(regionName, dataDate)
    );
    """)
    
    conn.commit()
    conn.close()


def save_forecasts(records: List[Dict[str, Any]], db_path: str = DEFAULT_DB_PATH) -> int:
    """
    寫入或更新氣象觀測資料 (支援 O-A0003-001 與舊格式)
    實作 INSERT OR REPLACE 達成 Idempotency (重複執行不重複插入)。
    """
    init_db(db_path)
    if not records:
        return 0
        
    conn = get_db_connection(db_path)
    cursor = conn.cursor()
    
    # 檢查是否為 O-A0003-001 觀測資料 (包含 stationId)
    is_observation = "stationId" in records[0]
    
    if is_observation:
        insert_sql = """
        INSERT INTO StationObservations (
            stationId, stationName, countyName, townName, obsTime,
            airTemp, minT, maxT, relativeHumidity, weather, precipitation,
            lat, lon
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(stationId, obsTime) DO UPDATE SET
            airTemp = excluded.airTemp,
            minT = excluded.minT,
            maxT = excluded.maxT,
            relativeHumidity = excluded.relativeHumidity,
            weather = excluded.weather,
            precipitation = excluded.precipitation,
            lat = excluded.lat,
            lon = excluded.lon,
            created_at = CURRENT_TIMESTAMP;
        """
        data_tuples = [
            (
                r["stationId"],
                r["stationName"],
                r["countyName"],
                r.get("townName", ""),
                r["obsTime"],
                float(r["airTemp"]),
                float(r["minT"]),
                float(r["maxT"]),
                float(r["relativeHumidity"]) if r.get("relativeHumidity") is not None else None,
                r.get("weather", "良好"),
                float(r.get("precipitation", 0.0)),
                float(r.get("lat", 0.0)),
                float(r.get("lon", 0.0))
            )
            for r in records
        ]
        cursor.executemany(insert_sql, data_tuples)
        
        # 同步更新相容表 TemperatureForecasts
        compat_sql = """
        INSERT INTO TemperatureForecasts (regionName, dataDate, minT, maxT)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(regionName, dataDate) DO UPDATE SET
            minT = excluded.minT,
            maxT = excluded.maxT,
            created_at = CURRENT_TIMESTAMP;
        """
        compat_tuples = [
            (r["countyName"], r["obsTime"][:10], float(r["minT"]), float(r["maxT"]))
            for r in records
        ]
        cursor.executemany(compat_sql, compat_tuples)
    else:
        # 傳統預報資料相容處理
        insert_sql = """
        INSERT INTO TemperatureForecasts (regionName, dataDate, minT, maxT)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(regionName, dataDate) DO UPDATE SET
            minT = excluded.minT,
            maxT = excluded.maxT,
            created_at = CURRENT_TIMESTAMP;
        """
        data_tuples = [
            (r["regionName"], r["dataDate"], float(r["minT"]), float(r["maxT"]))
            for r in records
        ]
        cursor.executemany(insert_sql, data_tuples)
        
    conn.commit()
    affected = len(data_tuples)
    conn.close()
    return affected


def get_all_counties(db_path: str = DEFAULT_DB_PATH) -> List[str]:
    """取得所有不重複的縣市清單"""
    init_db(db_path)
    conn = get_db_connection(db_path)
    cursor = conn.cursor()
    cursor.execute("""
    SELECT DISTINCT countyName 
    FROM StationObservations 
    WHERE countyName != '未分類' AND countyName != ''
    ORDER BY countyName ASC;
    """)
    counties = [row["countyName"] for row in cursor.fetchall()]
    conn.close()
    if not counties:
        # 相容回退
        return get_all_regions(db_path)
    return counties


def get_all_regions(db_path: str = DEFAULT_DB_PATH) -> List[str]:
    """相容性函式：取得所有地區/縣市"""
    return get_all_counties(db_path)


def get_stations_by_county(county_name: str, db_path: str = DEFAULT_DB_PATH) -> List[Dict[str, Any]]:
    """取得指定縣市之所有最新測站即時觀測數據"""
    init_db(db_path)
    conn = get_db_connection(db_path)
    cursor = conn.cursor()
    query = """
    SELECT stationId, stationName, countyName, townName, obsTime,
           airTemp, minT, maxT, relativeHumidity, weather, precipitation, lat, lon,
           ROUND(maxT - minT, 1) AS tempRange
    FROM StationObservations
    WHERE countyName = ?
    ORDER BY airTemp DESC;
    """
    cursor.execute(query, (county_name,))
    rows = cursor.fetchall()
    results = [dict(r) for r in rows]
    conn.close()
    return results


def get_all_latest_observations(db_path: str = DEFAULT_DB_PATH) -> List[Dict[str, Any]]:
    """取得全台所有測站最新觀測紀錄 (供地圖與全域表格使用)"""
    init_db(db_path)
    conn = get_db_connection(db_path)
    cursor = conn.cursor()
    query = """
    SELECT stationId, stationName, countyName, townName, obsTime,
           airTemp, minT, maxT, relativeHumidity, weather, precipitation, lat, lon,
           ROUND(maxT - minT, 1) AS tempRange
    FROM StationObservations
    ORDER BY countyName ASC, stationName ASC;
    """
    cursor.execute(query)
    rows = cursor.fetchall()
    results = [dict(r) for r in rows]
    conn.close()
    return results


def get_forecasts_by_region(region_name: str, db_path: str = DEFAULT_DB_PATH) -> Any:
    """相容性查詢函式"""
    stations = get_stations_by_county(region_name, db_path)
    if not stations:
        # 回退至相容表
        init_db(db_path)
        conn = get_db_connection(db_path)
        query = "SELECT regionName, dataDate, minT, maxT FROM TemperatureForecasts WHERE regionName = ? ORDER BY dataDate ASC;"
        if pd is not None:
            try:
                df = pd.read_sql_query(query, conn, params=(region_name,))
                conn.close()
                return df
            except Exception:
                pass
        cursor = conn.cursor()
        cursor.execute(query, (region_name,))
        rows = cursor.fetchall()
        data = [dict(r) for r in rows]
        conn.close()
        return pd.DataFrame(data) if pd is not None else data
        
    return pd.DataFrame(stations) if pd is not None else stations


def get_all_dates(db_path: str = DEFAULT_DB_PATH) -> List[str]:
    """取得所有觀測時間時段"""
    init_db(db_path)
    conn = get_db_connection(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT DISTINCT obsTime FROM StationObservations ORDER BY obsTime DESC;")
    times = [row["obsTime"] for row in cursor.fetchall()]
    conn.close()
    return times


def get_forecasts_by_date(data_date: str, db_path: str = DEFAULT_DB_PATH) -> List[Dict[str, Any]]:
    """以時間篩選觀測資料 (地圖使用)"""
    init_db(db_path)
    conn = get_db_connection(db_path)
    cursor = conn.cursor()
    cursor.execute("""
    SELECT stationId, stationName, countyName, townName, obsTime,
           airTemp, minT, maxT, relativeHumidity, weather, precipitation, lat, lon
    FROM StationObservations
    WHERE obsTime = ?
    ORDER BY countyName ASC;
    """, (data_date,))
    rows = cursor.fetchall()
    if not rows:
        cursor.execute("""
        SELECT stationId, stationName, countyName, townName, obsTime,
               airTemp, minT, maxT, relativeHumidity, weather, precipitation, lat, lon
        FROM StationObservations;
        """)
        rows = cursor.fetchall()
    results = [dict(r) for r in rows]
    conn.close()
    return results


def get_total_records_count(db_path: str = DEFAULT_DB_PATH) -> int:
    """取得資料庫總筆數"""
    init_db(db_path)
    conn = get_db_connection(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) AS total FROM StationObservations;")
    count = cursor.fetchone()["total"]
    conn.close()
    return count


if __name__ == "__main__":
    init_db()
    print("SQLite 資料庫初始化成功！StationObservations 資料表就緒。")
