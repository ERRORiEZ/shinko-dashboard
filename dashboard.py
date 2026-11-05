import streamlit as st
import pandas as pd
import numpy as np
import time
import io
import os
import html
import urllib.request
import json
from numbers import Number

# ==========================================
# ฟังก์ชันช่วยแปลง ค.ศ. เป็น พ.ศ. (ภาษาไทย)
# ==========================================
THAI_MONTHS = {
    1: 'มกราคม', 2: 'กุมภาพันธ์', 3: 'มีนาคม', 4: 'เมษายน',
    5: 'พฤษภาคม', 6: 'มิถุนายน', 7: 'กรกฎาคม', 8: 'สิงหาคม',
    9: 'กันยายน', 10: 'ตุลาคม', 11: 'พฤศจิกายน', 12: 'ธันวาคม'
}


def to_thai_date_str(dt):
    if pd.isna(dt):
        return 'N/A'
    if hasattr(dt, 'strftime'):
        return f"{dt.day} {THAI_MONTHS.get(dt.month, '')} {dt.year + 543}"
    return str(dt)


def to_thai_month_str(year_month_str):
    try:
        parts = year_month_str.split('-')
        return f"{THAI_MONTHS.get(int(parts[1]), '')} {int(parts[0]) + 543}"
    except Exception:
        return year_month_str


def to_thai_year_str(year_str):
    try:
        return str(int(year_str) + 543)
    except Exception:
        return year_str


def fmt_num(x):
    """จัดรูปแบบตัวเลข (รองรับ numpy ทุกชนิด)"""
    if isinstance(x, (Number, np.number)) and not isinstance(x, bool):
        if pd.isna(x):
            return "N/A"
        return f"{x:,.0f}" if float(x).is_integer() else f"{x:,.2f}"
    return x


def is_num(x):
    return isinstance(x, (Number, np.number)) and not isinstance(x, bool)


def to_numeric_smart(series, min_ratio=0.5):
    """แปลงเป็นตัวเลขเฉพาะเมื่อข้อมูลส่วนใหญ่แปลงได้ ไม่งั้นคงเป็นข้อความเดิม
    (แก้ปัญหาการเดาจากชื่อคอลัมน์ เช่น running_time ที่เป็นตัวเลขแต่มีคำว่า time)"""
    converted = pd.to_numeric(series.astype(str).str.replace(',', '', regex=False), errors='coerce')
    non_null = series.notna().sum()
    if non_null == 0:
        return converted
    if converted.notna().sum() / non_null >= min_ratio:
        return converted
    return series


# ==========================================
# 1. ตั้งค่าหน้าเว็บและสไตล์ (CSS)
# ==========================================
st.set_page_config(
    page_title="Turbine Monitoring System",
    page_icon="⚙️",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

    html, body, .stMarkdown, p, label {
        font-family: 'Inter', 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif !important;
    }

    /* ให้ไอคอนของ Streamlit (ลูกศร sidebar ฯลฯ) ใช้ฟอนต์ไอคอนของตัวเอง ไม่ถูกทับด้วย Inter */
    [data-testid="stIconMaterial"],
    .material-icons,
    .material-symbols-rounded,
    .material-symbols-outlined {
        font-family: 'Material Symbols Rounded', 'Material Symbols Outlined', 'Material Icons' !important;
    }

    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}

    h1, h2, h3 {
        color: #1E3A8A;
        font-family: 'Inter', 'Segoe UI', sans-serif !important;
        font-weight: 700;
    }

    .latest-time { color: #e11d48; font-weight: bold; font-size: 1.2rem; }
    .status-live { color: #10b981; font-weight: bold; }
</style>
""", unsafe_allow_html=True)

st.title("⚙️ ELECTRIC TURBINE")
st.markdown("ระบบมอนิเตอร์และสรุปผล")
st.markdown("---")

# ==========================================
# 2. ตั้งค่าการเชื่อมต่อ Supabase (อ่านจาก secrets ไม่ฝังในโค้ด)
# ==========================================
def get_secret(name):
    try:
        return st.secrets[name]
    except Exception:
        return os.environ.get(name)


# ใช้ค่าจาก secrets/environment ก่อน ถ้าไม่มีให้ใช้ค่าเริ่มต้นด้านล่าง
SUPABASE_URL = get_secret("SUPABASE_URL") or "https://egjpkwgyrhsmajkumnyc.supabase.co"
SUPABASE_KEY = get_secret("SUPABASE_KEY") or "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImVnanBrd2d5cmhzbWFqa3VtbnljIiwicm9sZSI6ImFub24iLCJpYXQiOjE3OTI1MjkzOTYsImV4cCI6MjEwODEwNTM5Nn0.klAeK81K7_ZI_1Z5ow8CeIcJLZ26LxoReJzcf-ETPGo"

if not SUPABASE_URL or not SUPABASE_KEY:
    st.error(
        "❌ ยังไม่ได้ตั้งค่า SUPABASE_URL / SUPABASE_KEY\n\n"
        "สร้างไฟล์ `.streamlit/secrets.toml` แล้วใส่:\n\n"
        "```toml\nSUPABASE_URL = \"https://xxxx.supabase.co\"\nSUPABASE_KEY = \"your-anon-key\"\n```\n"
        "หากรันบน Streamlit Cloud ให้ใส่ในเมนู Settings → Secrets"
    )
    st.stop()

MAX_ROWS = 20000   # จำนวนแถวสูงสุดที่ดึง (ใหม่สุดก่อน)
PAGE_SIZE = 1000   # Supabase จำกัดแถวต่อ request


def fetch_table(table, max_rows=MAX_ROWS):
    """ดึงข้อมูลเรียงจากใหม่ไปเก่า พร้อม pagination"""
    rows, offset = [], 0
    while offset < max_rows:
        url = f"{SUPABASE_URL}/rest/v1/{table}?select=*&order=created_at.desc"
        req = urllib.request.Request(url, headers={
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}",
            "Range-Unit": "items",
            "Range": f"{offset}-{offset + PAGE_SIZE - 1}",
        })
        with urllib.request.urlopen(req, timeout=20) as response:
            batch = json.loads(response.read().decode())
        rows.extend(batch)
        if len(batch) < PAGE_SIZE:
            break
        offset += PAGE_SIZE
    return rows


@st.cache_data(ttl=30)
def load_data():
    try:
        df = pd.DataFrame(fetch_table("shinko_data"))
        if not df.empty:
            if 'created_at' in df.columns:
                df['created_at'] = pd.to_datetime(df['created_at'], utc=True).dt.tz_convert('Asia/Bangkok')
                df['date_only'] = df['created_at'].dt.date
                df['year_month'] = df['created_at'].dt.strftime('%Y-%m')
                df['year_only'] = df['created_at'].dt.strftime('%Y')

            skip_cols = ['id', 'created_at', 'date_only', 'year_month', 'year_only']
            for col in df.columns:
                if col not in skip_cols:
                    df[col] = to_numeric_smart(df[col])

            if 'created_at' in df.columns:
                df = df.sort_values('created_at').reset_index(drop=True)
        return df, None
    except Exception as e:
        return pd.DataFrame(), str(e)


@st.cache_data(ttl=30)
def load_logs_data():
    try:
        df_logs = pd.DataFrame(fetch_table("turbine_logs", max_rows=200))
        if not df_logs.empty and 'created_at' in df_logs.columns:
            df_logs['created_at'] = pd.to_datetime(df_logs['created_at'], utc=True).dt.tz_convert('Asia/Bangkok')
            df_logs = df_logs.sort_values('created_at', ascending=False)
        return df_logs, None
    except Exception as e:
        return pd.DataFrame(), str(e)


df, db_error = load_data()
df_logs, logs_error = load_logs_data()

# ==========================================
# แจ้งเตือนเมื่อข้อมูลไม่อัปเดต (ส่วนขยาย Chrome ส่งข้อมูลทุก 1 นาที)
# ==========================================
STALE_MINUTES = 5  # เตือนเมื่อแถวล่าสุดเก่ากว่ากี่นาที


def fmt_age(minutes):
    minutes = int(minutes)
    if minutes < 60:
        return f"{minutes} นาที"
    if minutes < 1440:
        return f"{minutes // 60} ชั่วโมง {minutes % 60} นาที"
    return f"{minutes // 1440} วัน {(minutes % 1440) // 60} ชั่วโมง"


if not df.empty and 'created_at' in df.columns:
    _latest_ts = df['created_at'].max()
    _age_min = (pd.Timestamp.now(tz='Asia/Bangkok') - _latest_ts).total_seconds() / 60
    if _age_min > STALE_MINUTES:
        st.error(
            f"⚠️ **ขณะนี้ข้อมูลไม่อัปเดต** บันทึกเมื่อวันที่ {to_thai_date_str(_latest_ts)} "
            f"เวลา {_latest_ts.strftime('%H:%M:%S')} น. (ผ่านมาแล้ว {fmt_age(_age_min)}) "
        )

# ==========================================
# 3. ส่วน Sidebar
# ==========================================
with st.sidebar:
    st.header("⚡ ควบคุมระบบ")
    auto_refresh = st.toggle("เปิดโหมดดึงข้อมูลอัตโนมัติ (ทุกๆ 60 วินาที)", value=False)

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

    # หน่วยของคอลัมน์ watt_hour (ข้อมูลมาจากเว็บอื่น จึงให้เลือกเอง)
    WH_UNITS = {"Wh": 0.001, "kWh": 1.0, "MWh": 1000.0}  # ตัวคูณแปลงเป็น kWh
    wh_unit = st.selectbox(
        "🔌 หน่วยของ WATT HOUR",
        list(WH_UNITS.keys()),
        index=2,
        help="ถ้าไม่แน่ใจ ให้เทียบผลที่ได้กับกำลังผลิตจริง (เครื่องนี้ rated 18,000 kW ≈ 18 MWh ต่อชั่วโมง)"
    )

    st.subheader("📊 เลือกการสรุปผล")
    summary_mode = st.radio("สรุปผล", ["Latest (24 ชม. ล่าสุด)", "Daily (รายวัน)", "Monthly (รายเดือน)", "Yearly (รายปี)"])

    selected_target = None
    has_df = not df.empty
    if summary_mode == "Daily (รายวัน)":
        days = sorted(df['date_only'].dropna().unique(), reverse=True) if has_df and 'date_only' in df.columns else []
        selected_target = st.selectbox("เลือกวันที่", days, format_func=to_thai_date_str) if days else None
    elif summary_mode == "Monthly (รายเดือน)":
        months = sorted(df['year_month'].dropna().unique(), reverse=True) if has_df and 'year_month' in df.columns else []
        selected_target = st.selectbox("เลือกเดือน", months, format_func=to_thai_month_str) if months else None
    elif summary_mode == "Yearly (รายปี)":
        years = sorted(df['year_only'].dropna().unique(), reverse=True) if has_df and 'year_only' in df.columns else []
        selected_target = st.selectbox("เลือกปี", years, format_func=to_thai_year_str) if years else None

    if has_df:
        st.caption(f"โหลดข้อมูล {len(df):,} แถว (สูงสุด {MAX_ROWS:,} แถวล่าสุด)")
    st.caption("Developed for Senior Project")

# ==========================================
# เกณฑ์ค่า RATED / ALARM / TRIP
# ==========================================
def get_limits(title):
    """คืนค่า dict: rated, unit, alarm=(ค่า, 'H'/'L'), trip=(ค่า, 'H'/'L')"""
    t = title.upper()
    if "GENERATOR" in t and "OUTPUT" in t:
        return {"rated": (18000, "kW")}
    if "SPEED" in t:
        return {"rated": (1500, "RPM"), "trip": (1635, "H", "RPM")}
    if "INLET" in t and "PRESS" in t:
        return {"rated": (40, "barG"), "alarm": (34, "L", "barG"), "trip": (30, "L", "barG")}
    if "EXH" in t and "PRESS" in t:
        return {"rated": (1.5, "barG"), "alarm": (2.5, "H", "barG"), "trip": (3, "H", "barG")}
    if "LUB" in t and "PRESS" in t:
        return {"alarm": (0.7, "L", "barG"), "trip": (0.5, "L", "barG")}
    if "CONT" in t and "PRESS" in t:
        return {"alarm": (7, "L", "barG")}
    if "INLET" in t and "TEMP" in t:
        return {"rated": (440, "°C")}
    if "LUB" in t and "OUTLET" in t and "TEMP" in t:
        return {"alarm": (50, "H", "°C")}
    if "BEARING" in t and "TEMP" in t:
        return {"alarm": (75, "H", "°C")}
    return {}


C_ALARM, C_TRIP = "#f59e0b", "#ef4444"


def get_threshold_tags(limits):
    def tag_l(label, val):
        return (f'<div style="display:flex;align-items:center;gap:8px;margin-bottom:4px;">'
                f'<span style="background-color:#38bdf8;color:white;padding:4px 8px;border-radius:4px;font-size:0.8rem;font-weight:600;">{label}</span>'
                f'<span style="color:#334155;font-size:0.95rem;font-weight:600;">{val}</span></div>')

    def tag_r(label, val, bg):
        return (f'<div style="display:flex;align-items:center;justify-content:flex-end;gap:6px;margin-bottom:4px;">'
                f'<span style="background-color:{bg};color:white;padding:2px 6px;border-radius:4px;font-size:0.75rem;font-weight:600;">{label}</span>'
                f'<span style="color:#334155;font-size:0.85rem;font-weight:600;">{val}</span></div>')

    left, right = "", ""
    if "rated" in limits:
        v, u = limits["rated"]
        left = tag_l("RATED", f"{v:,} {u}")
    # แสดง TRIP ก่อน ALARM ถ้าเป็นแบบ High, ALARM ก่อน TRIP ถ้าเป็นแบบ Low
    items = []
    if "trip" in limits and limits["trip"][1] == "H":
        items.append(("TRIP(H)", limits["trip"], C_TRIP))
    if "alarm" in limits and limits["alarm"][1] == "H":
        items.append(("ALARM(H)", limits["alarm"], C_ALARM))
    if "alarm" in limits and limits["alarm"][1] == "L":
        items.append(("ALARM(L)", limits["alarm"], C_ALARM))
    if "trip" in limits and limits["trip"][1] == "L":
        items.append(("TRIP(L)", limits["trip"], C_TRIP))
    for label, (v, _d, u), color in items:
        right += tag_r(label, f"{v:,} {u}", color)
    return left, right


def get_alarm_status(val, limits):
    """คืน 'TRIP' / 'ALARM' / None ตามค่าที่วัดได้"""
    if not is_num(val) or pd.isna(val):
        return None
    for key, name in (("trip", "TRIP"), ("alarm", "ALARM")):
        if key in limits:
            limit, direction = limits[key][0], limits[key][1]
            if (direction == "H" and val >= limit) or (direction == "L" and val <= limit):
                return name
    return None


def get_unit(col_name):
    name = col_name.lower()
    if 'watt_hour' in name or 'watthour' in name:
        return wh_unit
    if 'running' in name:
        return "min"
    if 'time' in name or 'date' in name or 'stamp' in name:
        return ""
    if 'temp' in name:
        return "°C"
    if 'press' in name:
        return "barG"
    if 'speed' in name or 'rpm' in name:
        return "RPM"
    if 'watt' in name or 'power' in name or 'generator' in name:
        return "kW"
    if 'rate' in name:
        return "%"
    if 'flow' in name:
        return "m³/h"
    return ""


# คำแปลภาษาไทย (ศัพท์วิศวกรรม) ของชื่อพารามิเตอร์ ใช้แสดงในไฟล์ Excel
# ถ้ามีคอลัมน์ใหม่ที่ไม่อยู่ในรายการนี้ จะแสดงเป็นภาษาอังกฤษอย่างเดียว เพิ่มคำแปลได้ที่นี่
THAI_PARAM_NAMES = {
    "GENERATOR OUTPUT": "กำลังไฟฟ้าของเครื่องกำเนิดไฟฟ้า",
    "OPERATING RATE": "อัตราการเดินเครื่อง",
    "WATT HOUR": "พลังงานไฟฟ้าสะสม",
    "STARTS": "จำนวนครั้งการสตาร์ท",
    "TRIPS": "จำนวนครั้งที่ทริป (หยุดเครื่องฉุกเฉิน)",
    "ALARMS": "จำนวนครั้งที่แจ้งเตือน (อะลาร์ม)",
    "RUNNING TIME": "เวลาเดินเครื่องสะสม",
    "TURBINE SPEED": "ความเร็วรอบกังหัน",
    "INLET STEAM FLOW": "อัตราการไหลของไอน้ำขาเข้า",
    "ACTUATOR DEMAND": "สัญญาณสั่งงานแอกชูเอเตอร์",
    "INLET STEAM PRESS": "ความดันไอน้ำขาเข้า",
    "AVG 1ST STAGE STEAM PRESS": "ความดันไอน้ำเฉลี่ยที่สเตจแรก",
    "EXH STEAM PRESS": "ความดันไอน้ำขาออก",
    "LUB OIL PRESS": "ความดันน้ำมันหล่อลื่น",
    "CONT OIL PRESS": "ความดันน้ำมันควบคุม",
    "INLET STEAM TEMP": "อุณหภูมิไอน้ำขาเข้า",
    "EXH STEAM TEMP": "อุณหภูมิไอน้ำขาออก",
    "LUB OIL OUTLET TEMP": "อุณหภูมิน้ำมันหล่อลื่นขาออก",
    "TURBINE THRUST BEARING TEMP": "อุณหภูมิแบริ่งรับแรงตามแนวแกนของกังหัน",
    "TURBINE BEARING GOV TEMP": "อุณหภูมิแบริ่งกังหันด้านโกเวอร์เนอร์",
    "TURBINE BEARING CP TEMP": "อุณหภูมิแบริ่งกังหันด้านคัปปลิง",
    "PINION BEARING TBN TEMP": "อุณหภูมิแบริ่งพิเนียนด้านกังหัน",
    "WHEEL BEARING TBN TEMP": "อุณหภูมิแบริ่งวีลเกียร์ด้านกังหัน",
    # ชื่อหัวการ์ดในหน้า Live Status
    "THE LAST START UP DATE TIME": "วัน-เวลาที่สตาร์ทเครื่องล่าสุด",
    "THE NUMBER OF STARTS": "จำนวนครั้งการสตาร์ท",
    "THE NUMBER OF TRIPS": "จำนวนครั้งที่ทริป (หยุดเครื่องฉุกเฉิน)",
    "THE NUMBER OF ALARMS": "จำนวนครั้งที่แจ้งเตือน (อะลาร์ม)",
    "TURBINE RUNNING TIME": "เวลาเดินเครื่องสะสมของกังหัน",
}


def thai_name(name):
    """คืนคำแปลไทยของชื่อพารามิเตอร์ (ไม่มีในรายการจะคืน None)"""
    return THAI_PARAM_NAMES.get(str(name).upper().replace('_', ' ').strip())


def thai_title_html(name):
    """บรรทัดคำแปลไทยใต้ชื่อบนหัวการ์ด"""
    th = thai_name(name)
    if not th:
        return ''
    return f'<div style="font-weight:400;font-size:0.8rem;letter-spacing:0;">({html.escape(th)})</div>'

HEADER_COLORS = ["#f87171", "#a855f7", "#38bdf8", "#ec4899", "#3b82f6", "#10b981"]

# ==========================================
# 4. สร้าง 3 แท็บหลัก
# ==========================================
tab1, tab2, tab3 = st.tabs(["🔴 สถานะเครื่องจักรขณะนี้ (Live Status)", "📊 สรุปผลภาพรวม (Summary)", "📂 อัปโหลดไฟล์ Excel (Custom Upload)"])

# ---------------- แท็บที่ 1 ----------------
with tab1:
    if db_error:
        st.error(f"❌ เกิดข้อผิดพลาดในการเชื่อมต่อฐานข้อมูล Supabase: {db_error}")
    elif df.empty:
        st.warning("⏳ ยังไม่มีข้อมูลในระบบ หรือตารางว่างเปล่า...")
    else:
        latest_data = df.iloc[-1]
        latest_time = latest_data['created_at'].strftime('%H:%M:%S') if 'created_at' in df.columns else 'N/A'
        latest_date_thai = to_thai_date_str(latest_data['created_at']) if 'created_at' in df.columns else 'N/A'

        st.subheader(f"🔴 มอนิเตอร์ขณะนี้ (ประจำวันที่ {latest_date_thai})")
        if auto_refresh:
            st.markdown(f"สถานะ: <span class='status-live'>ออนไลน์ ⚪ </span> | อัปเดตข้อมูลล่าสุดเมื่อเวลา: <span class='latest-time'>{latest_time}</span>", unsafe_allow_html=True)
        else:
            st.markdown(f"สถานะ: ออฟไลน์ ⚪ | อัปเดตข้อมูลล่าสุดเมื่อเวลา: <span class='latest-time'>{latest_time}</span>", unsafe_allow_html=True)
        st.markdown("<br>", unsafe_allow_html=True)

        with st.expander("📖 คำอธิบายสัญลักษณ์"):
            st.markdown(
                "- **RATED** = ค่าพิกัดออกแบบของเครื่อง\n"
                "- **ALARM(H) / ALARM(L)** = แจ้งเตือนเมื่อค่าสูงเกิน (H) หรือต่ำกว่า (L) ค่าที่กำหนด\n"
                "- **TRIP(H) / TRIP(L)** = ทริป คือระบบสั่งหยุดเครื่องอัตโนมัติเมื่อค่าสูงเกิน (H) หรือต่ำกว่า (L) ค่าที่กำหนด\n"
                "- **barG** = ความดันเกจ (บาร์เกจ), **kW** = กิโลวัตต์, **RPM** = รอบต่อนาที, "
                "**°C** = องศาเซลเซียส, **m³/h** = ลูกบาศก์เมตรต่อชั่วโมง, **min** = นาที"
            )

        exclude_cols = ['id', 'created_at', 'date_only', 'year_month', 'year_only']
        all_sensor_cols = [col for col in latest_data.index if col not in exclude_cols]

        num_columns = 2
        for i in range(0, len(all_sensor_cols), num_columns):
            cols = st.columns(num_columns)
            for j in range(num_columns):
                if i + j >= len(all_sensor_cols):
                    continue
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
                if val is None or (not isinstance(val, str) and pd.isna(val)):
                    display_val = "N/A"
                elif is_num(val):
                    display_val = f"{fmt_num(val)} {unit}".strip()
                else:
                    display_val = f"{val} {unit}".strip()

                bg_color = HEADER_COLORS[(i + j) % len(HEADER_COLORS)]
                limits = get_limits(display_title)
                left_tags, right_tags = get_threshold_tags(limits)

                status = get_alarm_status(val, limits)
                border = "1px solid #e2e8f0"
                badge = ""
                value_color = "#0f172a"
                if status == "TRIP":
                    border, value_color = f"2px solid {C_TRIP}", C_TRIP
                    badge = f'<span style="background:{C_TRIP};color:white;padding:2px 8px;border-radius:4px;font-size:0.75rem;margin-left:8px;">TRIP (ทริป)</span>'
                elif status == "ALARM":
                    border, value_color = f"2px solid {C_ALARM}", C_ALARM
                    badge = f'<span style="background:{C_ALARM};color:white;padding:2px 8px;border-radius:4px;font-size:0.75rem;margin-left:8px;">ALARM (แจ้งเตือน)</span>'

                card_html = (
                    f'<div style="background-color:#ffffff;border:{border};border-radius:12px;box-shadow:0 4px 6px rgba(0,0,0,0.03);overflow:hidden;margin-bottom:20px;">'
                    f'<div style="background-color:{bg_color};color:white;padding:10px 15px;font-weight:600;font-size:0.95rem;text-align:center;letter-spacing:0.5px;">{html.escape(display_title)}{badge}{thai_title_html(display_title)}</div>'
                    f'<div style="padding:18px 20px;display:flex;align-items:center;justify-content:space-between;min-height:80px;">'
                    f'<div style="flex:1;">{left_tags}</div>'
                    f'<div style="flex:1.5;text-align:center;color:{value_color};font-size:1.8rem;font-weight:700;">{html.escape(display_val)}</div>'
                    f'<div style="flex:1;">{right_tags}</div></div></div>'
                )
                cols[j].markdown(card_html, unsafe_allow_html=True)

        st.markdown("<br><hr>", unsafe_allow_html=True)
        st.subheader("📋 บันทึกเหตุการณ์สำคัญ (Event Summary)")
        if logs_error:
            st.warning(f"ดึงบันทึกเหตุการณ์ไม่สำเร็จ: {logs_error}")
        elif not df_logs.empty:
            latest_log = df_logs.iloc[0]
            log_time = latest_log.get('created_at', 'N/A')
            log_time_str = log_time.strftime('%Y-%m-%d %H:%M:%S') if pd.notna(log_time) and hasattr(log_time, 'strftime') else str(log_time)
            log_msg = html.escape(str(latest_log.get('message', latest_log.get('event', 'Turbine event occurred.'))))
            log_cause = html.escape(str(latest_log.get('cause', latest_log.get('description', ''))))

            st.markdown(f"""
            <div style="background-color:#ffffff;border:1px solid #e2e8f0;border-radius:12px;box-shadow:0 4px 6px rgba(0,0,0,0.03);overflow:hidden;margin-top:15px;">
                <div style="background-color:#06b6d4;color:white;padding:12px 20px;font-weight:600;font-size:1.1rem;text-align:center;">⚠️ Event Summary (สรุปเหตุการณ์)</div>
                <div style="padding:25px;text-align:center;color:#1e293b;">
                    <div style="font-size:1.15rem;font-weight:600;margin-bottom:10px;color:#334155;">{log_time_str}</div>
                    <div style="font-size:1.05rem;margin-bottom:8px;font-weight:500;">{log_msg}</div>
                    <div style="font-size:1.05rem;color:#e11d48;font-weight:700;">{log_cause}</div>
                </div>
            </div>
            """, unsafe_allow_html=True)
        else:
            st.info("ไม่มีบันทึกเหตุการณ์ (Log) ในระบบ")

# ---------------- แท็บที่ 2 ----------------
with tab2:
    if df.empty:
        st.warning("⏳ ไม่พบข้อมูลในระบบ...")
    else:
        if summary_mode.startswith("Latest"):
            end_t = df['created_at'].max()
            filtered_df = df[df['created_at'] >= end_t - pd.Timedelta(hours=24)]
            mode_label = "24 ชั่วโมงล่าสุด"
        elif summary_mode == "Daily (รายวัน)" and selected_target:
            filtered_df = df[df['date_only'] == selected_target]
            mode_label = f"ประจำวันที่ {to_thai_date_str(selected_target)}"
        elif summary_mode == "Monthly (รายเดือน)" and selected_target:
            filtered_df = df[df['year_month'] == selected_target]
            mode_label = f"ประจำเดือน {to_thai_month_str(selected_target)}"
        elif summary_mode == "Yearly (รายปี)" and selected_target:
            filtered_df = df[df['year_only'] == selected_target]
            mode_label = f"ประจำปี {to_thai_year_str(selected_target)}"
        else:
            filtered_df = df.copy()
            mode_label = "ภาพรวมทั้งหมด"

        if filtered_df.empty:
            st.warning(f"⏳ ไม่พบข้อมูลในช่วง {mode_label}")
        else:
            total_production_mwh = 0.0
            if 'watt_hour' in filtered_df.columns and pd.api.types.is_numeric_dtype(filtered_df['watt_hour']):
                # ใช้ผลรวมของส่วนต่างที่เป็นบวก เพื่อไม่ให้ผิดเมื่อมิเตอร์รีเซ็ตเป็น 0
                diffs = filtered_df.sort_values('created_at')['watt_hour'].diff().clip(lower=0)
                total_kwh = diffs.sum() * WH_UNITS[wh_unit]
                total_production_mwh = total_kwh / 1000
            else:
                total_kwh = 0.0
            total_revenue = total_kwh * electric_rate

            st.subheader(f"📌 สรุปผลการดำเนินงาน ({mode_label})")
            col1, col2, col3 = st.columns(3)
            col1.metric("⚡ พลังงานที่ผลิตได้ (MWh)", f"{total_production_mwh:,.3f}")
            col2.metric("💰 รายได้โดยประมาณ (บาท)", f"{total_revenue:,.2f}")
            col3.metric("⏱️ จำนวนข้อมูลทั้งหมด (รายการ)", f"{len(filtered_df):,}")

            st.markdown("<br>", unsafe_allow_html=True)
            st.subheader("📈 แนวโน้มกำลังการผลิต (Generator Output)")
            if 'generator_output' in filtered_df.columns:
                chart_data = filtered_df.set_index('created_at')['generator_output']
                st.area_chart(chart_data, color="#3b82f6")
            else:
                st.info("ไม่พบข้อมูล Generator Output สำหรับสร้างกราฟ")

            st.markdown("<br>", unsafe_allow_html=True)
            st.subheader("📊 ตารางสรุปค่าสถิติ (Statistics)")

            numeric_cols = [c for c in filtered_df.select_dtypes(include=['number']).columns if c != 'id']
            if numeric_cols:
                summary_df = filtered_df[numeric_cols].agg(['mean', 'max', 'min']).T
                summary_df.columns = ['ค่าเฉลี่ย (Mean)', 'ค่าสูงสุด (Max)', 'ค่าต่ำสุด (Min)']
                units_list = [get_unit(str(c)) for c in summary_df.index]
                summary_df.index = [str(c).upper().replace('_', ' ') for c in summary_df.index]

                display_summary_df = summary_df.apply(lambda s: s.map(fmt_num))
                display_summary_df.index = [f"{n} ({thai_name(n)})" if thai_name(n) else n for n in display_summary_df.index]
                st.dataframe(display_summary_df, use_container_width=True)

                export_df = summary_df.reset_index()
                export_df.columns = ['พารามิเตอร์ (Parameter)', 'ค่าเฉลี่ย (Mean)', 'ค่าสูงสุด (Max)', 'ค่าต่ำสุด (Min)']
                export_df.insert(1, 'หน่วย (Unit)', units_list)
                # ใส่คำแปลภาษาไทยในวงเล็บ ขึ้นบรรทัดใหม่ใต้ชื่อภาษาอังกฤษ
                export_df['พารามิเตอร์ (Parameter)'] = export_df['พารามิเตอร์ (Parameter)'].map(
                    lambda n: f"{n}\n({THAI_PARAM_NAMES[n]})" if n in THAI_PARAM_NAMES else n
                )

                HEADER_ROW = 6  # แถว 1-4 เป็นหัวรายงาน, แถว 5 เว้นว่าง, แถว 6 เป็นหัวตาราง
                t_min, t_max = filtered_df['created_at'].min(), filtered_df['created_at'].max()

                output = io.BytesIO()
                with pd.ExcelWriter(output, engine='openpyxl') as writer:
                    export_df.to_excel(writer, index=False, startrow=HEADER_ROW - 1, sheet_name='Summary')
                    worksheet = writer.sheets['Summary']

                    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
                    side = Side(style='thin', color='000000')  # เส้นกรอบสีดำ เห็นชัดทุกช่อง
                    thin_border = Border(left=side, right=side, top=side, bottom=side)
                    header_fill = PatternFill(start_color='BFDBFE', end_color='BFDBFE', fill_type='solid')
                    zebra_fill = PatternFill(start_color='F1F5F9', end_color='F1F5F9', fill_type='solid')
                    header_font = Font(name='Tahoma', size=11, bold=True, color='334155')
                    cell_font = Font(name='Tahoma', size=11, color='1E293B')

                    # ----- หัวรายงาน -----
                    worksheet.cell(row=1, column=1, value="สรุปผลการดำเนินงาน ELECTRIC TURBINE").font = Font(name='Tahoma', size=14, bold=True, color='1E3A8A')
                    worksheet.cell(row=2, column=1, value=f"ช่วงเวลาที่สรุป: {mode_label}").font = cell_font
                    worksheet.cell(row=3, column=1, value=(
                        f"ข้อมูลตั้งแต่ {to_thai_date_str(t_min)} {t_min.strftime('%H:%M')} น. "
                        f"ถึง {to_thai_date_str(t_max)} {t_max.strftime('%H:%M')} น. ({len(filtered_df):,} รายการ)"
                    )).font = cell_font
                    worksheet.cell(row=4, column=1, value=(
                        f"พลังงานที่ผลิตได้ {total_production_mwh:,.3f} MWh | "
                        f"รายได้โดยประมาณ {total_revenue:,.2f} บาท (อัตรา {electric_rate:,.2f} บาท/หน่วย)"
                    )).font = cell_font

                    # ----- หัวตาราง -----
                    n_cols = len(export_df.columns)
                    for col_num in range(1, n_cols + 1):
                        cell = worksheet.cell(row=HEADER_ROW, column=col_num)
                        cell.font, cell.fill, cell.border = header_font, header_fill, thin_border
                        cell.alignment = Alignment(horizontal='left' if col_num == 1 else ('center' if col_num == 2 else 'right'), vertical='center')

                    # ----- ข้อมูล -----
                    for row_num in range(HEADER_ROW + 1, HEADER_ROW + len(export_df) + 1):
                        for col_num in range(1, n_cols + 1):
                            cell = worksheet.cell(row=row_num, column=col_num)
                            cell.font, cell.border = cell_font, thin_border
                            if (row_num - HEADER_ROW) % 2 == 0:
                                cell.fill = zebra_fill  # สลับสีแถว ช่วยให้อ่านตามแถวง่ายขึ้น
                            cell.alignment = Alignment(horizontal='left' if col_num == 1 else ('center' if col_num == 2 else 'right'), vertical='center', wrap_text=(col_num == 1))
                            if col_num == 1 and '\n' in str(cell.value):
                                worksheet.row_dimensions[row_num].height = 32  # เผื่อที่ 2 บรรทัด
                            if col_num > 2 and is_num(cell.value):
                                cell.number_format = '#,##0' if float(cell.value).is_integer() else '#,##0.00'

                    # ความกว้างคอลัมน์คิดจากตารางเท่านั้น (ไม่รวมหัวรายงานที่ยาว)
                    for column in worksheet.columns:
                        max_len_col = max(max(len(line) for line in str(c.value or '').split('\n')) for c in column if c.row >= HEADER_ROW)
                        worksheet.column_dimensions[column[0].column_letter].width = max(max_len_col + 6, 16)

                    worksheet.freeze_panes = f"A{HEADER_ROW + 1}"

                st.download_button(
                    label="📥 ดาวน์โหลดตารางสรุปผล Excel (.xlsx)",
                    data=output.getvalue(),
                    file_name=f"turbine_summary_{summary_mode.split()[0].lower()}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True
                )

# ---------------- แท็บที่ 3 ----------------
with tab3:
    st.subheader("📂 อัปโหลดไฟล์ Excel ของคุณเพื่อแสดงผลข้อมูล")
    st.markdown("ลากไฟล์ Excel (`.xlsx` หรือ `.csv`) ที่กรอกข้อมูลเสร็จแล้วมาวางด้านล่างนี้ได้เลย ระบบจะแสดงผลออกมาทันทีครับ")

    uploaded_file = st.file_uploader("ลากไฟล์มาวางที่นี่ หรือคลิกเพื่อเลือกไฟล์", type=["xlsx", "csv"], key="custom_excel_uploader")

    if uploaded_file is not None:
        try:
            up_df = pd.read_csv(uploaded_file) if uploaded_file.name.endswith('.csv') else pd.read_excel(uploaded_file)

            if 'created_at' not in up_df.columns and 'timestamp' in up_df.columns:
                up_df['created_at'] = pd.to_datetime(up_df['timestamp'])
            elif 'created_at' in up_df.columns:
                up_df['created_at'] = pd.to_datetime(up_df['created_at'])
            else:
                up_df['created_at'] = pd.date_range(start='2026-01-01 00:00:00', periods=len(up_df), freq='h')

            skip_cols = ['id', 'created_at']
            for col in up_df.columns:
                if col not in skip_cols:
                    up_df[col] = to_numeric_smart(up_df[col])

            up_df = up_df.sort_values('created_at', ascending=False)
            latest_up = up_df.iloc[0]

            st.success("🎉 อัปโหลดและประมวลผลไฟล์สำเร็จ! ข้อมูลถูกแสดงผลด้านล่างนี้ครับ")
            st.markdown("---")

            up_sensor_cols = [c for c in latest_up.index if c not in skip_cols]
            cols = st.columns(2)
            for idx, c_name in enumerate(up_sensor_cols):
                val = latest_up[c_name]
                c_title = html.escape(str(c_name).upper().replace('_', ' '))
                val_str = html.escape(str(fmt_num(val)))
                bg_color = HEADER_COLORS[idx % len(HEADER_COLORS)]

                card_box = (
                    f'<div style="background-color:#ffffff;border:1px solid #e2e8f0;border-radius:12px;padding:0;margin-bottom:20px;box-shadow:0 4px 6px rgba(0,0,0,0.03);overflow:hidden;">'
                    f'<div style="background-color:{bg_color};color:white;padding:10px 15px;font-weight:600;font-size:0.95rem;text-align:center;letter-spacing:0.5px;">{c_title}{thai_title_html(c_name)}</div>'
                    f'<div style="padding:20px;text-align:center;color:#0f172a;font-size:1.8rem;font-weight:700;">{val_str}</div></div>'
                )
                cols[idx % 2].markdown(card_box, unsafe_allow_html=True)

            st.markdown("### 📋 ตารางข้อมูลดิบจากไฟล์ที่คุณอัปโหลด")
            st.dataframe(up_df, use_container_width=True)

        except Exception as e:
            st.error(f"เกิดข้อผิดพลาดในการอ่านไฟล์: {e}")
    else:
        st.info("💡 ยังไม่ได้อัปโหลดไฟล์ กรุณาเลือกไฟล์ Excel ในช่องด้านบนเพื่อดูผลลัพธ์")

# ==========================================
# 5. ระบบ Auto-Refresh (ทุก 60 วินาที)
# ==========================================
if auto_refresh:
    try:
        from streamlit_autorefresh import st_autorefresh
        st_autorefresh(interval=60_000, key="turbine_autorefresh")
    except ImportError:
        # ถ้ายังไม่ได้ติดตั้ง streamlit-autorefresh ใช้วิธีเดิมแทน (หน้าจะหน่วงระหว่างรอ)
        st.sidebar.warning("แนะนำ: pip install streamlit-autorefresh เพื่อให้ refresh ไม่ค้างหน้า")
        time.sleep(60)
        st.cache_data.clear()
        st.rerun()
