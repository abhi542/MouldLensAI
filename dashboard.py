import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import pymongo
from datetime import datetime, timedelta
import os
from config import settings

st.set_page_config(page_title="MouldLensAI Monitor", page_icon="⚙️", layout="wide")

# Database Connection
@st.cache_resource
def init_connection():
    return pymongo.MongoClient(settings.mongodb_uri)

client = init_connection()
db = client[settings.mongodb_db_name]

def fetch_recent_logs(hours=24):
    import datetime as dt
    cutoff = datetime.now(dt.timezone.utc) - timedelta(hours=hours)
    cursor = db["mould_readings"].find({"timestamp": {"$gte": cutoff}}).sort("timestamp", -1)
    logs = list(cursor)
    return logs

# Fetch Data
st.title("🏭 MouldLensAI Telemetry")
st.markdown("Real-time monitoring and analytics for the Cope & Drag extraction cameras.")

with st.spinner("Fetching latest telemetry..."):
    raw_logs = fetch_recent_logs()

if not raw_logs:
    st.info("No logs found for the last 24 hours.")
    st.stop()

# Convert to DataFrame
df = pd.DataFrame(raw_logs)

# Schema Migration / Backward Compatibility
if 'status' not in df.columns:
    df['status'] = "success"
if 'mould_detected' in df.columns:
    df['status'] = df.apply(
        lambda x: x['status'] if pd.notna(x.get('status')) else ("success" if x.get('mould_detected', True) else "empty"),
        axis=1
    )
    
if 'processing_time_ms' not in df.columns:
    df['processing_time_ms'] = df.get('scan_time_ms', 0)
else:
    # Fill NaN just in case mixed records
    df['processing_time_ms'] = df['processing_time_ms'].fillna(df.get('scan_time_ms', 0))

if 'camera_id' not in df.columns:
    df['camera_id'] = "CAM_01"
df['camera_id'] = df['camera_id'].fillna("CAM_01")
df['status'] = df['status'].fillna("success")

# 1. System Health / Status Indicator
last_3_status = df.head(3)['status'].tolist()
system_ok = not (len(last_3_status) == 3 and all(s == "empty" for s in last_3_status))

if system_ok:
    st.success("🟢 System Status: **HEALTHY** (Cameras detecting regular moulds)")
else:
    st.error("🔴 System Status: **DOWNTIME DETECTED** (Last 3 captures were empty. Check camera/belt!)")

st.markdown("---")

# 2. Key Metrics
col1, col2, col3, col4, col5 = st.columns(5)

total_captures = len(df)
success_count = len(df[df['status'] == 'success'])
empty_count = len(df[df['status'] == 'empty'])
success_rate = (success_count / total_captures) * 100 if total_captures > 0 else 0
avg_processing_time = df['processing_time_ms'].mean()

# Safely get last valid mould IF one exists
last_valid = df[df['status'] == 'success'].head(1)
last_mould_id = "N/A"
if not last_valid.empty:
    mould = last_valid.iloc[0]
    cope = mould.get('cope', 'Unknown')
    drag = mould.get('drag', {})
    drag_main = drag.get('main', 'Unknown') if isinstance(drag, dict) else 'Unknown'
    drag_sub = drag.get('sub', '') if isinstance(drag, dict) else ''
    
    if pd.isna(drag_sub) or not drag_sub:
        last_mould_id = f"C:{cope} | D:{drag_main}"
    else:
        last_mould_id = f"C:{cope} | D:{drag_main} ({drag_sub})"

with col1:
    st.metric("Total Captures (24h)", f"{total_captures:,}")
with col2:
    st.metric("Success Rate", f"{success_rate:.1f}%")
with col3:
    st.metric("Empty Frames", f"{empty_count:,}")
with col4:
    st.metric("Avg Processing Time", f"{avg_processing_time:.0f} ms")
with col5:
    st.metric("Last Valid Detection", last_mould_id)


# 3. Charts
st.subheader("Analytics Overview")
chart_col1, chart_col2 = st.columns(2)

with chart_col1:
    # Bar Chart: Success vs Empty
    status_counts = df['status'].value_counts().reset_index()
    status_counts.columns = ['Status', 'Count']
    fig_status = px.bar(
        status_counts, 
        x='Status', 
        y='Count', 
        color='Status',
        color_discrete_map={"success": "#2ecc71", "empty": "#f39c12", "error": "#e74c3c"},
        title="Detection Distribution"
    )
    st.plotly_chart(fig_status, width="stretch")

with chart_col2:
    # Line Chart: Processing Time
    # Sort chronological for line chart
    df_chrono = df.sort_values("timestamp")
    fig_time = px.line(
        df_chrono,
        x='timestamp',
        y='processing_time_ms',
        color='status',
        color_discrete_map={"success": "#2ecc71", "empty": "#f39c12", "error": "#e74c3c"},
        title="Processing Time Trend (ms)",
        markers=True
    )
    st.plotly_chart(fig_time, width="stretch")

# 4. Recent Timeline/Logs
st.subheader("Recent Detections Timeline")
recent_df = df[['timestamp', 'camera_id', 'status', 'cope', 'drag', 'processing_time_ms']].head(20).copy()

# Format the drag object for clean display
def format_drag(d):
    if pd.isna(d) or d is None:
         return ""
    if isinstance(d, dict):
         main = d.get('main', '')
         sub = d.get('sub', '')
         return f"{main} ({sub})" if sub else str(main)
    return str(d)

recent_df['drag'] = recent_df['drag'].apply(format_drag)
recent_df['timestamp'] = pd.to_datetime(recent_df['timestamp']).dt.strftime('%H:%M:%S')
recent_df.columns = ['Time', 'Camera', 'Status', 'Cope', 'Drag', 'Latency (ms)']

st.dataframe(
    recent_df, 
    width="stretch",
    hide_index=True
)
