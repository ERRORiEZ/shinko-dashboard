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
        
        cols_to_numeric = ['watt_hour', 'generator_output', 'operating_rate', 'turbine_speed']
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
        
        # สวิตช์ออโต้ 60 วินาที
        auto_refresh = st.toggle("เปิดโหมด Auto-Refresh (ทุก 60 วิ)", value=False)
        
        if auto_refresh:
            st.success("🟢 ระบบกำลังดึงข้อมูลอัตโนมัติ")
        else:
            st.info("⚪ ระบบหยุดดึงข้อมูลอัตโนมัติ")
            
        # ปุ่มกดดึงข้อมูลแบบ Manual
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
        
        # ---------------- หน้าต่างที่ 1: ข้อมูลเรียลไทม์ ----------------
        with tab1:
            display_df = daily_df.sort_values('created_at', ascending=False)
            latest_data = display_df.iloc[0] 
            latest_time = latest_data['created_at'].strftime('%H:%M:%S')
            
            st.subheader("🔴 มอนิเตอร์ค่าเซ็นเซอร์แบบเรียลไทม์")
            if auto_refresh:
                st.markdown(f"สถานะ: <span class='status-live'>Live 🟢</span> | อัปเดตข้อมูลล่าสุดเมื่อเวลา: <span class='latest-time'>{latest_time}</span>", unsafe_allow_html=True)
            else:
                st.markdown(f"สถานะ: ออฟไลน์ ⚪ | อัปเดตข้อมูลล่าสุดเมื่อเวลา: <span class='latest-time'>{latest_time}</span>", unsafe_allow_html=True)
            st.markdown("<br>", unsafe_allow_html=True)
            
            r1c1, r1c2, r1c3, r1c4 = st.columns(4)
            r1c1.metric("กำลังการผลิต (kW)", f"{latest_data.get('generator_output', 0):,.2f}")
            r1c2.metric("ความเร็วกังหัน (RPM)", f"{latest_data.get('turbine_speed', 0):,.2f}")
            r1c3.metric("อัตราการเดินเครื่อง (%)", f"{latest_data.get('operating_rate', 0):,.2f}")
            r1c4.metric("พลังงานสะสม (Watt-hour)", f"{latest_data.get('watt_hour', 0):,.0f}")
            
            st.markdown("<br><hr>", unsafe_allow_html=True)
            
            with st.expander("🔍 ดูตารางข้อมูลดิบทั้งหมด (Raw Data)"):
                st.dataframe(display_df.drop(columns=['date_only'], errors='ignore'), use_container_width=True, height=300)

        # ---------------- หน้าต่างที่ 2: สรุปภาพรวม ----------------
        with tab2:
            st.subheader(f"📌 สรุปผลการดำเนินงานวันที่ {selected_date}")
            
            col1, col2, col3 = st.columns(3)
            col1.metric("⚡ พลังงานที่ผลิตได้ (MWh)", f"{daily_production:,.3f}")
            col2.metric("💰 รายได้โดยประมาณ (บาท)", f"{daily_revenue:,.2f}")
            col3.metric("⏱️ จำนวนข้อมูล (รายการ)", f"{len(daily_df)}")
            
            st.markdown("<br>", unsafe_allow_html=True)
            st.subheader("📈 แนวโน้มกำลังการผลิต (Generator Output)")
            chart_data = daily_df.set_index('created_at')['generator_output']
            st.area_chart(chart_data, color="#3b82f6") 
            
            with st.expander("📌 ดูตารางสรุปสถิติเชิงลึก", expanded=False):
                summary_cols = ['generator_output', 'operating_rate', 'turbine_speed']
                existing_cols = [col for col in summary_cols if col in daily_df.columns]
                
                if existing_cols:
                    summary_df = daily_df[existing_cols].agg(['mean', 'max', 'min']).T
                    summary_df.columns = ['ค่าเฉลี่ย', 'ค่าสูงสุด', 'ค่าต่ำสุด']
                    name_mapping = {
                        'generator_output': 'กำลังการผลิต (kW)',
                        'operating_rate': 'อัตราการเดินเครื่อง (%)',
                        'turbine_speed': 'ความเร็วกังหัน (RPM)'
                    }
                    summary_df.index = [name_mapping[col] for col in existing_cols]
                    st.dataframe(summary_df.style.format("{:.2f}").background_gradient(cmap='Blues'), use_container_width=True)

    else:
        st.info("ไม่มีข้อมูลสำหรับวันที่เลือก")

# ==========================================
# 5. ระบบ Auto-Refresh (ทุก 60 วินาที)
# ==========================================
if auto_refresh:
    time.sleep(60) 
    st.cache_data.clear() 
    st.rerun()
