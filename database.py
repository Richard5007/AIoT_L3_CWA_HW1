"""
database.py - SQLite 資料庫操作模組
負責建立資料庫、資料表 Schema 設計，以及資料寫入與查詢驗證。
符合專案工作流程 Steps 8, 9, 10, 12, 20 之規範 (包含防重複寫入 Idempotency 機制)。
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
    初始化資料庫與資料表結構 (Step 8 & 9)
    設計 TemperatureForecasts 資料表，並建立 (regionName, dataDate) 唯一約束
    以確保重複執行時不重複插入資料 (Step 20 Idempotency)。
    """
    conn = get_db_connection(db_path)
    cursor = conn.cursor()
    
    # 建立氣溫預報資料表
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
    
    # 建立索引以加速地區與日期查詢
    cursor.execute("""
    CREATE INDEX IF NOT EXISTS idx_region_date 
    ON TemperatureForecasts (regionName, dataDate);
    """)
    
    conn.commit()
    conn.close()


def save_forecasts(records: List[Dict[str, Any]], db_path: str = DEFAULT_DB_PATH) -> int:
    """
    將解析後的氣溫資料存入 SQLite 資料庫 (Step 8 & 20)
    使用 INSERT OR REPLACE 避免重複插入相同地區與日期的資料。
    
    :param records: 包含 regionName, dataDate, minT, maxT 的字典列表
    :param db_path: 資料庫檔案路徑
    :return: 成功寫入或更新的筆數
    """
    init_db(db_path)
    conn = get_db_connection(db_path)
    cursor = conn.cursor()
    
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


def get_all_regions(db_path: str = DEFAULT_DB_PATH) -> List[str]:
    """查詢所有不重複的預報地區清單 (Step 10 & 13)"""
    init_db(db_path)
    conn = get_db_connection(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT DISTINCT regionName FROM TemperatureForecasts ORDER BY regionName;")
    regions = [row["regionName"] for row in cursor.fetchall()]
    conn.close()
    return regions


def get_all_dates(db_path: str = DEFAULT_DB_PATH) -> List[str]:
    """查詢所有不重複的預報日期 (Step 18)"""
    init_db(db_path)
    conn = get_db_connection(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT DISTINCT dataDate FROM TemperatureForecasts ORDER BY dataDate ASC;")
    dates = [row["dataDate"] for row in cursor.fetchall()]
    conn.close()
    return dates


def get_forecasts_by_region(region_name: str, db_path: str = DEFAULT_DB_PATH) -> Any:
    """
    查詢特定地區的氣溫資料並轉換為 Pandas DataFrame (Step 10 & 12)
    """
    init_db(db_path)
    conn = get_db_connection(db_path)
    query = """
    SELECT regionName, dataDate, minT, maxT, ROUND((maxT + minT)/2.0, 1) as avgT
    FROM TemperatureForecasts
    WHERE regionName = ?
    ORDER BY dataDate ASC;
    """
    if pd is not None:
        try:
            df = pd.read_sql_query(query, conn, params=(region_name,))
            return df
        except Exception:
            pass
            
    # 當 pandas 尚未安裝或發生異常時之原生 sqlite3 回退機制
    cursor = conn.cursor()
    cursor.execute(query, (region_name,))
    rows = cursor.fetchall()
    data = [dict(r) for r in rows]
    conn.close()
    return pd.DataFrame(data) if pd is not None else data


def get_forecasts_by_date(data_date: str, db_path: str = DEFAULT_DB_PATH) -> List[Dict[str, Any]]:
    """查詢特定日期的全台灣各地氣象預報 (用於地圖呈現 Step 17 & 18)"""
    init_db(db_path)
    conn = get_db_connection(db_path)
    cursor = conn.cursor()
    cursor.execute("""
    SELECT regionName, dataDate, minT, maxT, ROUND((maxT + minT)/2.0, 1) as avgT
    FROM TemperatureForecasts
    WHERE dataDate = ?
    ORDER BY regionName ASC;
    """, (data_date,))
    rows = cursor.fetchall()
    results = [dict(row) for row in rows]
    conn.close()
    return results


def get_total_records_count(db_path: str = DEFAULT_DB_PATH) -> int:
    """取得資料表中的總紀錄筆數 (Step 10 驗證用)"""
    init_db(db_path)
    conn = get_db_connection(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) AS total FROM TemperatureForecasts;")
    count = cursor.fetchone()["total"]
    conn.close()
    return count


if __name__ == "__main__":
    init_db()
    print("SQLite 資料庫初始化成功！資料表結構就緒。")
