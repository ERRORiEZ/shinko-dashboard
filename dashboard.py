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
    div[data-testid="metric-container"] {
        background-color: #ffffff;
        border: 1px solid #e0e0e0;
        padding: 20px;
        border-radius: 15px;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.05);
        transition: transform 0.2s ease-in-out;
    }
    div[data-testid="metric-container"]:hover {
        transform: translateY(-5px);
        box-shadow: 0 6px 12px rgba(0, 0, 0, 0.1);
    }
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
        
        # แปลงค่าตัวเลขให้เป็น Float เพื่อใช้คำนวณและแสดงผล
        cols_to_numeric = ['watt_hour', 'generator_output', 'operating_rate', 'turbine_speed', 'starts', 'trips', 'alarms']
        for col in cols_to_numeric:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col].astype(str).str.replace(',', ''), errors='coerce')
        
        df = df.sort_values('created_at')
        
    return df

df = load_data()

# ==========================================
# 4. ส่วนแสดงผลหน้า Dashboard
# ==========================================
if df.empty:
    st.warning("⏳ ยังไม่มีข้อมูลในระบบ หรือกำลังเชื่อมต่อฐานข้อมูล...")
else:
    # ---------------- Sidebar ----------------
    with st.sidebar:
        st.image("https://cdn-icons-png.flaticon.com/512/2157/2157014.png", width=120) 
        
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
        watt_max = daily_df['watt_hour'].max()
        watt_min = daily_df['watt_hour'].min()
        daily_production = watt_max - watt_min
        daily_revenue = daily_production * 1000 * electric_rate
        
        tab1, tab2 = st.tabs(["🔴 สถานะเครื่องจักร (Live Status)", "📊 สรุปภาพรวม (Summary)"])
        
        # ---------------- หน้าต่างที่ 1: ข้อมูลเรียลไทม์ดึงทุกค่าอัตโนมัติ ----------------
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
            
            # ดึงชื่อคอลัมน์ทั้งหมด ยกเว้นคอลัมน์ระบบที่ไม่ต้องการแสดง
            exclude_cols = ['id', 'created_at', 'date_only']
            all_sensor_cols = [col for col in latest_data.index if col not in exclude_cols]
            
            # ลูปสร้างกล่อง Metrics แถวละ 4 กล่องอัตโนมัติ
            num_columns = 4
            for i in range(0, len(all_sensor_cols), num_columns):
                cols = st.columns(num_columns)
                for j in range(num_columns):
                    if i + j < len(all_sensor_cols):
                        col_name = all_sensor_cols[i + j]
                        val = latest_data[col_name]
                        
                        # ทำชื่อคอลัมน์ให้ดูสวยงาม
                        display_title = str(col_name).replace('_', ' ').title()
                        
                        # จัดฟอร์แมตค่าตัวเลข
                        if pd.isna(val) or val is None or str(val).strip().upper() == 'NULL':
                            display_val = "N/A"
                        elif isinstance(val, (int, float)):
                            if val % 1 != 0:
                                display_val = f"{val:,.2f}"
                            else:
                                display_val = f"{val:,.0f}"
                        else:
                            display_val = str(val)
                            
                        cols[j].metric(display_title, display_val)
                        
            st.markdown("<br><hr>", unsafe_allow_html=True)

        # ---------------- หน้าต่างที่ 2: สรุปภาพรวม (เพิ่มตารางสถิติกลับมา) ----------------
        with tab2:
            st.subheader(f"📌 สรุปผลการดำเนินงานวันที่ {selected_date}")
            
            col1, col2, col3 = st.columns(3)
            col1.metric("⚡ พลังงานที่ผลิตได้ (MWh)", f"{daily_production:,.3f}")
            col2.metric("💰 รายได้โดยประมาณ (บาท)", f"{daily_revenue:,.2f}")
            col3.metric("⏱️ จำนวนข้อมูล (รายการ)", f"{len(daily_df)}")
            
            st.markdown("<br>", unsafe_allow_html=True)
            
            # กราฟแสดงแนวโน้ม
            st.subheader("📈 แนวโน้มกำลังการผลิต (Generator Output)")
            if 'generator_output' in daily_df.columns:
                chart_data = daily_df.set_index('created_at')['generator_output']
                st.area_chart(chart_data, color="#3b82f6") 
            else:
                st.info("ไม่พบข้อมูล Generator Output สำหรับสร้างกราฟ")

            st.markdown("<br>", unsafe_allow_html=True)
            
            # ตารางสรุปสถิติประจำวัน (ดึงเฉพาะคอลัมน์ตัวเลขมาทำสถิติอัตโนมัติ)
            st.subheader("📊 ตารางสรุปค่าสถิติประจำวัน (Daily Statistics)")
            numeric_cols = daily_df.select_dtypes(include=['float64', 'int64']).columns
            exclude_stat_cols = ['id']
            stat_cols = [col for col in numeric_cols if col not in exclude_stat_cols]
            
            if stat_cols:
                summary_df = daily_df[stat_cols].agg(['mean', 'max', 'min']).T
                summary_df.columns = ['ค่าเฉลี่ย (Mean)', 'ค่าสูงสุด (Max)', 'ค่าต่ำสุด (Min)']
                summary_df.index = [str(col).replace('_', ' ').title() for col in summary_df.index]
                
                # แสดงผลตารางแบบไม่มีสีไล่เฉด ป้องกัน Error Jinja2
                st.dataframe(summary_df.round(2), use_container_width=True)
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
