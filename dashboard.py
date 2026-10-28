import streamlit as st
import pandas as pd
import time
import io
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
# ⚠️ (ถ้าคีย์เดิมมีปัญหา นำ Supabase Anon Key ล่าสุดมาวางแทนที่ตรงนี้ครับ)
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
    try:
        response = supabase.table("shinko_data").select("*").limit(1000).execute()
        data = response.data if hasattr(response, 'data') else response[1]
        df = pd.DataFrame(data)
        
        if not df.empty:
            if 'created_at' in df.columns:
                df['created_at'] = pd.to_datetime(df['created_at']).dt.tz_convert('Asia/Bangkok')
                df['date_only'] = df['created_at'].dt.date
            
            skip_cols = ['id', 'created_at', 'date_only']
            for col in df.columns:
                if col not in skip_cols and not ('time' in col.lower() or 'date' in col.lower() or 'stamp' in col.lower()):
                    df[col] = pd.to_numeric(df[col].astype(str).str.replace(',', ''), errors='coerce')
            
            if 'created_at' in df.columns:
                df = df.sort_values('created_at')
        return df
    except Exception as e:
        st.error(f"เกิดข้อผิดพลาดในการโหลดข้อมูล shinko_data: {e}")
        return pd.DataFrame()

@st.cache_data(ttl=2) 
def load_logs_data():
    try:
        response = supabase.table("turbine_logs").select("*").limit(100).execute()
        data = response.data if hasattr(response, 'data') else response[1]
        df_logs = pd.DataFrame(data)
        if not df_logs.empty and 'created_at' in df_logs.columns:
            df_logs['created_at'] = pd.to_datetime(df_logs['created_at']).dt.tz_convert('Asia/Bangkok')
            df_logs = df_logs.sort_values('created_at', ascending=False)
        return df_logs
    except:
        return pd.DataFrame()

df = load_data()
df_logs = load_logs_data()

# กำหนดค่าเริ่มต้นให้กับ auto_refresh เพื่อป้องกัน NameError
auto_refresh = False

# ==========================================
# 4. ส่วนแสดงผลหน้า Dashboard
# ==========================================
if df.empty:
    st.warning("⏳ ยังไม่มีข้อมูลในระบบ หรือกำลังเชื่อมต่อฐานข้อมูล... (โปรดตรวจสอบ API Key ของ Supabase อีกครั้ง)")
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
        
        available_dates = df['date_only'].unique() if 'date_only' in df.columns else []
        selected_date = st.selectbox("📅 เลือกวันที่ต้องการดูข้อมูล", available_dates, index=len(available_dates)-1) if len(available_dates) > 0 else None
        st.caption("Developed for Senior Project")

    if selected_date is not None and not df.empty:
        daily_df = df[df['date_only'] == selected_date].copy()
    else:
        daily_df = pd.DataFrame()
    
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
                    if 'running' in name or 'run' in name:
                        return "min"
                    return ""
                elif 'temp' in name:
                    return "°C"
                elif 'press' in name or 'pressure' in name:
                    return "barG"
                elif 'speed' in name or 'rpm' in name:
                    return "RPM"
                elif 'watt' in name or 'power' in name or 'generator' in name:
                    return "kW"
                elif 'rate' in name:
                    return "%"
                elif 'flow' in name:
                    return "m³/h"
                elif 'running' in name or 'run' in name:
                    return "min"
                else:
                    return ""
            
            def get_threshold_tags(title):
                t = title.upper()
                left_html, right_html = "", ""
                
                def tag_l(label, val):
                    return f'<div style="display: flex; align-items: center; gap: 8px; margin-bottom: 4px;"><span style="background-color: #38bdf8; color: white; padding: 4px 8px; border-radius: 4px; font-size: 0.8rem; font-weight: bold;">{label}</span><span style="color: #334155; font-size: 0.95rem; font-weight: bold;">{val}</span></div>'
                
                def tag_r(label, val, bg_color):
                    return f'<div style="display: flex; align-items: center; justify-content: flex-end; gap: 6px; margin-bottom: 4px;"><span style="background-color: {bg_color}; color: white; padding: 2px 6px; border-radius: 4px; font-size: 0.75rem; font-weight: bold;">{label}</span><span style="color: #334155; font-size: 0.85rem; font-weight: bold;">{val}</span></div>'

                c_alarm = "#f59e0b" 
                c_trip = "#ef4444"  

                if "GENERATOR" in t and "OUTPUT" in t:
                    left_html = tag_l("RATED", "18,000 kW")
                elif "SPEED" in t:
                    left_html = tag_l("RATED", "1,500 RPM")
                    right_html = tag_r("TRIP(H)", "1,635 RPM", c_trip)
                elif "INLET" in t and "PRESS" in t:
                    left_html = tag_l("RATED", "40 barG")
                    right_html = tag_r("ALARM(L)", "34 barG", c_alarm) + tag_r("TRIP(L)", "30 barG", c_trip)
                elif "EXH" in t and "PRESS" in t:
                    left_html = tag_l("RATED", "1.5 barG")
                    right_html = tag_r("TRIP(H)", "3 barG", c_trip) + tag_r("ALARM(H)", "2.5 barG", c_alarm)
                elif "LUB" in t and "PRESS" in t:
                    right_html = tag_r("ALARM(L)", "0.7 barG", c_alarm) + tag_r("TRIP(L)", "0.5 barG", c_trip)
                elif "CONT" in t and "PRESS" in t:
                    right_html = tag_r("ALARM(L)", "7 barG", c_alarm)
                elif "INLET" in t and "TEMP" in t:
                    left_html = tag_l("RATED", "440 °C")
                elif "LUB" in t and "OUTLET" in t and "TEMP" in t:
                    right_html = tag_r("ALARM(H)", "50 °C", c_alarm)
                elif "BEARING" in t and "TEMP" in t:
                    right_html = tag_r("ALARM(H)", "75 °C", c_alarm)
                
                return left_html, right_html

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
                            if 'running' in col_name.lower() or 'run' in col_name.lower():
                                display_val = f"{val} {unit}".strip()
                            else:
                                try:
                                    display_val = pd.to_datetime(val).strftime('%Y-%m-%d %H:%M:%S')
                                except:
                                    display_val = str(val)
                        else:
                            display_val = f"{val} {unit}".strip()
                        
                        bg_color = header_colors[(i + j) % len(header_colors)]
                        left_tags, right_tags = get_threshold_tags(display_title)
                        
                        card_html = f'<div style="background-color: #ffffff; border: 1px solid #e0e0e0; border-radius: 12px; box-shadow: 0 4px 6px rgba(0,0,0,0.05); overflow: hidden; margin-bottom: 20px;"><div style="background-color: {bg_color}; color: white; padding: 10px 15px; font-weight: bold; font-size: 1rem; text-align: center; letter-spacing: 0.5px;">{display_title}</div><div style="padding: 18px 20px; display: flex; align-items: center; justify-content: space-between; min-height: 80px;"><div style="flex: 1; display: flex; flex-direction: column; justify-content: center; align-items: flex-start;">{left_tags}</div><div style="flex: 1.5; text-align: center; color: #1e293b; font-size: 1.8rem; font-weight: bold; white-space: nowrap;">{display_val}</div><div style="flex: 1; display: flex; flex-direction: column; justify-content: center; align-items: flex-end;">{right_tags}</div></div></div>'
                        cols[j].markdown(card_html, unsafe_allow_html=True)
                        
            st.markdown("<br><hr>", unsafe_allow_html=True)
            
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
            
            numeric_cols = []
            for col in daily_df.select_dtypes(include=['float64', 'int64']).columns:
                if col not in ['id'] and not ('time' in col.lower() or 'date' in col.lower() or 'stamp' in col.lower()):
                    numeric_cols.append(col)
                elif 'running' in col.lower() or 'run' in col.lower():
                    numeric_cols.append(col)
            
            if numeric_cols:
                summary_df = daily_df[numeric_cols].agg(['mean', 'max', 'min']).T
                summary_df.columns = ['ค่าเฉลี่ย (Mean)', 'ค่าสูงสุด (Max)', 'ค่าต่ำสุด (Min)']
                
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
                
                # --- สร้างไฟล์ Excel (.xlsx) พร้อมจัดกรอบและปรับความกว้างอัตโนมัติ ---
                export_df = summary_df.reset_index()
                export_df.columns = ['', 'ค่าเฉลี่ย (Mean)', 'ค่าสูงสุด (Max)', 'ค่าต่ำสุด (Min)']
                
                output = io.BytesIO()
                with pd.ExcelWriter(output, engine='openpyxl') as writer:
                    export_df.to_excel(writer, index=False, startrow=0, sheet_name='Summary')
                    
                    workbook = writer.book
                    worksheet = writer.sheets['Summary']
                    
                    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
                    
                    thin_border = Border(
                        left=Side(style='thin', color='CCCCCC'),
                        right=Side(style='thin', color='CCCCCC'),
                        top=Side(style='thin', color='CCCCCC'),
                        bottom=Side(style='thin', color='CCCCCC')
                    )
                    
                    header_fill = PatternFill(start_color='F2F2F2', end_color='F2F2F2', fill_type='solid')
                    header_font = Font(name='Calibri', size=11, bold=True)
                    cell_font = Font(name='Calibri', size=11)
                    
                    for col_num in range(1, len(export_df.columns) + 1):
                        cell = worksheet.cell(row=1, column=col_num)
                        cell.font = header_font
                        cell.fill = header_fill
                        cell.alignment = Alignment(horizontal='center', vertical='center')
                        cell.border = thin_border
                        
                    for row_num in range(2, len(export_df) + 2):
                        for col_num in range(1, len(export_df.columns) + 1):
                            cell = worksheet.cell(row=row_num, column=col_num)
                            cell.font = cell_font
                            cell.border = thin_border
                            if col_num == 1:
                                cell.alignment = Alignment(horizontal='left', vertical='center')
                            else:
                                cell.alignment = Alignment(horizontal='right', vertical='center')
                                
                    for col in worksheet.columns:
                        max_len = max(len(str(cell.value or '')) for cell in col)
                        col_letter = col[0].column_letter
                        worksheet.column_dimensions[col_letter].width = max(max_len + 4, 15)
                        
                excel_data = output.getvalue()
                
                st.download_button(
                    label="📥 ดาวน์โหลดตารางสรุปผลเป็น Excel (.xlsx)",
                    data=excel_data,
                    file_name=f"turbine_summary_{selected_date}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
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
