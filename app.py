"""
app.py - Taiwan Weather Live 即時氣象觀測儀表板 (CWA O-A0003-001 專用版)
全台 330+ 氣象觀測站實時連線 · 即時氣溫 · 今日高低溫 · 相對濕度 · 互動地圖
"""

import os
import sys
from datetime import datetime

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

import streamlit as st

try:
    import pandas as pd
except ImportError:
    pd = None

try:
    import plotly.graph_objects as go
    import plotly.express as px
except ImportError:
    go = None
    px = None

try:
    import folium
    from streamlit_folium import st_folium
except ImportError:
    folium = None
    st_folium = None

import database
import importlib
importlib.reload(database)

init_db = database.init_db
save_forecasts = database.save_forecasts
get_all_counties = getattr(database, "get_all_counties", getattr(database, "get_all_regions", lambda: []))
get_stations_by_county = getattr(database, "get_stations_by_county", lambda c: [])
get_all_latest_observations = getattr(database, "get_all_latest_observations", lambda: [])
get_total_records_count = getattr(database, "get_total_records_count", lambda: 0)
from cwa_service import (
    fetch_weather_data,
    parse_weather_json,
    load_cwa_api_key,
    DATASET_ID
)

# 頁面配置
st.set_page_config(
    page_title="Taiwan Weather Live - 即時氣象觀測儀表板",
    page_icon="🌤️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 進階美化 CSS 樣式
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;600;700;800&family=Noto+Sans+TC:wght@400;500;700;900&display=swap');
    
    html, body, [class*="css"] {
        font-family: 'Plus Jakarta Sans', 'Noto Sans TC', sans-serif;
    }
    
    /* 頂部 Hero Banner */
    .hero-banner {
        background: linear-gradient(135deg, #0f172a 0%, #1e3a8a 50%, #0284c7 100%);
        border-radius: 16px;
        padding: 26px 30px;
        color: white;
        margin-bottom: 22px;
        box-shadow: 0 10px 25px -5px rgba(2, 132, 199, 0.25);
        position: relative;
    }
    
    .hero-title {
        font-size: 2.1rem;
        font-weight: 800;
        margin: 0 0 6px 0;
        display: flex;
        align-items: center;
        gap: 12px;
    }
    
    .hero-desc {
        font-size: 1.02rem;
        opacity: 0.92;
        margin: 0;
        font-weight: 400;
    }
    
    .status-badge {
        display: inline-flex;
        align-items: center;
        gap: 6px;
        background: rgba(255, 255, 255, 0.16);
        backdrop-filter: blur(10px);
        padding: 5px 12px;
        border-radius: 9999px;
        font-size: 0.82rem;
        font-weight: 600;
        margin-top: 12px;
        border: 1px solid rgba(255, 255, 255, 0.2);
    }
    
    .status-dot {
        width: 8px;
        height: 8px;
        background-color: #10B981;
        border-radius: 50%;
        box-shadow: 0 0 8px #10B981;
    }

    /* 指標卡片美化 */
    .metric-card-box {
        background: white;
        border-radius: 14px;
        padding: 18px 20px;
        border: 1px solid #E2E8F0;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05);
        transition: transform 0.2s ease, box-shadow 0.2s ease;
    }
    
    .metric-card-box:hover {
        transform: translateY(-2px);
        box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.08);
    }

    .metric-label {
        font-size: 0.85rem;
        font-weight: 600;
        color: #64748B;
        margin-bottom: 4px;
    }
    
    .metric-value {
        font-size: 1.9rem;
        font-weight: 800;
        line-height: 1.2;
    }
    
    .metric-footer {
        margin-top: 6px;
        font-size: 0.8rem;
        color: #94A3B8;
    }

    /* 生活建議小卡 */
    .tip-card {
        background: #F8FAFC;
        border-left: 4px solid #0284C7;
        border-radius: 0 12px 12px 0;
        padding: 14px 18px;
        margin: 16px 0;
    }
</style>
""", unsafe_allow_html=True)


def get_temp_color(avg_temp: float) -> str:
    """依據即時氣溫返回溫度標籤色階"""
    if avg_temp < 20:
        return "#3B82F6"  # 藍色 (<20°C 涼爽)
    elif avg_temp <= 25:
        return "#10B981"  # 綠色 (20-25°C 舒適)
    elif avg_temp <= 30:
        return "#F59E0B"  # 橙色 (25-30°C 溫暖)
    else:
        return "#EF4444"  # 紅色 (>30°C 炎熱)


def get_greeting() -> str:
    """依當前小時取得問候語"""
    now_hour = datetime.now().hour
    if 5 <= now_hour < 11:
        return "早安"
    elif 11 <= now_hour < 14:
        return "午安"
    elif 14 <= now_hour < 18:
        return "下午好"
    else:
        return "晚安"


def get_clothing_advice(air_temp: float, max_t: float, min_t: float) -> tuple:
    """智慧穿搭與天氣生活建議"""
    diff = max_t - min_t
    if air_temp >= 30:
        cloth = "目前氣溫高達 30°C 以上，戶外高溫炎熱，建議穿著排汗透氣短袖，注意防曬並定時補充水分。"
        icon = "☀️"
    elif air_temp >= 25:
        cloth = "氣溫在 25~30°C 之間，體感暖和微熱，穿著一般夏季休閒短袖即可。"
        icon = "🌤️"
    elif air_temp >= 20:
        cloth = "目前氣溫約 20~25°C，微風舒適宜人，適合穿著舒適長袖或搭配薄襯衫。"
        icon = "🧥"
    else:
        cloth = "氣溫低於 20°C，體感偏冷涼，建議著保暖外套或毛衣禦寒。"
        icon = "🧣"
        
    notice = "今日日溫差偏大 (超過 7°C)，外出請注意早晚溫差變化。" if diff >= 7 else "今日溫差平穩，氣溫穩定。"
    return cloth, notice, icon


def main():
    init_db()
    cwa_key = load_cwa_api_key()
    
    # 側邊欄控制面板
    st.sidebar.markdown("### 🌤️ **氣象控制台**")
    st.sidebar.caption(f"中央氣象署 Open Data ({DATASET_ID})")
    
    # 手動即時同步按鈕
    if st.sidebar.button("🔄 同步氣象署最新觀測資料", use_container_width=True, type="primary"):
        with st.spinner("正在向中央氣象署請求全台測站即時觀測數據..."):
            try:
                raw_json = fetch_weather_data(cwa_key)
                records = parse_weather_json(raw_json)
                if records:
                    saved = save_forecasts(records)
                    st.sidebar.success(f"✅ 同步成功！已更新 {saved} 處測站資料。")
                else:
                    st.sidebar.warning("⚠️ 未取得任何紀錄，請確認網路連線。")
            except Exception as e:
                st.sidebar.error(f"❌ 同步失敗: {e}")
                
    st.sidebar.markdown("---")
    
    # 資料庫初次確認
    counties = get_all_counties()
    if not counties:
        with st.spinner("首次啟動：正在初始化全台氣象測站資料庫..."):
            raw_json = fetch_weather_data(cwa_key)
            records = parse_weather_json(raw_json)
            save_forecasts(records)
            counties = get_all_counties()
            
    # 縣市篩選選單
    default_county_idx = 0
    for fav in ["臺北市", "台中市", "高雄市", "新北市"]:
        if fav in counties:
            default_county_idx = counties.index(fav)
            break
            
    selected_county = st.sidebar.selectbox(
        "📍 選擇觀測縣市 (County)",
        options=counties,
        index=default_county_idx
    )
    
    # 取得該縣市內之測站清單
    county_stations = get_stations_by_county(selected_county)
    station_names = [f"{s['townName']} - {s['stationName']}" if s.get('townName') else s['stationName'] for s in county_stations]
    
    selected_station_idx = 0
    selected_station_label = st.sidebar.selectbox(
        "🏢 選擇具體測站 (Station)",
        options=station_names,
        index=0 if station_names else None
    )
    
    st.sidebar.markdown("---")
    
    # 資料庫摘要卡片
    total_count = get_total_records_count()
    st.sidebar.markdown(f"""
    <div style="background-color: #F8FAFC; border: 1px solid #E2E8F0; border-radius: 10px; padding: 12px; font-size: 0.85rem; color: #475569;">
        <div style="font-weight: 700; color: #1E293B; margin-bottom: 4px;">📊 資料庫連線狀態</div>
        <div>• 即時觀測測站：<b>{total_count}</b> 站</div>
        <div>• 涵蓋縣市範圍：<b>{len(counties)}</b> 縣市</div>
        <div>• 資料來源代碼：<b>{DATASET_ID}</b></div>
    </div>
    """, unsafe_allow_html=True)
    
    # 取得當前所選測站之觀測數據
    current_station = None
    if county_stations and selected_station_label:
        for s in county_stations:
            label = f"{s['townName']} - {s['stationName']}" if s.get('townName') else s['stationName']
            if label == selected_station_label:
                current_station = s
                break
        if not current_station:
            current_station = county_stations[0]
            
    # 主畫面 Hero Banner
    greeting = get_greeting()
    obs_time_display = current_station['obsTime'].replace("T", " ")[:19] if current_station else datetime.now().strftime("%Y-%m-%d %H:%M")
    
    st.markdown(f"""
    <div class="hero-banner">
        <div class="hero-title">
            <span>🌤️</span> Taiwan Weather Live
        </div>
        <p class="hero-desc">{greeting}！全台 330+ 自動氣象站現在天氣觀測報告 · 實時溫濕度與極值記錄。</p>
        <div class="status-badge">
            <span class="status-dot"></span>
            <span>CWA {DATASET_ID} 即時觀測 · 最新觀測時間：{obs_time_display}</span>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    # 核心氣象 KPI 指標卡
    if current_station:
        air_t = float(current_station['airTemp'])
        max_t = float(current_station['maxT'])
        min_t = float(current_station['minT'])
        hum = current_station.get('relativeHumidity')
        hum_str = f"{hum} %" if hum is not None else "檢測中"
        weather_desc = current_station.get('weather', '良好')
        precip = current_station.get('precipitation', 0.0)
        
        col1, col2, col3, col4, col5 = st.columns(5)
        
        with col1:
            st.markdown(f"""
            <div class="metric-card-box">
                <div class="metric-label">📍 當前觀測站</div>
                <div class="metric-value" style="color: #0F172A; font-size: 1.45rem;">{current_station['stationName']}</div>
                <div class="metric-footer">{current_station['countyName']} {current_station.get('townName','')}</div>
            </div>
            """, unsafe_allow_html=True)
            
        with col2:
            st.markdown(f"""
            <div class="metric-card-box">
                <div class="metric-label">🌡️ 目前即時氣溫</div>
                <div class="metric-value" style="color: #0284C7;">{air_t} <span style="font-size: 1.1rem; font-weight: 500;">°C</span></div>
                <div class="metric-footer">天氣現況: {weather_desc}</div>
            </div>
            """, unsafe_allow_html=True)
            
        with col3:
            st.markdown(f"""
            <div class="metric-card-box">
                <div class="metric-label">🔺 今日最高溫 (Max)</div>
                <div class="metric-value" style="color: #DC2626;">{max_t} <span style="font-size: 1.1rem; font-weight: 500;">°C</span></div>
                <div class="metric-footer">當日最高極值</div>
            </div>
            """, unsafe_allow_html=True)
            
        with col4:
            st.markdown(f"""
            <div class="metric-card-box">
                <div class="metric-label">🔻 今日最低溫 (Min)</div>
                <div class="metric-value" style="color: #3B82F6;">{min_t} <span style="font-size: 1.1rem; font-weight: 500;">°C</span></div>
                <div class="metric-footer">當日最低極值</div>
            </div>
            """, unsafe_allow_html=True)
            
        with col5:
            st.markdown(f"""
            <div class="metric-card-box">
                <div class="metric-label">💧 相對濕度 / 雨量</div>
                <div class="metric-value" style="color: #10B981; font-size: 1.6rem;">{hum_str}</div>
                <div class="metric-footer">累積雨量: {precip} mm</div>
            </div>
            """, unsafe_allow_html=True)
            
        # 生活穿搭建議
        cloth, notice, tip_icon = get_clothing_advice(air_t, max_t, min_t)
        st.markdown(f"""
        <div class="tip-card">
            <div style="font-weight: 700; font-size: 0.95rem; color: #0369A1; margin-bottom: 4px;">
                {tip_icon} 即時天氣生活與穿搭提醒
            </div>
            <div style="font-size: 0.9rem; color: #334155;">
                {cloth} <b>{notice}</b>
            </div>
        </div>
        """, unsafe_allow_html=True)
        
    st.markdown("---")
    
    # 分頁配置
    tab1, tab2, tab3 = st.tabs([
        f"📊 {selected_county} 各測站即時氣溫比較",
        "🗺️ 全台 330+ 測站即時地圖視覺化",
        "📋 氣象測站即時觀測數據表"
    ])
    
    # Tab 1: 縣市內測站即時比較
    with tab1:
        st.markdown(f"#### 📊 **{selected_county}** 轄區內各氣象站即時氣溫排行")
        if county_stations:
            df_county = pd.DataFrame(county_stations) if pd is not None else None
            if df_county is not None and not df_county.empty:
                # 排序
                df_sorted = df_county.sort_values(by="airTemp", ascending=True)
                
                if go is not None:
                    fig = go.Figure()
                    
                    # 橫向長條圖：即時氣溫
                    fig.add_trace(go.Bar(
                        y=df_sorted["townName"] + " - " + df_sorted["stationName"],
                        x=df_sorted["airTemp"],
                        orientation="h",
                        name="即時氣溫",
                        text=[f"{t}°C" for t in df_sorted["airTemp"]],
                        textposition="outside",
                        marker=dict(
                            color=df_sorted["airTemp"],
                            colorscale="Viridis",
                            colorbar=dict(title="氣溫 (°C)")
                        )
                    ))
                    
                    fig.update_layout(
                        title=f"{selected_county} 各測站即時溫度對比",
                        xaxis_title="氣溫 (°C)",
                        yaxis_title="測站名稱",
                        margin=dict(l=20, r=40, t=40, b=20),
                        height=max(380, len(df_sorted) * 36),
                        plot_bgcolor="white",
                        paper_bgcolor="white"
                    )
                    st.plotly_chart(fig, use_container_width=True)
                else:
                    st.dataframe(df_sorted[["stationName", "townName", "airTemp", "maxT", "minT", "relativeHumidity"]], use_container_width=True)
            else:
                st.info("該縣市暫無可用測站數據。")
        else:
            st.info("暫無測站資料。")
            
    # Tab 2: 全台即時地圖
    with tab2:
        st.markdown("#### 🗺️ 全台灣氣象觀測站實時氣溫分佈圖")
        st.markdown("""
        <div style="display: flex; gap: 14px; flex-wrap: wrap; margin-bottom: 12px; font-size: 0.85rem; font-weight: 600;">
            <span style="color: #3B82F6;">🟦 &lt; 20°C (涼爽)</span>
            <span style="color: #10B981;">🟩 20 ~ 25°C (舒適)</span>
            <span style="color: #F59E0B;">🟧 25 ~ 30°C (溫暖)</span>
            <span style="color: #EF4444;">🟥 &gt; 30°C (炎熱)</span>
        </div>
        """, unsafe_allow_html=True)
        
        all_stations = get_all_latest_observations()
        
        if folium is not None and st_folium is not None and all_stations:
            # 建立地圖實例
            m = folium.Map(
                location=[23.75, 120.95],
                zoom_start=7,
                tiles="OpenStreetMap"
            )
            
            for s in all_stations:
                lat = s.get("lat")
                lon = s.get("lon")
                air_t = s.get("airTemp")
                
                # 排除不合理座標
                if not (lat and lon and 21.0 <= lat <= 26.5 and 118.0 <= lon <= 122.5):
                    continue
                    
                color = get_temp_color(air_t)
                popup_html = f"""
                <div style="font-family: sans-serif; min-width: 140px; padding: 4px;">
                    <h4 style="margin: 0 0 6px 0; color: #0284C7; font-size: 15px;">📍 {s['countyName']} - {s['stationName']}</h4>
                    <hr style="margin: 4px 0; border: none; border-top: 1px solid #E2E8F0;" />
                    <div style="font-size: 12px; color: #64748B; margin-bottom: 4px;">鄉鎮區: {s.get('townName','')}</div>
                    <div style="display: flex; justify-content: space-between; margin: 2px 0;">
                        <span>🌡️ 目前氣溫:</span><b style="color: {color};">{air_t} °C</b>
                    </div>
                    <div style="display: flex; justify-content: space-between; margin: 2px 0;">
                        <span>🔺 今日最高:</span><b style="color: #EF4444;">{s.get('maxT')} °C</b>
                    </div>
                    <div style="display: flex; justify-content: space-between; margin: 2px 0;">
                        <span>🔻 今日最低:</span><b style="color: #3B82F6;">{s.get('minT')} °C</b>
                    </div>
                    <div style="display: flex; justify-content: space-between; margin: 2px 0;">
                        <span>💧 相對濕度:</span><b>{s.get('relativeHumidity')}%</b>
                    </div>
                    <div style="display: flex; justify-content: space-between; margin: 2px 0;">
                        <span>☁️ 天氣狀況:</span><b>{s.get('weather','良好')}</b>
                    </div>
                </div>
                """
                
                is_selected = (s.get("countyName") == selected_county)
                folium.CircleMarker(
                    location=[lat, lon],
                    radius=8 if is_selected else 5,
                    popup=folium.Popup(popup_html, max_width=270),
                    tooltip=f"{s['countyName']} {s['stationName']}: {air_t}°C ({s.get('weather','良好')})",
                    color="#0F172A" if is_selected else color,
                    fill=True,
                    fill_color=color,
                    fill_opacity=0.9 if is_selected else 0.7,
                    weight=2 if is_selected else 1
                ).add_to(m)
                
            st_folium(m, width="100%", height=520)
        else:
            st.info("地圖模組載入中或未安裝...")

    # Tab 3: 詳細數據表
    with tab3:
        st.markdown(f"#### 📋 **{selected_county}** 各測站即時數據一覽")
        if county_stations:
            df_display = pd.DataFrame(county_stations) if pd is not None else None
            if df_display is not None and not df_display.empty:
                cols = {
                    "stationId": "測站代碼",
                    "stationName": "測站名稱",
                    "townName": "鄉鎮區",
                    "airTemp": "即時氣溫 (°C)",
                    "maxT": "今日最高溫 (°C)",
                    "minT": "今日最低溫 (°C)",
                    "relativeHumidity": "相對濕度 (%)",
                    "weather": "天氣狀況",
                    "precipitation": "累積雨量 (mm)",
                    "obsTime": "觀測時間"
                }
                valid_cols = [c for c in cols.keys() if c in df_display.columns]
                show_df = df_display[valid_cols].rename(columns=cols)
                st.dataframe(show_df, use_container_width=True, hide_index=True)
                
                csv_data = show_df.to_csv(index=False).encode("utf-8-sig")
                st.download_button(
                    label="📥 下載此縣市觀測 CSV",
                    data=csv_data,
                    file_name=f"{selected_county}_stations_weather.csv",
                    mime="text/csv"
                )
        else:
            st.info("暫無數據。")
            
    st.markdown("---")
    st.markdown("""
    <div style="text-align: center; color: #94A3B8; font-size: 0.82rem; padding: 10px 0;">
        交通部中央氣象署 (CWA) Open Data · 資料集代碼: O-A0003-001 · 實時更新
    </div>
    """, unsafe_allow_html=True)


if __name__ == "__main__":
    main()
