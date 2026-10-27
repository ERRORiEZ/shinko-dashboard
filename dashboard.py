import streamlit as st
import pandas as pd
import time
from supabase import create_client, Client

# ==========================================
# 1. ตั้งค่าหน้าเว็บและสไตล์ (CSS)
# ==========================================
st.set_page_config(page_title="Turbine Monitoring System", page_icon="⚙️", layout="wide")

st.markdown("""
<style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    h1, h2, h3 { color: #1E3A8A; }
    .latest-time { color: #e11d48; font-weight: bold; font-size: 1.2rem; }
    .status-live { color: #10b981; font-weight: bold; }
</style>
""", unsafe_allow_html=True)

st.title("⚙️ Turbine Monitoring & Revenue Dashboard")
st.markdown("ระบบมอนิเตอร์ประสิทธิภาพและสรุปรายได้กังหันไฟฟ้าแบบเรียลไทม์")
st.markdown("---")

# ==========================================
# 2. ตั้งค่าการเชื่อมต่อ Supabase
# ==========================================
SUPABASE_URL = "https://egjpkwgyrhsmajkumnyc.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImVnanBrd2d5cmhzbWFqa3VtbnljIiwicm9sZSI6ImFub24iLCJpYXQiOjE3OTI1MjkzOTYsImV4cCI6MjEwODEwNTM5Nn0.klAeK81K7_ZI_1Z5ow8CeIcJLZ26LxoReJzcf-ETPGo"

@st.cache_resource
def init_connection():
    return create_client(SUPABASE_URL, SUPABASE_KEY)
    
supabase = init_connection()

# ==========================================
# 3. ฟังก์ชันดึงข้อมูล 
# ==========================================
@st.cache_data(ttl=2) 
def load_data():
    response = supabase.table("shinko_data").select("*").execute()
    df = pd.DataFrame(response.data)
    
    if not df.empty:
        df['created_at'] = pd.to_datetime(df['created_at']).dt.tz_convert('Asia/Bangkok')
        df['date_only'] = df['created_at'].dt.date
        
        # แปลงเฉพาะคอลัมน์ที่เป็นตัวเลขจริงๆ (เว้นคอลัมน์ที่เป็นเวลา วันที่ หรือไอดีไว้)
        skip_cols = ['id', 'created_at', 'date_only']
        for col in df.columns:
            if col not in skip_cols and not ('time' in col.lower() or 'date' in col.lower() or 'stamp' in col.lower()):
                df[col] = pd.to_numeric(df[col].astype(str).str.replace(',', ''), errors='coerce')
        
        df = df.sort_values('created_at')
        
    return df

@st.cache_data(ttl=2) 
def load_logs_data():
    try:
        response = supabase.table("turbine_logs").select("*").execute()
        df_logs = pd.DataFrame(response.data)
        if not df_logs.empty and 'created_at' in df_logs.columns:
            df_logs['created_at'] = pd.to_datetime(df_logs['created_at']).dt.tz_convert('Asia/Bangkok')
            df_logs = df_logs.sort_values('created_at', ascending=False)
        return df_logs
    except:
        return pd.DataFrame()

df = load_data()
df_logs = load_logs_data()

# ==========================================
# 4. ส่วนแสดงผลหน้า Dashboard
# ==========================================
if df.empty:
    st.warning("⏳ ยังไม่มีข้อมูลในระบบ หรือกำลังเชื่อมต่อฐานข้อมูล...")
else:
    # ---------------- Sidebar ----------------
    with st.sidebar:
        st.header("⚡ ควบคุมระบบ Real-time")
        
        auto_refresh = st.toggle("เปิดโหมด Auto-Refresh (ทุก 60 วิ)", value=False)
        
        if auto_refresh:
            st.success("🟢 ระบบกำลังดึงข้อมูลอัตโนมัติ")
        else:
            st.info("⚪ ระบบหยุดดึงข้อมูลอัตโนมัติ")
            
        if st.button("🔄 ดึงข้อมูลทันที (Manual)", use_container_width=True):
            st.cache_data.clear()
            st.rerun()
            
        st.markdown("---")
        st.header("⚙️ ตั้งค่าระบบ")
        electric_rate = st.number_input("💵 อัตราค่าไฟ (บาท/หน่วย)", value=4.0, step=0.1)
        
        available_dates = df['date_only'].unique()
        selected_date = st.selectbox("📅 เลือกวันที่ต้องการดูข้อมูล", available_dates, index=len(available_dates)-1)
        st.caption("Developed for Senior Project")

    daily_df = df[df['date_only'] == selected_date].copy()
    
    if not daily_df.empty:
        watt_max = daily_df['watt_hour'].max() if 'watt_hour' in daily_df.columns else 0
        watt_min = daily_df['watt_hour'].min() if 'watt_hour' in daily_df.columns else 0
        daily_production = watt_max - watt_min
        daily_revenue = daily_production * 1000 * electric_rate
        
        tab1, tab2 = st.tabs(["🔴 สถานะเครื่องจักร (Live Status)", "📊 สรุปภาพรวม (Summary)"])
        
        # ---------------- หน้าต่างที่ 1: ข้อมูลเรียลไทม์ ----------------
        with tab1:
            display_df = daily_df.sort_values('created_at', ascending=False)
            latest_data = display_df.iloc[0] 
            latest_time = latest_data['created_at'].strftime('%H:%M:%S')
            
            st.subheader("🔴 มอนิเตอร์ค่าเซ็นเซอร์ทุกพารามิเตอร์แบบเรียลไทม์")
            if auto_refresh:
                st.markdown(f"สถานะ: <span class='status-live'>Live 🟢</span> | อัปเดตข้อมูลล่าสุดเมื่อเวลา: <span class='latest-time'>{latest_time}</span>", unsafe_allow_html=True)
            else:
                st.markdown(f"สถานะ: ออฟไลน์ ⚪ | อัปเดตข้อมูลล่าสุดเมื่อเวลา: <span class='latest-time'>{latest_time}</span>", unsafe_allow_html=True)
            st.markdown("<br>", unsafe_allow_html=True)
            
            exclude_cols = ['id', 'created_at', 'date_only']
            all_sensor_cols = [col for col in latest_data.index if col not in exclude_cols]
            
            def get_unit(col_name):
                name = col_name.lower()
                if 'time' in name or 'date' in name or 'stamp' in name:
                    return ""
                elif 'temp' in name:
                    return "°C"
                elif 'press' in name or 'pressure' in name:
                    return "bar"
                elif 'speed' in name or 'rpm' in name:
                    return "RPM"
                elif 'watt' in name or 'power' in name or 'generator' in name:
                    return "kW"
                elif 'rate' in name:
                    return "%"
                elif 'flow' in name:
                    return "m³/h"
                else:
                    return ""

            header_colors = ["#f87171", "#a855f7", "#38bdf8", "#ec4899", "#3b82f6", "#10b981"]

            num_columns = 2
            for i in range(0, len(all_sensor_cols), num_columns):
                cols = st.columns(num_columns)
                for j in range(num_columns):
                    if i + j < len(all_sensor_cols):
                        col_name = all_sensor_cols[i + j]
                        val = latest_data[col_name]
                        
                        raw_name = str(col_name).upper().replace('_', ' ')
                        if "START" in raw_name and "TIME" in raw_name:
                            display_title = "THE LAST START UP DATE TIME"
                        elif "START" in raw_name:
                            display_title = "THE NUMBER OF STARTS"
                        elif "TRIP" in raw_name:
                            display_title = "THE NUMBER OF TRIPS"
                        elif "ALARM" in raw_name:
                            display_title = "THE NUMBER OF ALARMS"
                        elif "RUNNING" in raw_name or "RUN" in raw_name:
                            display_title = "TURBINE RUNNING TIME"
                        else:
                            display_title = raw_name

                        unit = get_unit(col_name)
                        
                        if pd.isna(val) or val is None or str(val).strip().upper() == 'NULL':
                            display_val = "N/A"
                        elif isinstance(val, pd.Timestamp) or 'time' in col_name.lower() or 'date' in col_name.lower() or 'stamp' in col_name.lower():
                            try:
                                display_val = pd.to_datetime(val).strftime('%Y-%m-%d %H:%M:%S')
                            except:
                                display_val = str(val)
                        elif isinstance(val, (int, float)):
                            if val % 1 != 0:
                                display_val = f"{val:,.2f} {unit}".strip()
                            else:
                                display_val = f"{val:,.0f} {unit}".strip()
                        else:
                            display_val = f"{val} {unit}".strip()
                        
                        bg_color = header_colors[(i + j) % len(header_colors)]
                        
                        card_html = f"""
                        <div style="background-color: #ffffff; border: 1px solid #e0e0e0; border-radius: 12px; box-shadow: 0 4px 6px rgba(0,0,0,0.05); overflow: hidden; margin-bottom: 20px;">
                            <div style="background-color: {bg_color}; color: white; padding: 10px 15px; font-weight: bold; font-size: 1rem; text-align: center; letter-spacing: 0.5px;">
                                {display_title}
                            </div>
                            <div style="padding: 22px; text-align: center; color: #1e293b; font-size: 1.8rem; font-weight: bold;">
                                {display_val}
                            </div>
                        </div>
                        """
                        cols[j].markdown(card_html, unsafe_allow_html=True)
                        
            st.markdown("<br><hr>", unsafe_allow_html=True)
            
            # --- ส่วนแสดงกล่อง Event Summary ด้านล่างสุด ---
            st.subheader("📋 บันทึกเหตุการณ์สำคัญล่าสุด (Event Summary)")
            
            if not df_logs.empty:
                latest_log = df_logs.iloc[0]
                log_time = latest_log.get('created_at', latest_log.get('timestamp', 'N/A'))
                if pd.notna(log_time) and hasattr(log_time, 'strftime'):
                    log_time_str = log_time.strftime('%Y-%m-%d %H:%M:%S')
                else:
                    log_time_str = str(log_time)
                    
                log_msg = latest_log.get('message', latest_log.get('event', 'Turbine event occurred.'))
                log_cause = latest_log.get('cause', latest_log.get('description', ''))
                
                st.markdown(f"""
                <div style="background-color: #ffffff; border: 1px solid #e0e0e0; border-radius: 12px; box-shadow: 0 4px 6px rgba(0,0,0,0.05); overflow: hidden; margin-top: 15px;">
                    <div style="background-color: #06b6d4; color: white; padding: 12px 20px; font-weight: bold; font-size: 1.15rem; text-align: center;">
                        ⚠️ Event Summary
                    </div>
                    <div style="padding: 25px; text-align: center; color: #1e293b;">
                        <div style="font-size: 1.2rem; font-weight: bold; margin-bottom: 10px; color: #334155;">{log_time_str}</div>
                        <div style="font-size: 1.1rem; margin-bottom: 8px; font-weight: 500;">{log_msg}</div>
                        <div style="font-size: 1.05rem; color: #e11d48; font-weight: bold;">{log_cause}</div>
                    </div>
                </div>
                """, unsafe_allow_html=True)
            else:
                st.info("ยังไม่มีบันทึกเหตุการณ์ (Log) ในระบบ")

        # ---------------- หน้าต่างที่ 2: สรุปภาพรวม + ตารางสถิติ ----------------
        with tab2:
            st.subheader(f"📌 สรุปผลการดำเนินงานวันที่ {selected_date}")
            
            col1, col2, col3 = st.columns(3)
            col1.metric("⚡ พลังงานที่ผลิตได้ (MWh)", f"{daily_production:,.3f}")
            col2.metric("💰 รายได้โดยประมาณ (บาท)", f"{daily_revenue:,.2f}")
            col3.metric("⏱️ จำนวนข้อมูล (รายการ)", f"{len(daily_df):,}")
            
            st.markdown("<br>", unsafe_allow_html=True)
            
            st.subheader("📈 แนวโน้มกำลังการผลิต (Generator Output)")
            if 'generator_output' in daily_df.columns:
                chart_data = daily_df.set_index('created_at')['generator_output']
                st.area_chart(chart_data, color="#3b82f6") 
            else:
                st.info("ไม่พบข้อมูล Generator Output สำหรับสร้างกราฟ")

            st.markdown("<br>", unsafe_allow_html=True)
            
            st.subheader("📊 ตารางสรุปค่าสถิติประจำวัน (Daily Statistics)")
            
            # เลือกเฉพาะคอลัมน์ที่เป็นตัวเลขมาคำนวณสถิติ
            numeric_cols = []
            for col in daily_df.select_dtypes(include=['float64', 'int64']).columns:
                if col not in ['id'] and not ('time' in col.lower() or 'date' in col.lower() or 'stamp' in col.lower()):
                    numeric_cols.append(col)
            
            if numeric_cols:
                summary_df = daily_df[numeric_cols].agg(['mean', 'max', 'min']).T
                summary_df.columns = ['ค่าเฉลี่ย (Mean)', 'ค่าสูงสุด (Max)', 'ค่าต่ำสุด (Min)']
                
                summary_df = summary_df.map(lambda x: f"{x:,.2f}" if pd.notna(x) and isinstance(x, (int, float)) else x)
                
                formatted_index = []
                for col in summary_df.index:
                    raw_name = str(col).upper().replace('_', ' ')
                    if "START" in raw_name and "TIME" in raw_name:
                        formatted_index.append("THE LAST START UP DATE TIME")
                    elif "START" in raw_name:
                        formatted_index.append("THE NUMBER OF STARTS")
                    elif "TRIP" in raw_name:
                        formatted_index.append("THE NUMBER OF TRIPS")
                    elif "ALARM" in raw_name:
                        formatted_index.append("THE NUMBER OF ALARMS")
                    elif "RUNNING" in raw_name or "RUN" in raw_name:
                        formatted_index.append("TURBINE RUNNING TIME")
                    else:
                        formatted_index.append(raw_name)
                
                summary_df.index = formatted_index
                
                st.dataframe(summary_df, use_container_width=True)
                
                csv_data = summary_df.to_csv().encode('utf-8-sig')
                
                st.download_button(
                    label="📥 ดาวน์โหลดตารางสรุปผล (Excel/CSV)",
                    data=csv_data,
                    file_name=f"turbine_summary_{selected_date}.csv",
                    mime="text/csv",
                    use_container_width=True
                )
            else:
                st.info("ไม่มีข้อมูลตัวเลขสำหรับสร้างตารางสรุปสถิติ")

    else:
        st.info("ไม่มีข้อมูลสำหรับวันที่เลือก")

# ==========================================
# 5. ระบบ Auto-Refresh (ทุก 60 วินาที)
# ==========================================
if auto_refresh:
    time.sleep(60) 
    st.cache_data.clear() 
    st.rerun()
