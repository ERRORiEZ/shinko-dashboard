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
# 2. ฟังก์ชันดึงข้อมูล
# ==========================================
@st.cache_data(ttl=60)  # ดึงข้อมูลใหม่ทุก 1 นาที
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
# 3. ส่วนแสดงผลหน้า Dashboard
# ==========================================
if df.empty:
    st.warning("⚠️ ยังไม่มีข้อมูลในระบบ หรือกำลังเชื่อมต่อฐานข้อมูล")
else:
    # ---------------- Sidebar ----------------
    st.sidebar.header("⚙️ ตั้งค่าการคำนวณ")
    electric_rate = st.sidebar.number_input("อัตราค่าไฟ (บาท/หน่วย)", value=4.0, step=0.1)
    
    available_dates = df['date_only'].unique()
    selected_date = st.sidebar.selectbox("🗓️ เลือกวันที่ต้องการดูข้อมูล", available_dates, index=len(available_dates)-1)
    
    daily_df = df[df['date_only'] == selected_date].copy()
    
    if not daily_df.empty:
        # คำนวณพลังงานและรายได้
        watt_max = daily_df['watt_hour'].max()
        watt_min = daily_df['watt_hour'].min()
        daily_production = watt_max - watt_min
        daily_revenue = daily_production * 1000 * electric_rate
        
        # ==========================================
        # สร้างส่วนหน้าต่างแบ่งเป็น 2 แท็บ
        # ==========================================
        tab1, tab2 = st.tabs(["📋 ข้อมูลเรียลไทม์ (Real-time Logs)", "🎯 สรุปภาพรวม (Summary)"])
        
        # ---------------- หน้าต่างที่ 1: ข้อมูลเรียลไทม์ ----------------
        with tab1:
            st.header("📋 ข้อมูลการทำงานแบบละเอียด")
            st.markdown("แสดงค่าเซ็นเซอร์ทุกรายการที่ถูกส่งเข้ามา **เรียงจากเวลาล่าสุดอยู่ด้านบนสุด**")
            
            # เรียงข้อมูลจากใหม่ไปเก่า และซ่อนคอลัมน์ date_only
            display_df = daily_df.drop(columns=['date_only'], errors='ignore').sort_values('created_at', ascending=False)
            st.dataframe(display_df, use_container_width=True, height=600)
            
        # ---------------- หน้าต่างที่ 2: สรุปภาพรวม ----------------
        with tab2:
            st.header("🎯 สร
