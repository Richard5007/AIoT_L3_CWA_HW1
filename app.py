"""
app.py - Taiwan Weather Forecast 互動式天氣預報 Web 應用
符合專案工作流程 Steps 11 ~ 19 之全套介面設計
使用 Streamlit + Plotly + Folium + SQLite
"""

import os
import sys
from datetime import datetime

# 設置標準輸出編碼
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

import streamlit as st

# 檢查可選依賴項
try:
    import pandas as pd
except ImportError:
    pd = None

try:
    import plotly.graph_objects as go
except ImportError:
    go = None

try:
    import folium
    from streamlit_folium import st_folium
except ImportError:
    folium = None
    st_folium = None

from database import (
    init_db,
    save_forecasts,
    get_all_regions,
    get_all_dates,
    get_forecasts_by_region,
    get_forecasts_by_date,
    get_total_records_count
)
from cwa_service import (
    fetch_weather_data,
    parse_weather_json,
    load_cwa_api_key,
    TAIWAN_LOCATION_COORDS
)

# 頁面配置
st.set_page_config(
    page_title="Taiwan Weather Forecast - 氣象預報儀表板",
    page_icon="🌤️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 樣式自訂
st.markdown("""
<style>
    .main-title {
        font-size: 2.2rem;
        font-weight: 700;
        color: #1E3A8A;
        margin-bottom: 0.2rem;
    }
    .sub-title {
        font-size: 1.05rem;
        color: #4B5563;
        margin-bottom: 1.5rem;
    }
    .metric-card {
        background-color: #F3F4F6;
        border-radius: 8px;
        padding: 12px;
        text-align: center;
    }
</style>
""", unsafe_allow_html=True)


def get_temp_color(avg_temp: float) -> str:
    """依據平均溫度返回圖層色彩 (Step 17 溫度色階)"""
    if avg_temp < 20:
        return "#3B82F6"  # 藍色 (<20°C)
    elif avg_temp <= 25:
        return "#10B981"  # 綠色 (20-25°C)
    elif avg_temp <= 30:
        return "#F59E0B"  # 橙色 (25-30°C)
    else:
        return "#EF4444"  # 紅色 (>30°C)


def main():
    # 確保資料庫初始化
    init_db()
    
    # 側邊欄 (Sidebar) 控制面板
    st.sidebar.title("⚙️ 控制面板")
    st.sidebar.markdown("---")
    
    # API Key 設定 (Step 3 & 4)
    default_key = load_cwa_api_key()
    api_key_input = st.sidebar.text_input(
        "CWA 授權碼 (API Key)",
        value=default_key,
        type="password",
        help="中央氣象署 Open Data 授權碼，留空或無效時將使用模擬數據。"
    )
    
    # 手動同步資料按鈕
    if st.sidebar.button("🔄 從氣象署同步最新資料", use_container_width=True):
        with st.spinner("正在向中央氣象署請求最新預報資料..."):
            try:
                raw_json = fetch_weather_data(api_key_input)
                records = parse_weather_json(raw_json)
                if records:
                    saved = save_forecasts(records)
                    st.sidebar.success(f"同步成功！已更新 {saved} 筆氣象紀錄。")
                else:
                    st.sidebar.warning("未取得任何紀錄，請檢查 API Key 是否正確。")
            except Exception as e:
                st.sidebar.error(f"同步失敗: {e}")
                
    st.sidebar.markdown("---")
    
    # 檢查資料庫是否有資料，若無則自動執行一次同步
    regions = get_all_regions()
    if not regions:
        with st.spinner("首次啟動：正在初始化預報數據..."):
            raw_json = fetch_weather_data(api_key_input)
            records = parse_weather_json(raw_json)
            save_forecasts(records)
            regions = get_all_regions()
            
    dates = get_all_dates()
    
    # 下拉選單選擇地區 (Step 13)
    default_region_idx = 0
    if "臺北市" in regions:
        default_region_idx = regions.index("臺北市")
    elif "北部地區" in regions:
        default_region_idx = regions.index("北部地區")
        
    selected_region = st.sidebar.selectbox(
        "📍 選擇預報地區 (Region)",
        options=regions,
        index=default_region_idx
    )
    
    # 選擇日期 / 時段 (Step 18)
    selected_date = st.sidebar.selectbox(
        "📅 選擇預報時段 (Date / Time)",
        options=dates,
        index=0 if dates else None
    )
    
    st.sidebar.markdown("---")
    total_count = get_total_records_count()
    st.sidebar.info(f"📊 資料庫狀態：\n- 總紀錄數：{total_count} 筆\n- 涵蓋地區數：{len(regions)} 處")
    
    # 主頁面頂部標題
    st.markdown('<div class="main-title">🌤️ Taiwan Weather Forecast 互動式天氣預報應用</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-title">AI 創新微課程：CWA API × JSON × Python × SQLite × Streamlit × Folium</div>', unsafe_allow_html=True)
    
    # 載入所選地區資料 (Step 12)
    region_data = get_forecasts_by_region(selected_region)
    if pd is not None and isinstance(region_data, pd.DataFrame):
        df_region = region_data
    elif pd is not None and isinstance(region_data, list):
        df_region = pd.DataFrame(region_data)
    else:
        df_region = None
        
    # KPI 指標區塊 (Metrics)
    if df_region is not None and not df_region.empty:
        # 取所選日期或最新一筆資料
        match_row = df_region[df_region["dataDate"] == selected_date]
        current_item = match_row.iloc[0] if not match_row.empty else df_region.iloc[0]
        
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("📍 觀測地區", selected_region)
        with col2:
            st.metric("🔺 最高氣溫 (MaxT)", f"{current_item['maxT']} °C")
        with col3:
            st.metric("🔻 最低氣溫 (MinT)", f"{current_item['minT']} °C")
        with col4:
            temp_diff = round(float(current_item['maxT']) - float(current_item['minT']), 1)
            st.metric("🌡️ 預估溫差", f"{temp_diff} °C")
    
    st.markdown("---")
    
    # 分頁配置：圖表與表格 / 台灣互動地圖
    tab1, tab2, tab3 = st.tabs(["📈 氣溫走勢圖 (Step 14)", "📋 詳細預報表格 (Step 15)", "🗺️ 台灣地圖視覺化 (Step 17 & 18)"])
    
    # Tab 1: 繪製折線圖 (Step 14)
    with tab1:
        st.subheader(f"📊 {selected_region} 氣溫預報走勢")
        if df_region is not None and not df_region.empty:
            if go is not None:
                fig = go.Figure()
                # 最高溫線 (紅色)
                fig.add_trace(go.Scatter(
                    x=df_region["dataDate"],
                    y=df_region["maxT"],
                    mode="lines+markers+text",
                    name="最高溫 (MaxT)",
                    text=[f"{val}°C" for val in df_region["maxT"]],
                    textposition="top center",
                    line=dict(color="#EF4444", width=3),
                    marker=dict(size=8)
                ))
                # 最低溫線 (藍色)
                fig.add_trace(go.Scatter(
                    x=df_region["dataDate"],
                    y=df_region["minT"],
                    mode="lines+markers+text",
                    name="最低溫 (MinT)",
                    text=[f"{val}°C" for val in df_region["minT"]],
                    textposition="bottom center",
                    line=dict(color="#3B82F6", width=3),
                    marker=dict(size=8)
                ))
                fig.update_layout(
                    title=f"{selected_region} 一週/時段氣溫預報折線圖",
                    xaxis_title="預報時段 / 日期",
                    yaxis_title="溫度 (°C)",
                    hovermode="x unified",
                    template="plotly_white",
                    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
                )
                st.plotly_chart(fig, use_container_width=True)
            else:
                # 簡易 Streamlit 原生圖表備援
                chart_df = df_region.set_index("dataDate")[["minT", "maxT"]]
                st.line_chart(chart_df)
        else:
            st.info("尚無該地區之氣溫數據。")
            
    # Tab 2: 顯示資料表格 (Step 15)
    with tab2:
        st.subheader(f"📋 {selected_region} 結構化數據清單")
        if df_region is not None and not df_region.empty:
            display_df = df_region.rename(columns={
                "regionName": "地區",
                "dataDate": "預報時段",
                "minT": "最低氣溫 (°C)",
                "maxT": "最高氣溫 (°C)",
                "avgT": "平均氣溫 (°C)"
            })
            st.dataframe(display_df, use_container_width=True, hide_index=True)
            
            # CSV 下載按鈕
            csv_data = display_df.to_csv(index=False).encode("utf-8-sig")
            st.download_button(
                label="📥 下載此地區預報 CSV",
                data=csv_data,
                file_name=f"{selected_region}_weather_forecast.csv",
                mime="text/csv"
            )
        else:
            st.info("暫無表格數據。")
            
    # Tab 3: 台灣地圖視覺化 (Step 17 & 18)
    with tab3:
        st.subheader(f"🗺️ 台灣全區氣溫分佈地圖 ({selected_date or '最新時段'})")
        st.caption("色彩說明：🟦 <20°C (寒冷) | 🟩 20-25°C (舒適) | 🟧 25-30°C (溫暖) | 🟥 >30°C (炎熱)")
        
        date_records = get_forecasts_by_date(selected_date) if selected_date else []
        
        if folium is not None and st_folium is not None:
            # 建立 Folium 地圖物件 (中心定位於台灣)
            m = folium.Map(
                location=[23.75, 120.95],
                zoom_start=7,
                tiles="OpenStreetMap"
            )
            
            for item in date_records:
                r_name = item["regionName"]
                min_t = item["minT"]
                max_t = item["maxT"]
                avg_t = item.get("avgT", round((min_t + max_t) / 2.0, 1))
                
                coords = TAIWAN_LOCATION_COORDS.get(r_name)
                if coords:
                    color = get_temp_color(avg_t)
                    popup_html = f"""
                    <div style="font-family: sans-serif; min-width: 130px;">
                        <h4 style="margin: 0 0 6px 0; color: #1E3A8A;">{r_name}</h4>
                        <hr style="margin: 4px 0;" />
                        <p style="margin: 2px 0;"><b>預報時段:</b> {item['dataDate']}</p>
                        <p style="margin: 2px 0; color: #EF4444;"><b>最高溫:</b> {max_t} °C</p>
                        <p style="margin: 2px 0; color: #3B82F6;"><b>最低溫:</b> {min_t} °C</p>
                        <p style="margin: 2px 0;"><b>平均溫:</b> {avg_t} °C</p>
                    </div>
                    """
                    folium.CircleMarker(
                        location=coords,
                        radius=11,
                        popup=folium.Popup(popup_html, max_width=250),
                        tooltip=f"{r_name}: {min_t}°C ~ {max_t}°C (均溫 {avg_t}°C)",
                        color=color,
                        fill=True,
                        fill_color=color,
                        fill_opacity=0.85,
                        weight=2
                    ).add_to(m)
            
            st_folium(m, width="100%", height=520)
        else:
            # 當 Folium 尚未安裝時之替代視覺化呈現
            st.info("💡 提示：安裝 `folium` 與 `streamlit-folium` 可解鎖互動式台灣地圖。")
            if date_records:
                map_df = pd.DataFrame(date_records)
                st.dataframe(map_df, use_container_width=True)
                
    st.markdown("---")
    st.caption("AIoT Lesson 3 Homework 1 | 氣象資料來源：交通部中央氣象署 Open Data Platform | MIT License")


if __name__ == "__main__":
    main()
