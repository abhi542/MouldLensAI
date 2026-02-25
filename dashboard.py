import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import os
import requests
import time
from config import settings

st.set_page_config(page_title="MouldLensAI Monitor", page_icon="⚙️", layout="wide")

def fetch_recent_logs(hours=24, start_date=None, end_date=None):
    try:
        url = f"http://127.0.0.1:8000/api/metrics/recent?hours={hours}"
        if start_date and end_date:
            url += f"&start_date={start_date}&end_date={end_date}"
            
        response = requests.get(url)
        if response.status_code == 200:
            return response.json()
        else:
            st.error(f"Failed to fetch metrics: {response.text}")
            return []
    except requests.exceptions.ConnectionError:
        st.error("Cannot connect to API. Is FastAPI running on port 8000?")
        return []

# Fetch Data
st.title("🏭 MouldLensAI Telemetry")
st.markdown("Real-time monitoring and analytics for the Cope & Drag extraction cameras.")

# Create tabs
tab1, tab2 = st.tabs(["📊 Analytics Dashboard", " Upload/Capture Image"])

with tab1:
    st.subheader("Filter Telemetry")
    col_d1, col_d2 = st.columns([1, 2])
    
    with col_d1:
        date_range = st.date_input(
            "Select Date Range",
            value=(datetime.utcnow().date() - timedelta(days=1), datetime.utcnow().date()),
            format="DD/MM/YYYY"
        )
        
    start_date_str = None
    end_date_str = None
    if isinstance(date_range, tuple) and len(date_range) == 2:
        start_date_str = date_range[0].isoformat()
        end_date_str = date_range[1].isoformat()

    with st.spinner("Fetching telemetry..."):
        if start_date_str and end_date_str:
            raw_logs = fetch_recent_logs(start_date=start_date_str, end_date=end_date_str)
        else:
            raw_logs = fetch_recent_logs()

    if not raw_logs:
        st.info("No logs found for the last 24 hours.")
    else:
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

        if 'is_human_corrected' not in df.columns:
            df['is_human_corrected'] = False
        df['is_human_corrected'] = df['is_human_corrected'].fillna(False)

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
        cope_val = "N/A"
        drag_val = "N/A"
        if not last_valid.empty:
            mould = last_valid.iloc[0]
            cope = mould.get('cope', 'Unknown')
            drag = mould.get('drag', {})
            drag_main = drag.get('main', 'Unknown') if isinstance(drag, dict) else 'Unknown'
            drag_sub = drag.get('sub', '') if isinstance(drag, dict) else ''
            
            cope_val = str(cope)
            if pd.isna(drag_sub) or not drag_sub:
                drag_val = str(drag_main)
            else:
                drag_val = f"{drag_main} ({drag_sub})"

        with col1:
            st.metric("Total Captures (24h)", f"{total_captures:,}")
        with col2:
            st.metric("Success Rate", f"{success_rate:.1f}%")
        with col3:
            st.metric("Empty Frames", f"{empty_count:,}")
        with col4:
            st.metric("Avg Processing Time", f"{avg_processing_time:.0f} ms")
        with col5:
            if cope_val == "N/A":
                st.metric("Last Valid Detection", "N/A")
            else:
                st.caption("Last Valid Detection")
                st.markdown(f"**C:** {cope_val}<br>**D:** {drag_val}", unsafe_allow_html=True)

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
        
        # Search Filters
        filter_col1, filter_col2 = st.columns(2)
        with filter_col1:
            search_cope = st.text_input("🔍 Search Cope Value", "")
        with filter_col2:
            search_drag = st.text_input("🔍 Search Drag Value", "")
            
        filtered_df = df[['timestamp', 'camera_id', 'status', 'cope', 'drag', 'processing_time_ms', 'is_human_corrected']].copy()
        
        # Format the drag object for clean display/searching
        def format_drag(d):
            if pd.isna(d) or d is None:
                 return ""
            if isinstance(d, dict):
                 main = d.get('main', '')
                 sub = d.get('sub', '')
                 return f"{main} ({sub})" if sub else str(main)
            return str(d)
            
        filtered_df['drag_str'] = filtered_df['drag'].apply(format_drag)
        
        # Apply Search Filtering
        if search_cope:
            filtered_df = filtered_df[filtered_df['cope'].astype(str).str.contains(search_cope, case=False, na=False)]
        if search_drag:
            filtered_df = filtered_df[filtered_df['drag_str'].astype(str).str.contains(search_drag, case=False, na=False)]
            
        recent_df = filtered_df.head(5000).copy()
        recent_df['timestamp'] = pd.to_datetime(recent_df['timestamp']).dt.strftime('%d %m %Y %H:%M:%S')
        
        # Highlight Operator Edits
        recent_df['is_human_corrected'] = recent_df['is_human_corrected'].apply(lambda x: "Yes" if x else "No")
        
        # Re-arrange final columns
        recent_df = recent_df[['timestamp', 'camera_id', 'status', 'cope', 'drag_str', 'processing_time_ms', 'is_human_corrected']]
        recent_df.columns = ['Time', 'Camera', 'Status', 'Cope', 'Drag', 'Latency (ms)', 'Edited by Operator']

        # CSV Export Button
        csv_data = recent_df.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="Export to CSV",
            data=csv_data,
            file_name=f"mould_telemetry_{datetime.now().strftime('%Y%m%d')}.csv",
            mime="text/csv"
        )

        st.dataframe(
            recent_df, 
            width="stretch",
            hide_index=True
        )

with tab2:
    st.subheader("Upload an Image for Extraction")
    
    uploaded_file = st.file_uploader("Choose a mould image to analyze", type=["jpg", "jpeg", "png", "webp"])
    
    if "current_result" not in st.session_state:
        st.session_state.current_result = None
    if "last_upload_duration" not in st.session_state:
        st.session_state.last_upload_duration = 0
    
    if uploaded_file is not None:
        col_img, col_res = st.columns(2)
        
        with col_img:
            st.image(uploaded_file, caption="Uploaded Image", use_container_width=True)
            
        with col_res:
            if st.button("Process Image", type="primary"):
                with st.spinner("Analyzing with Vision LLM..."):
                    try:
                        uploaded_file.seek(0)
                        files = {"file": (uploaded_file.name, uploaded_file.getvalue(), uploaded_file.type)}
                        data = {"camera_id": "factory_cam_01"}
                        
                        start_time = time.time()
                        response = requests.post("http://127.0.0.1:8000/api/upload", files=files, data=data)
                        st.session_state.last_upload_duration = round((time.time() - start_time) * 1000, 2)
                        
                        if response.status_code == 200:
                            st.session_state.current_result = response.json()
                        else:
                            st.error(f"API Error {response.status_code}: {response.text}")
                    except requests.exceptions.ConnectionError:
                        st.error("Failed to connect to the backend. Is the FastAPI server running on port 8000?")
                    except Exception as e:
                        st.error(f"An unexpected error occurred: {str(e)}")
            
            # Display cached result block
            result = st.session_state.current_result
            if result:
                status = result.get("status")
                reading_id = result.get("id")
                
                if status == "success":
                    st.success(f"**Automated Capture Saved!** (Analyzed in {st.session_state.last_upload_duration}ms)")
                    
                    st.markdown("### 🛠 Override Extracted Values")
                    st.info("The values below have already been saved to the remote database automatically. If they are incorrect, you can manually type over them to patch the database record.")
                    
                    # Ensure safe fallback dictionary extraction
                    cope_val = result.get('cope', '')
                    if cope_val is None: cope_val = ''
                    
                    drag_obj = result.get('drag', {})
                    if not isinstance(drag_obj, dict): drag_obj = {}
                    
                    drag_main = drag_obj.get('main', '')
                    if drag_main is None: drag_main = ''
                    
                    drag_sub = drag_obj.get('sub', '')
                    if drag_sub is None: drag_sub = ''
                    
                    with st.form(f"override_form_{reading_id}"):
                        new_cope = st.text_input("COPE", value=str(cope_val))
                        new_main = st.text_input("DRAG MAIN", value=str(drag_main))
                        new_sub = st.text_input("DRAG SUB (Bracket)", value=str(drag_sub))
                        
                        submitted = st.form_submit_button("Save Correction to Database")
                        
                        if submitted:
                            with st.spinner("Patching remote database..."):
                                put_payload = {
                                    "cope": new_cope,
                                    "drag": {
                                        "main": new_main,
                                        "sub": new_sub if new_sub else None
                                    }
                                }
                                try:
                                    put_res = requests.put(f"http://127.0.0.1:8000/api/metrics/update/{reading_id}", json=put_payload)
                                    if put_res.status_code == 200:
                                        st.success("Override saved successfully! Changes are live on the Telemetry tab.")
                                        
                                        # Update the cached session state so UI reflects the hardcoded patched values
                                        st.session_state.current_result['cope'] = new_cope
                                        st.session_state.current_result['drag']['main'] = new_main
                                        st.session_state.current_result['drag']['sub'] = new_sub if new_sub else None
                                        st.session_state.current_result['is_human_corrected'] = True
                                    else:
                                        st.error(f"Failed to update dataset: {put_res.text}")
                                except Exception as e:
                                    st.error(f"Failed to send override request: {str(e)}")

                    # st.caption("Raw Extracted JSON Output:")
                    # st.json(result)
                
                elif status == "empty":
                    st.warning(f"**Empty Read** - {result.get('message')}")
                    st.info("The automated system accurately determined there were no valid digits natively. (Saved as Error)")
                    st.json(result)
                else:
                    st.error(f"**Error** - {result.get('message')}")
