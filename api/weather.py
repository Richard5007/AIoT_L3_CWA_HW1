"""
api/weather.py - Vercel Serverless Function for /api/weather
直接處理氣象數據 API 請求
"""

import os
import sys
import json
from datetime import datetime
from flask import Flask, jsonify, make_response

current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.abspath(os.path.join(current_dir, ".."))
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

from cwa_service import fetch_weather_data, parse_weather_json, load_cwa_api_key, DATASET_ID

app = Flask(__name__)


@app.route("/", defaults={"path": ""})
@app.route("/<path:path>")
def handler(path):
    api_key = load_cwa_api_key()
    raw_data = fetch_weather_data(api_key)
    records = parse_weather_json(raw_data)
    
    resp = make_response(jsonify({
        "success": True,
        "dataset": DATASET_ID,
        "count": len(records),
        "updated_at": datetime.now().isoformat(),
        "stations": records
    }))
    
    resp.headers["Cache-Control"] = "public, max-age=60, s-maxage=300"
    resp.headers["Access-Control-Allow-Origin"] = "*"
    return resp


if __name__ == "__main__":
    app.run(port=3001, debug=True)
