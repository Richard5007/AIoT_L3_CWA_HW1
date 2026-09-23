"""
app.py - Taiwan Weather Forecast 互動式天氣預報 Web 應用 (Modern UI Edition)
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
    page_title="Taiwan Weather Forecast - 智慧天氣預報儀表板",
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
        background: linear-gradient(135deg, #1e3a8a 0%, #2563eb 50%, #06b6d4 100%);
        border-radius: 16px;
        padding: 28px 32px;
        color: white;
        margin-bottom: 24px;
        box-shadow: 0 10px 25px -5px rgba(37, 99, 235, 0.25);
        position: relative;
        overflow: hidden;
    }
    
    .hero-title {
        font-size: 2.1rem;
        font-weight: 800;
        letter-spacing: -0.02em;
        margin: 0 0 8px 0;
        display: flex;
        align-items: center;
        gap: 12px;
    }
    
    .hero-desc {
        font-size: 1.05rem;
        opacity: 0.92;
        margin: 0;
        font-weight: 400;
    }
    
    .status-badge {
        display: inline-flex;
        align-items: center;
        gap: 6px;
        background: rgba(255, 255, 255, 0.18);
        backdrop-filter: blur(10px);
        padding: 6px 14px;
        border-radius: 9999px;
        font-size: 0.82rem;
        font-weight: 600;
        margin-top: 14px;
        border: 1px solid rgba(255, 255, 255, 0.25);
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
        padding: 20px 22px;
        border: 1px solid #E5E7EB;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05), 0 2px 4px -1px rgba(0, 0, 0, 0.03);
        transition: transform 0.2s ease, box-shadow 0.2s ease;
    }
    
    .metric-card-box:hover {
        transform: translateY(-2px);
        box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.08);
    }

    .metric-label {
        font-size: 0.88rem;
        font-weight: 600;
        color: #6B7280;
        margin-bottom: 6px;
        display: flex;
        align-items: center;
        gap: 6px;
    }
    
    .metric-value {
        font-size: 1.95rem;
        font-weight: 800;
        letter-spacing: -0.02em;
        line-height: 1.2;
    }
    
    .metric-footer {
        margin-top: 8px;
        font-size: 0.8rem;
        color: #9CA3AF;
        display: flex;
        align-items: center;
        gap: 4px;
    }

    /* 生活建議小卡 */
    .tip-card {
        background: #F8FAFC;
        border-left: 4px solid #3B82F6;
        border-radius: 0 12px 12px 0;
        padding: 16px 20px;
        margin: 16px 0;
    }

    /* 標籤頁美化 */
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
    }
    
    .stTabs [data-baseweb="tab"] {
        border-radius: 8px 8px 0 0;
        padding: 10px 20px;
        font-weight: 600;
    }
</style>
""", unsafe_allow_html=True)


def get_temp_color(avg_temp: float) -> str:
    """依據平均溫度返回圖層色彩 (Step 17 溫度色階)"""
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


def get_clothing_advice(max_t: float, min_t: float) -> tuple:
    """智慧穿搭與天氣建議"""
    diff = max_t - min_t
    if max_t >= 30:
        cloth = "天氣炎熱，建議穿著透氣排汗短袖衣服，注意防曬並多補充水分。"
        icon = "☀️"
    elif max_t >= 25:
        cloth = "氣候溫和舒適，適合穿著休閒短袖或薄長袖。"
        icon = "🌤️"
    elif max_t >= 20:
        cloth = "體感略顯涼爽，建議著長袖衣物並隨身備好外套。"
        icon = "🧥"
    else:
        cloth = "天氣偏冷，請注意保暖，建議搭配厚外套或毛衣。"
        icon = "🧣"
        
    notice = "早晚溫差顯著 (超過 7°C)，外出建議洋蔥式穿搭。" if diff >= 7 else "早晚氣溫穩定，舒適宜人。"
    return cloth, notice, icon


def main():
    # 初始化資料庫
    init_db()
    
    # 側邊欄 (Sidebar)
    st.sidebar.markdown("### 🌤️ **氣象設定與操作**")
    st.sidebar.caption("交通部中央氣象署 Open Data API 串接")
    
    # 背景自動讀取 API Key (無痕安全機制)
    cwa_key = load_cwa_api_key()
    
    # 手動即時同步按鈕
    if st.sidebar.button("🔄 同步氣象署最新預報", use_container_width=True, type="primary"):
        with st.spinner("正在自中央氣象署拉取最新預報數據..."):
            try:
                raw_json = fetch_weather_data(cwa_key)
                records = parse_weather_json(raw_json)
                if records:
                    saved = save_forecasts(records)
                    st.sidebar.success(f"✅ 同步成功！已更新 {saved} 筆氣象紀錄。")
                else:
                    st.sidebar.warning("⚠️ 未取得任何紀錄，請確認網路連線。")
            except Exception as e:
                st.sidebar.error(f"❌ 同步失敗: {e}")
                
    st.sidebar.markdown("---")
    
    # 檢查資料庫是否有預存資料
    regions = get_all_regions()
    if not regions:
        with st.spinner("首次啟動：正在初始化全台氣溫資料庫..."):
            raw_json = fetch_weather_data(cwa_key)
            records = parse_weather_json(raw_json)
            save_forecasts(records)
            regions = get_all_regions()
            
    dates = get_all_dates()
    
    # 預報地區選擇
    default_idx = 0
    for fav in ["臺北市", "台中市", "高雄市", "北部地區"]:
        if fav in regions:
            default_idx = regions.index(fav)
            break
            
    selected_region = st.sidebar.selectbox(
        "📍 選擇觀測縣市 / 地區",
        options=regions,
        index=default_idx
    )
    
    # 預報時段選擇
    selected_date = st.sidebar.selectbox(
        "📅 選擇預報時段",
        options=dates,
        index=0 if dates else None
    )
    
    st.sidebar.markdown("---")
    
    # 側邊欄資料庫狀態卡片
    total_count = get_total_records_count()
    st.sidebar.markdown(f"""
    <div style="background-color: #F8FAFC; border: 1px solid #E2E8F0; border-radius: 10px; padding: 14px; font-size: 0.86rem; color: #475569;">
        <div style="font-weight: 700; color: #1E293B; margin-bottom: 6px;">📊 系統資料庫狀態</div>
        <div>• 累積氣溫紀錄：<b>{total_count}</b> 筆</div>
        <div>• 涵蓋觀測縣市：<b>{len(regions)}</b> 處</div>
        <div>• 資料庫防護：<b>Idempotency 已啟動</b></div>
    </div>
    """, unsafe_allow_html=True)
    
    # 主畫面 Hero Banner
    greeting = get_greeting()
    now_time_str = datetime.now().strftime("%Y-%m-%d %H:%M")
    
    st.markdown(f"""
    <div class="hero-banner">
        <div class="hero-title">
            <span>🌤️</span> Taiwan Weather Forecast
        </div>
        <p class="hero-desc">{greeting}！即時台灣各地天氣預報、多日氣溫走勢與地理資訊視覺化看板。</p>
        <div class="status-badge">
            <span class="status-dot"></span>
            <span>CWA Open Data 連線中 · 系統時間 {now_time_str}</span>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    # 載入所選地區預報資料
    region_data = get_forecasts_by_region(selected_region)
    if pd is not None and isinstance(region_data, pd.DataFrame):
        df_region = region_data
    elif pd is not None and isinstance(region_data, list):
        df_region = pd.DataFrame(region_data)
    else:
        df_region = None
        
    # KPI 核心氣溫指標卡
    if df_region is not None and not df_region.empty:
        match_row = df_region[df_region["dataDate"] == selected_date]
        current_item = match_row.iloc[0] if not match_row.empty else df_region.iloc[0]
        
        min_val = float(current_item['minT'])
        max_val = float(current_item['maxT'])
        diff_val = round(max_val - min_val, 1)
        avg_val = round((max_val + min_val) / 2.0, 1)
        
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.markdown(f"""
            <div class="metric-card-box">
                <div class="metric-label">📍 當前觀測地區</div>
                <div class="metric-value" style="color: #1E3A8A;">{selected_region}</div>
                <div class="metric-footer">時段: {current_item['dataDate']}</div>
            </div>
            """, unsafe_allow_html=True)
            
        with col2:
            st.markdown(f"""
            <div class="metric-card-box">
                <div class="metric-label">🔥 最高氣溫 (MaxT)</div>
                <div class="metric-value" style="color: #DC2626;">{max_val} <span style="font-size: 1.1rem; font-weight: 500;">°C</span></div>
                <div class="metric-footer">預估日間最高體感</div>
            </div>
            """, unsafe_allow_html=True)
            
        with col3:
            st.markdown(f"""
            <div class="metric-card-box">
                <div class="metric-label">❄️ 最低氣溫 (MinT)</div>
                <div class="metric-value" style="color: #2563EB;">{min_val} <span style="font-size: 1.1rem; font-weight: 500;">°C</span></div>
                <div class="metric-footer">預估夜間清晨最低溫</div>
            </div>
            """, unsafe_allow_html=True)
            
        with col4:
            st.markdown(f"""
            <div class="metric-card-box">
                <div class="metric-label">⚖️ 預報溫差 (Range)</div>
                <div class="metric-value" style="color: #7C3AED;">{diff_val} <span style="font-size: 1.1rem; font-weight: 500;">°C</span></div>
                <div class="metric-footer">平均溫: {avg_val}°C</div>
            </div>
            """, unsafe_allow_html=True)
            
        # 智慧生活與穿搭推薦小卡 (Step 22 延伸應用展示)
        cloth, notice, tip_icon = get_clothing_advice(max_val, min_val)
        st.markdown(f"""
        <div class="tip-card">
            <div style="font-weight: 700; font-size: 0.96rem; color: #1E3A8A; margin-bottom: 4px;">
                {tip_icon} 智慧穿搭與生活提醒（AIoT 助理）
            </div>
            <div style="font-size: 0.9rem; color: #334155;">
                {cloth} <b>{notice}</b>
            </div>
        </div>
        """, unsafe_allow_html=True)

    # 主分頁結構
    tab1, tab2, tab3 = st.tabs([
        "📈 氣溫趨勢折線圖 (Step 14)",
        "🗺️ 全台氣溫地圖視覺化 (Step 17 & 18)",
        "📋 預報數據清單與導出 (Step 15)"
    ])
    
    # Tab 1: 氣溫走勢圖
    with tab1:
        st.markdown(f"#### 📊 **{selected_region}** 氣溫變化預報圖")
        if df_region is not None and not df_region.empty:
            if go is not None:
                fig = go.Figure()
                
                # 填充溫差區域
                fig.add_trace(go.Scatter(
                    x=df_region["dataDate"],
                    y=df_region["maxT"],
                    mode="lines",
                    line=dict(width=0),
                    showlegend=False,
                    hoverinfo="skip"
                ))
                fig.add_trace(go.Scatter(
                    x=df_region["dataDate"],
                    y=df_region["minT"],
                    mode="lines",
                    line=dict(width=0),
                    fill="tonexty",
                    fillcolor="rgba(59, 130, 246, 0.08)",
                    name="氣溫波動範圍",
                    hoverinfo="skip"
                ))
                
                # 最高溫線 (紅色漸層)
                fig.add_trace(go.Scatter(
                    x=df_region["dataDate"],
                    y=df_region["maxT"],
                    mode="lines+markers+text",
                    name="最高溫 (MaxT)",
                    text=[f"{v}°" for v in df_region["maxT"]],
                    textposition="top center",
                    line=dict(color="#EF4444", width=3, shape="spline"),
                    marker=dict(size=9, color="#EF4444", symbol="circle", line=dict(color="white", width=2))
                ))
                
                # 最低溫線 (藍色漸層)
                fig.add_trace(go.Scatter(
                    x=df_region["dataDate"],
                    y=df_region["minT"],
                    mode="lines+markers+text",
                    name="最低溫 (MinT)",
                    text=[f"{v}°" for v in df_region["minT"]],
                    textposition="bottom center",
                    line=dict(color="#3B82F6", width=3, shape="spline"),
                    marker=dict(size=9, color="#3B82F6", symbol="circle", line=dict(color="white", width=2))
                ))
                
                fig.update_layout(
                    margin=dict(l=20, r=20, t=35, b=20),
                    height=420,
                    xaxis=dict(
                        title="預報時段 / 日期",
                        showgrid=True,
                        gridcolor="#F3F4F6",
                        linecolor="#E5E7EB"
                    ),
                    yaxis=dict(
                        title="溫度 (°C)",
                        showgrid=True,
                        gridcolor="#F3F4F6",
                        linecolor="#E5E7EB"
                    ),
                    legend=dict(
                        orientation="h",
                        yanchor="bottom",
                        y=1.02,
                        xanchor="right",
                        x=1
                    ),
                    hovermode="x unified",
                    plot_bgcolor="white",
                    paper_bgcolor="white"
                )
                st.plotly_chart(fig, use_container_width=True)
            else:
                chart_df = df_region.set_index("dataDate")[["minT", "maxT"]]
                st.line_chart(chart_df)
        else:
            st.info("尚無該地區之氣溫數據。")

    # Tab 2: 台灣地圖視覺化
    with tab2:
        st.markdown(f"#### 🗺️ 台灣全區氣溫分佈圖 ({selected_date or '最新時段'})")
        st.markdown("""
        <div style="display: flex; gap: 14px; flex-wrap: wrap; margin-bottom: 12px; font-size: 0.85rem; font-weight: 600;">
            <span style="color: #3B82F6;">🟦 &lt; 20°C (寒冷涼爽)</span>
            <span style="color: #10B981;">🟩 20 ~ 25°C (舒適適中)</span>
            <span style="color: #F59E0B;">🟧 25 ~ 30°C (溫暖微熱)</span>
            <span style="color: #EF4444;">🟥 &gt; 30°C (炎熱高溫)</span>
        </div>
        """, unsafe_allow_html=True)
        
        date_records = get_forecasts_by_date(selected_date) if selected_date else []
        
        if folium is not None and st_folium is not None:
            # 建立地圖實例
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
                    <div style="font-family: sans-serif; min-width: 140px; padding: 4px;">
                        <h4 style="margin: 0 0 6px 0; color: #1E3A8A; font-size: 15px;">📍 {r_name}</h4>
                        <hr style="margin: 4px 0; border: none; border-top: 1px solid #E2E8F0;" />
                        <div style="font-size: 12px; color: #64748B; margin-bottom: 4px;">時段: {item['dataDate']}</div>
                        <div style="display: flex; justify-content: space-between; margin: 2px 0;">
                            <span>🔺 最高溫:</span><b style="color: #EF4444;">{max_t} °C</b>
                        </div>
                        <div style="display: flex; justify-content: space-between; margin: 2px 0;">
                            <span>🔻 最低溫:</span><b style="color: #3B82F6;">{min_t} °C</b>
                        </div>
                        <div style="display: flex; justify-content: space-between; margin: 2px 0;">
                            <span>⚖️ 平均溫:</span><b>{avg_t} °C</b>
                        </div>
                    </div>
                    """
                    folium.CircleMarker(
                        location=coords,
                        radius=11,
                        popup=folium.Popup(popup_html, max_width=260),
                        tooltip=f"{r_name}: {min_t}°C ~ {max_t}°C (均溫 {avg_t}°C)",
                        color=color,
                        fill=True,
                        fill_color=color,
                        fill_opacity=0.85,
                        weight=2
                    ).add_to(m)
            
            st_folium(m, width="100%", height=500)
        else:
            st.info("💡 提示：安裝 `folium` 與 `streamlit-folium` 可體驗高畫質台灣互動地圖。")
            if date_records:
                map_df = pd.DataFrame(date_records)
                st.dataframe(map_df, use_container_width=True)

    # Tab 3: 預報數據清單
    with tab3:
        st.markdown(f"#### 📋 **{selected_region}** 預報詳細數據清單")
        if df_region is not None and not df_region.empty:
            display_df = df_region.rename(columns={
                "regionName": "觀測地區",
                "dataDate": "預報時段",
                "minT": "最低氣溫 (°C)",
                "maxT": "最高氣溫 (°C)",
                "avgT": "平均氣溫 (°C)"
            })
            st.dataframe(display_df, use_container_width=True, hide_index=True)
            
            csv_data = display_df.to_csv(index=False).encode("utf-8-sig")
            st.download_button(
                label="📥 下載本區預報數據 (CSV)",
                data=csv_data,
                file_name=f"{selected_region}_weather_forecast.csv",
                mime="text/csv",
                use_container_width=False
            )
        else:
            st.info("暫無結構化數據。")
            
    st.markdown("---")
    st.markdown("""
    <div style="text-align: center; color: #94A3B8; font-size: 0.82rem; padding: 12px 0;">
        AIoT Lesson 3 Homework 1 · Central Weather Administration (CWA) Open Data · Developed with Streamlit
    </div>
    """, unsafe_allow_html=True)


if __name__ == "__main__":
    main()
