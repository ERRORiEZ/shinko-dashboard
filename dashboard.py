import streamlit as st
import pandas as pd
import time
import io
import urllib.request
import json

# ==========================================
# 1. ตั้งค่าหน้าเว็บและสไตล์ (CSS - ล็อก Sidebar ให้คาไว้ตลอดถาวร)
# ==========================================
st.set_page_config(
    page_title="Turbine Monitoring System", 
    page_icon="⚙️", 
    layout="wide",
    initial_sidebar_state="expanded"  # บังคับให้เปิด Sidebar ไว้ตั้งแต่เริ่ม
)

st.markdown("""
<style>
    /* นำเข้าฟอนต์ Inter จาก Google Fonts เพื่อความคมชัดและเป็นระเบียบระดับสากล */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

    html, body, [class*="css"], .stMarkdown, p, span, div {
        font-family: 'Inter', 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif !important;
    }
    
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    
    /* ซ่อนปุ่มพับ Sidebar ออกไปเลย เพื่อให้ Sidebar คาไว้ตลอดถาวร */
    [data-testid="collapsedControl"] {
        display: none !important;
    }
    
    h1, h2, h3 { 
        color: #1E3A8A; 
        font-family: 'Inter', 'Segoe UI', sans-serif !important; 
        font-weight: 700;
    }
    
    .latest-time { color: #e11d48; font-weight: bold; font-size: 1.2rem; }
    .status-live { color: #10b981; font-weight: bold; }
</style>
""", unsafe_allow_html=True)

st.title("⚙️ Turbine Monitoring & Revenue Dashboard")
st.markdown("ระบบมอนิเตอร์ประสิทธิภาพและสรุปรายได้กังหันไฟฟ้าแบบเรียลไทม์")
st.markdown("---")

# ==========================================
# 2. ตั้งค่าการเชื่อมต่อ Supabase (Direct REST API)
# ==========================================
SUPABASE_URL = "https://egjpkwgyrhsmajkumnyc.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImVnanBrd2d5cmhzbWFqa3VtbnljIiwicm9sZSI6ImFub24iLCJpYXQiOjE3OTI1MjkzOTYsImV4cCI6MjEwODEwNTM5Nn0.klAeK81K7_ZI_1Z5ow8CeIcJLZ26LxoReJzcf-ETPGo"

@st.cache_data(ttl=2) 
def load_data():
    try:
        url = f"{SUPABASE_URL}/rest/v1/shinko_data?select=*"
        req = urllib.request.Request(url, headers={
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}"
        })
        with urllib.request.urlopen(req) as response:
            data = json.loads(response.read().decode())
        
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
        return pd.DataFrame()

@st.cache_data(ttl=2) 
def load_logs_data():
    try:
        url = f"{SUPABASE_URL}/rest/v1/turbine_logs?select=*"
        req = urllib.request.Request(url, headers={
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}"
        })
        with urllib.request.urlopen(req) as response:
            data = json.loads(response.read().decode())
        
        df_logs = pd.DataFrame(data)
        if not df_logs.empty and 'created_at' in df_logs.columns:
            df_logs['created_at'] = pd.to_datetime(df_logs['created_at']).dt.tz_convert('Asia/Bangkok')
            df_logs = df_logs.sort_values('created_at', ascending=False)
        return df_logs
    except:
        return pd.DataFrame()

df = load_data()
df_logs = load_logs_data()
auto_refresh = False

# ==========================================
# 3. ส่วน Sidebar (คาไว้ตลอดถาวร)
# ==========================================
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
    
    available_dates = df['date_only'].unique() if not df.empty and 'date_only' in df.columns else []
    selected_date = st.selectbox("📅 เลือกวันที่ต้องการดูข้อมูล", available_dates, index=len(available_dates)-1) if len(available_dates) > 0 else None
    st.caption("Developed for Senior Project")

# ==========================================
# 4. สร้าง 3 แท็บหลัก
# ==========================================
tab1, tab2, tab3 = st.tabs(["🔴 สถานะเครื่องจักร (Live Status)", "📊 สรุปภาพรวม (Summary)", "📂 อัปโหลดไฟล์ Excel (Custom Upload)"])

# ---------------- แท็บที่ 1: สถานะเครื่องจักร ----------------
with tab1:
    if df.empty:
        st.warning("⏳ ยังไม่มีข้อมูลในระบบ หรือกำลังเชื่อมต่อฐานข้อมูล...")
    else:
        daily_df = df[df['date_only'] == selected_date].copy() if selected_date is not None else pd.DataFrame()
        if not daily_df.empty:
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
                    return "min" if 'running' in name else ""
                elif 'temp' in name: return "°C"
                elif 'press' in name or 'pressure' in name: return "barG"
                elif 'speed' in name or 'rpm' in name: return "RPM"
                elif 'watt' in name or 'power' in name or 'generator' in name: return "kW"
                elif 'rate' in name: return "%"
                elif 'flow' in name: return "m³/h"
                else: return ""
            
            def get_threshold_tags(title):
                t = title.upper()
                left_html, right_html = "", ""
                def tag_l(label, val):
                    return f'<div style="display: flex; align-items: center; gap: 8px; margin-bottom: 4px;"><span style="background-color: #38bdf8; color: white; padding: 4px 8px; border-radius: 4px; font-size: 0.8rem; font-weight: 600;">{label}</span><span style="color: #334155; font-size: 0.95rem; font-weight: 600;">{val}</span></div>'
                def tag_r(label, val, bg_color):
                    return f'<div style="display: flex; align-items: center; justify-content: flex-end; gap: 6px; margin-bottom: 4px;"><span style="background-color: {bg_color}; color: white; padding: 2px 6px; border-radius: 4px; font-size: 0.75rem; font-weight: 600;">{label}</span><span style="color: #334155; font-size: 0.85rem; font-weight: 600;">{val}</span></div>'

                c_alarm, c_trip = "#f59e0b", "#ef4444"
                if "GENERATOR" in t and "OUTPUT" in t: left_html = tag_l("RATED", "18,000 kW")
                elif "SPEED" in t: left_html = tag_l("RATED", "1,500 RPM"); right_html = tag_r("TRIP(H)", "1,635 RPM", c_trip)
                elif "INLET" in t and "PRESS" in t: left_html = tag_l("RATED", "40 barG"); right_html = tag_r("ALARM(L)", "34 barG", c_alarm) + tag_r("TRIP(L)", "30 barG", c_trip)
                elif "EXH" in t and "PRESS" in t: left_html = tag_l("RATED", "1.5 barG"); right_html = tag_r("TRIP(H)", "3 barG", c_trip) + tag_r("ALARM(H)", "2.5 barG", c_alarm)
                elif "LUB" in t and "PRESS" in t: right_html = tag_r("ALARM(L)", "0.7 barG", c_alarm) + tag_r("TRIP(L)", "0.5 barG", c_trip)
                elif "CONT" in t and "PRESS" in t: right_html = tag_r("ALARM(L)", "7 barG", c_alarm)
                elif "INLET" in t and "TEMP" in t: left_html = tag_l("RATED", "440 °C")
                elif "LUB" in t and "OUTLET" in t and "TEMP" in t: right_html = tag_r("ALARM(H)", "50 °C", c_alarm)
                elif "BEARING" in t and "TEMP" in t: right_html = tag_r("ALARM(H)", "75 °C", c_alarm)
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
                        if "START" in raw_name and "TIME" in raw_name: display_title = "THE LAST START UP DATE TIME"
                        elif "START" in raw_name: display_title = "THE NUMBER OF STARTS"
                        elif "TRIP" in raw_name: display_title = "THE NUMBER OF TRIPS"
                        elif "ALARM" in raw_name: display_title = "THE NUMBER OF ALARMS"
                        elif "RUNNING" in raw_name or "RUN" in raw_name: display_title = "TURBINE RUNNING TIME"
                        else: display_title = raw_name

                        unit = get_unit(col_name)
                        if pd.isna(val) or val is None: display_val = "N/A"
                        elif isinstance(val, (int, float)):
                            display_val = f"{val:,.2f} {unit}".strip() if val % 1 != 0 else f"{val:,.0f} {unit}".strip()
                        else: display_val = f"{val} {unit}".strip()
                        
                        bg_color = header_colors[(i + j) % len(header_colors)]
                        left_tags, right_tags = get_threshold_tags(display_title)
                        
                        card_html = f'<div style="background-color: #ffffff; border: 1px solid #e2e8f0; border-radius: 12px; box-shadow: 0 4px 6px rgba(0,0,0,0.03); overflow: hidden; margin-bottom: 20px;"><div style="background-color: {bg_color}; color: white; padding: 10px 15px; font-weight: 600; font-size: 0.95rem; text-align: center; letter-spacing: 0.5px;">{display_title}</div><div style="padding: 18px 20px; display: flex; align-items: center; justify-content: space-between; min-height: 80px;"><div style="flex: 1;">{left_tags}</div><div style="flex: 1.5; text-align: center; color: #0f172a; font-size: 1.8rem; font-weight: 700;">{display_val}</div><div style="flex: 1;">{right_tags}</div></div></div>'
                        cols[j].markdown(card_html, unsafe_allow_html=True)
                        
            st.markdown("<br><hr>", unsafe_allow_html=True)
            st.subheader("📋 บันทึกเหตุการณ์สำคัญล่าสุด (Event Summary)")
            if not df_logs.empty:
                latest_log = df_logs.iloc[0]
                log_time = latest_log.get('created_at', latest_log.get('timestamp', 'N/A'))
                log_time_str = log_time.strftime('%Y-%m-%d %H:%M:%S') if pd.notna(log_time) and hasattr(log_time, 'strftime') else str(log_time)
                log_msg = latest_log.get('message', latest_log.get('event', 'Turbine event occurred.'))
                log_cause = latest_log.get('cause', latest_log.get('description', ''))
                
                st.markdown(f"""
                <div style="background-color: #ffffff; border: 1px solid #e2e8f0; border-radius: 12px; box-shadow: 0 4px 6px rgba(0,0,0,0.03); overflow: hidden; margin-top: 15px;">
                    <div style="background-color: #06b6d4; color: white; padding: 12px 20px; font-weight: 600; font-size: 1.1rem; text-align: center;">⚠️ Event Summary</div>
                    <div style="padding: 25px; text-align: center; color: #1e293b;">
                        <div style="font-size: 1.15rem; font-weight: 600; margin-bottom: 10px; color: #334155;">{log_time_str}</div>
                        <div style="font-size: 1.05rem; margin-bottom: 8px; font-weight: 500;">{log_msg}</div>
                        <div style="font-size: 1.05rem; color: #e11d48; font-weight: 700;">{log_cause}</div>
                    </div>
                </div>
                """, unsafe_allow_html=True)
            else:
                st.info("ยังไม่มีบันทึกเหตุการณ์ (Log) ในระบบ")

# ---------------- แท็บที่ 2: สรุปภาพรวม ----------------
with tab2:
    if df.empty:
        st.warning("⏳ ยังไม่มีข้อมูลในระบบ...")
    else:
        daily_df = df[df['date_only'] == selected_date].copy() if selected_date is not None else pd.DataFrame()
        if not daily_df.empty:
            watt_max = daily_df['watt_hour'].max() if 'watt_hour' in daily_df.columns else 0
            watt_min = daily_df['watt_hour'].min() if 'watt_hour' in daily_df.columns else 0
            daily_production = watt_max - watt_min
            daily_revenue = daily_production * 1000 * electric_rate
            
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
            
            numeric_cols = [col for col in daily_df.select_dtypes(include=['float64', 'int64']).columns if col not in ['id'] and not ('time' in col.lower() or 'date' in col.lower() or 'stamp' in col.lower())]
            if numeric_cols:
                summary_df = daily_df[numeric_cols].agg(['mean', 'max', 'min']).T
                summary_df.columns = ['ค่าเฉลี่ย (Mean)', 'ค่าสูงสุด (Max)', 'ค่าต่ำสุด (Min)']
                summary_df.index = [str(col).upper().replace('_', ' ') for col in summary_df.index]
                
                display_summary_df = summary_df.map(lambda x: f"{x:,.2f}" if pd.notna(x) and isinstance(x, (int, float)) else x)
                st.dataframe(display_summary_df, use_container_width=True)
                
                # --- สร้างไฟล์ Excel (.xlsx) พร้อมดาวน์โหลด ---
                export_df = summary_df.reset_index()
                export_df.columns = ['', 'ค่าเฉลี่ย (Mean)', 'ค่าสูงสุด (Max)', 'ค่าต่ำสุด (Min)']
                
                output = io.BytesIO()
                with pd.ExcelWriter(output, engine='openpyxl') as writer:
                    export_df.to_excel(writer, index=False, startrow=0, sheet_name='Summary')
                    workbook = writer.book
                    worksheet = writer.sheets['Summary']
                    
                    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
                    thin_border = Border(left=Side(style='thin', color='E2E8F0'), right=Side(style='thin', color='E2E8F0'), top=Side(style='thin', color='E2E8F0'), bottom=Side(style='thin', color='E2E8F0'))
                    header_fill = PatternFill(start_color='F8FAFC', end_color='F8FAFC', fill_type='solid')
                    header_font = Font(name='Inter', size=11, bold=True, color='334155')
                    cell_font = Font(name='Inter', size=11, color='1E293B')
                    
                    for col_num in range(1, len(export_df.columns) + 1):
                        cell = worksheet.cell(row=1, column=col_num)
                        cell.font = header_font
                        cell.fill = header_fill
                        cell.alignment = Alignment(horizontal='left' if col_num == 1 else 'right', vertical='center')
                        cell.border = thin_border
                        
                    for row_num in range(2, len(export_df) + 2):
                        for col_num in range(1, len(export_df.columns) + 1):
                            cell = worksheet.cell(row=row_num, column=col_num)
                            cell.font = cell_font
                            cell.border = thin_border
                            cell.alignment = Alignment(horizontal='left', vertical='center') if col_num == 1 else Alignment(horizontal='right', vertical='center')
                            if col_num > 1 and isinstance(cell.value, (int, float)):
                                cell.number_format = '#,##0' if str(cell.value).endswith('.0') or isinstance(cell.value, int) else '#,##0.00'
                                
                    for column in worksheet.columns:
                        max_len_col = max(len(str(cell.value or '')) for cell in column)
                        worksheet.column_dimensions[column[0].column_letter].width = max(max_len_col + 6, 20)
                        
                excel_data = output.getvalue()
                st.download_button(
                    label="📥 ดาวน์โหลดตารางสรุปผลเป็น Excel (.xlsx)",
                    data=excel_data,
                    file_name=f"turbine_summary_{selected_date}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True
                )

# ---------------- แท็บที่ 3: อัปโหลดไฟล์ Excel ----------------
with tab3:
    st.subheader("📂 อัปโหลดไฟล์ Excel ของคุณเพื่อแสดงผลข้อมูลทันที")
    st.markdown("คุณสามารถลากไฟล์ Excel (`.xlsx` หรือ `.csv`) ที่กรอกข้อมูลเสร็จแล้วมาวางด้านล่างนี้ได้เลย ระบบจะแสดงผลออกมาเป็นหน้าแดชบอร์ดและการ์ดมอนิเตอร์ทันทีครับ")
    
    uploaded_file = st.file_uploader("ลากไฟล์มาวางที่นี่ หรือคลิกเพื่อเลือกไฟล์", type=["xlsx", "csv"], key="custom_excel_uploader")
    
    if uploaded_file is not None:
        try:
            up_df = pd.read_csv(uploaded_file) if uploaded_file.name.endswith('.csv') else pd.read_excel(uploaded_file)
                
            if 'created_at' not in up_df.columns and 'timestamp' in up_df.columns:
                up_df['created_at'] = pd.to_datetime(up_df['timestamp'])
            elif 'created_at' in up_df.columns:
                up_df['created_at'] = pd.to_datetime(up_df['created_at'])
            else:
                up_df['created_at'] = pd.date_range(start='2026-01-01 00:00:00', periods=len(up_df), freq='H')

            skip_cols = ['id', 'created_at']
            for col in up_df.columns:
                if col not in skip_cols and not ('time' in col.lower() or 'date' in col.lower() or 'stamp' in col.lower()):
                    up_df[col] = pd.to_numeric(up_df[col].astype(str).str.replace(',', ''), errors='coerce')
                    
            up_df = up_df.sort_values('created_at', ascending=False)
            latest_up = up_df.iloc[0]
            
            st.success("🎉 อัปโหลดและประมวลผลไฟล์สำเร็จ! ข้อมูลถูกแสดงผลด้านล่างนี้ครับ")
            st.markdown("---")
            
            up_sensor_cols = [c for c in latest_up.index if c not in skip_cols]
            cols = st.columns(2)
            for idx, c_name in enumerate(up_sensor_cols):
                val = latest_up[c_name]
                c_title = str(c_name).upper().replace('_', ' ')
                val_str = f"{val:,.2f}" if isinstance(val, (int, float)) and val % 1 != 0 else (f"{val:,.0f}" if isinstance(val, (int, float)) else str(val))
                
                header_colors = ["#f87171", "#a855f7", "#38bdf8", "#ec4899", "#3b82f6", "#10b981"]
                bg_color = header_colors[idx % len(header_colors)]
                
                card_box = f'<div style="background-color: #ffffff; border: 1px solid #e2e8f0; border-radius: 12px; padding: 0px; margin-bottom: 20px; box-shadow: 0 4px 6px rgba(0,0,0,0.03); overflow: hidden;"><div style="background-color: {bg_color}; color: white; padding: 10px 15px; font-weight: 600; font-size: 0.95rem; text-align: center; letter-spacing: 0.5px;">{c_title}</div><div style="padding: 20px; text-align: center; color: #0f172a; font-size: 1.8rem; font-weight: 700;">{val_str}</div></div>'
                cols[idx % 2].markdown(card_box, unsafe_allow_html=True)
                
            st.markdown("### 📋 ตารางข้อมูลดิบจากไฟล์ที่คุณอัปโหลด")
            
            display_up_df = up_df.copy()
            for col in display_up_df.select_dtypes(include=['float64', 'int64']).columns:
                display_up_df[col] = display_up_df[col].apply(lambda x: f"{x:,.2f}" if pd.notna(x) and x % 1 != 0 else (f"{x:,.0f}" if pd.notna(x) else x))
            
            st.dataframe(display_up_df, use_container_width=True)
            
        except Exception as e:
            st.error(f"เกิดข้อผิดพลาดในการอ่านไฟล์: {e}")
    else:
        st.info("💡 ยังไม่ได้อัปโหลดไฟล์ กรุณาเลือกไฟล์ Excel ในช่องด้านบนเพื่อดูผลลัพธ์")

# ==========================================
# 5. ระบบ Auto-Refresh (ทุก 60 วินาที)
# ==========================================
if auto_refresh:
    time.sleep(60) 
    st.cache_data.clear() 
    st.rerun()
