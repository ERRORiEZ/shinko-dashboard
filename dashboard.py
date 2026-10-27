import streamlit as st
import pandas as pd
from supabase import create_client, Client

# ==========================================
# 1. ตั้งค่าการเชื่อมต่อ Supabase
# ==========================================
SUPABASE_URL = "https://egjpkwgyrhsmajkumnyc.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImVnanBrd2d5cmhzbWFqa3VtbnljIiwicm9sZSI6ImFub24iLCJpYXQiOjE3OTI1MjkzOTYsImV4cCI6MjEwODEwNTM5Nn0.klAeK81K7_ZI_1Z5ow8CeIcJLZ26LxoReJzcf-ETPGo"
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# ตั้งค่าหน้าเว็บ
st.set_page_config(page_title="Turbine Dashboard", layout="wide")
st.title("⚡ Dashboard สรุปประสิทธิภาพและรายได้กังหันไฟฟ้า")

# ==========================================
# 2. ฟังก์ชันดึงข้อมูลและทำความสะอาดตัวเลข
# ==========================================
@st.cache_data(ttl=60)  # ดึงข้อมูลใหม่ทุก 1 นาที
def load_data():
    # ดึงข้อมูลจากตาราง shinko_data
    response = supabase.table("shinko_data").select("*").execute()
    df = pd.DataFrame(response.data)
    
    if not df.empty:
        # แปลงเวลาเป็น Datetime ของไทย
        df['created_at'] = pd.to_datetime(df['created_at']).dt.tz_convert('Asia/Bangkok')
        df['date_only'] = df['created_at'].dt.date
        
        # รายชื่อคอลัมน์ที่ต้องใช้คำนวณ (แปลงเป็นตัวเลขและเอาลูกน้ำออก)
        cols_to_numeric = ['watt_hour', 'generator_output', 'operating_rate', 'turbine_speed']
        for col in cols_to_numeric:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col].astype(str).str.replace(',', ''), errors='coerce')
        
        # เรียงข้อมูลตามเวลา
        df = df.sort_values('created_at')
        
    return df

# โหลดข้อมูลเข้าตัวแปร
df = load_data()

# ==========================================
# 3. ส่วนแสดงผลหน้า Dashboard
# ==========================================
if df.empty:
    st.warning("⚠️ ยังไม่มีข้อมูลในระบบ หรือกำลังเชื่อมต่อฐานข้อมูล")
else:
    # ---------------- Sidebar ----------------
    st.sidebar.header("⚙️ ตั้งค่าการคำนวณ")
    electric_rate = st.sidebar.number_input("อัตราค่าไฟ (บาท/หน่วย)", value=4.0, step=0.1)
    
    # ดึงรายชื่อวันที่ทั้งหมดที่มีในระบบมาสร้างตัวเลือก
    available_dates = df['date_only'].unique()
    selected_date = st.sidebar.selectbox("🗓️ เลือกวันที่ต้องการดูข้อมูล", available_dates, index=len(available_dates)-1)
    
    # ---------------- ฟิลเตอร์ข้อมูล ----------------
    daily_df = df[df['date_only'] == selected_date].copy()
    
    if not daily_df.empty:
        # คำนวณพลังงานและรายได้
        watt_max = daily_df['watt_hour'].max()
        watt_min = daily_df['watt_hour'].min()
        daily_production = watt_max - watt_min
        daily_revenue = daily_production * 1000 * electric_rate
        
        # ---------------- การ์ดสรุปยอด ----------------
        st.subheader(f"📊 สรุปยอดประจำวันที่ {selected_date}")
        col1, col2, col3 = st.columns(3)
        col1.metric("⚡ พลังงานที่ผลิตได้", f"{daily_production:,.3f} MWh")
        col2.metric("💰 รายได้โดยประมาณ", f"{daily_revenue:,.2f} บาท")
        col3.metric("⏱️ ข้อมูลที่บันทึกได้วันนี้", f"{len(daily_df)} รายการ")
        
        st.markdown("---")
        
        # ---------------- กราฟเส้น ----------------
        st.subheader("📈 กราฟแสดงกำลังการผลิต (Generator Output) ตลอดวัน")
        chart_data = daily_df.set_index('created_at')['generator_output']
        st.line_chart(chart_data)
        
        # ---------------- ตารางสรุปสถิติ ----------------
        # เปิดตารางโชว์อัตโนมัติด้วย expanded=True
        with st.expander("📊 ดูตารางสรุปสถิติประจำวัน (Daily Summary)", expanded=True):
            summary_cols = ['generator_output', 'operating_rate', 'turbine_speed']
            
            # เช็คว่ามีคอลัมน์ครบไหมแล้วนำมาหา ค่าเฉลี่ย, สูงสุด, ต่ำสุด
            existing_cols = [col for col in summary_cols if col in daily_df.columns]
            
            if existing_cols:
                summary_df = daily_df[existing_cols].agg(['mean', 'max', 'min']).T
                summary_df.columns = ['ค่าเฉลี่ย (Average)', 'ค่าสูงสุด (Max)', 'ค่าต่ำสุด (Min)']
                
                # แมปปิ้งชื่อภาษาไทยให้ตารางอ่านง่ายขึ้น
                name_mapping = {
                    'generator_output': 'กำลังการผลิต (kW)',
                    'operating_rate': 'อัตราการเดินเครื่อง (%)',
                    'turbine_speed': 'ความเร็วกังหัน (RPM)'
                }
                summary_df.index = [name_mapping[col] for col in existing_cols]
                
                # แสดงตารางพร้อมจัดฟอร์แมตทศนิยม 2 ตำแหน่ง
                st.dataframe(summary_df.style.format("{:.2f}"), use_container_width=True)
            else:
                st.info("ไม่พบคอลัมน์ที่ต้องการสรุปข้อมูล")
    else:
        st.info("ไม่มีข้อมูลสำหรับวันที่เลือก")