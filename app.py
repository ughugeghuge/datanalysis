import streamlit as st
import pandas as pd
import numpy as np
import re
from datetime import timedelta, datetime, time
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from pathlib import Path
import warnings
warnings.filterwarnings('ignore')

st.set_page_config(page_title="Boiler Analytics Platform", layout="wide", initial_sidebar_state="expanded")

# ==============================================================================
# UI/UX: PREMIUM APPLE-STYLE SIDEBAR NAVIGATION CSS (LEFT-ALIGNED & GAPLESS)
# ==============================================================================
st.markdown("""
<style>
/* Sidebar Background Polish */
[data-testid="stSidebar"] {
    background-color: #fbfbfd;
}

/* Radio Group Container */
[data-testid="stSidebar"] div[role="radiogroup"] {
    gap: 4px !important;
    width: 100%;
    display: flex;
    flex-direction: column;
}

/* Base Tab Styling - Uniform Width & Left Aligned */
[data-testid="stSidebar"] div[role="radiogroup"] label {
    padding: 12px 16px !important;
    border-radius: 8px !important; 
    margin: 0px !important;
    background-color: transparent !important;
    border: 1px solid transparent !important;
    transition: all 0.2s ease;
    cursor: pointer;
    width: 100% !important;
    display: flex !important;
    justify-content: flex-start !important; /* Forces left alignment */
    align-items: center !important;
}

/* Hover State */
[data-testid="stSidebar"] div[role="radiogroup"] label:hover {
    background-color: #e8e8ed !important;
}

/* Active State Styling - Refined Professional Blue */
[data-testid="stSidebar"] div[role="radiogroup"] label[data-checked="true"],
[data-testid="stSidebar"] div[role="radiogroup"] label:has(input:checked) {
    background-color: #0071e3 !important;
    border-color: #0071e3 !important;
    box-shadow: 0 2px 6px rgba(0, 113, 227, 0.3) !important;
    position: relative;
    overflow: hidden;
}

/* Subtle White Light-Sweep Animation */
[data-testid="stSidebar"] div[role="radiogroup"] label[data-checked="true"]::before,
[data-testid="stSidebar"] div[role="radiogroup"] label:has(input:checked)::before {
    content: '';
    position: absolute;
    top: 0; left: -100%;
    width: 50%; height: 100%;
    background: linear-gradient(90deg, transparent, rgba(255, 255, 255, 0.25), transparent);
    animation: light-sweep 3s infinite cubic-bezier(0.4, 0, 0.2, 1);
    z-index: 1;
    pointer-events: none;
}

@keyframes light-sweep {
    0% { left: -100%; }
    50% { left: 200%; }
    100% { left: 200%; }
}

/* Text Formatting */
[data-testid="stSidebar"] div[role="radiogroup"] label p {
    margin: 0 !important;
    font-size: 14.5px;
    color: #1d1d1f; 
    font-weight: 500;
    z-index: 2; 
    position: relative;
    text-align: left !important;
    width: 100%;
}

/* Active Text Color */
[data-testid="stSidebar"] div[role="radiogroup"] label[data-checked="true"] p,
[data-testid="stSidebar"] div[role="radiogroup"] label:has(input:checked) p {
    color: #ffffff !important;
    font-weight: 600;
}

/* FORCE HIDE THE CIRCULAR RADIO WIDGET */
[data-testid="stSidebar"] div[role="radiogroup"] label > div:first-child {
    display: none !important;
    width: 0px !important;
    margin: 0px !important;
    padding: 0px !important;
}

/* Align Markdown Container strictly to the left edge */
[data-testid="stSidebar"] div[role="radiogroup"] label div[data-testid="stMarkdownContainer"] {
    display: flex !important;
    justify-content: flex-start !important;
    width: 100% !important;
}

/* Push the 'Data Management' tab down to create space */
[data-testid="stSidebar"] div[role="radiogroup"] label:last-child {
    margin-top: 60px !important;
    border: 1px solid #d2d2d7 !important;
}
</style>
""", unsafe_allow_html=True)

# ==============================================================================
# PROFESSIONAL LIGHT THEME COLORS
# ==============================================================================
B_COLORS = {
    'Boiler 1': '#1f77b4',  
    'Boiler 2': '#2ca02c',  
    'Boiler 3': '#ff7f0e'   
}
SEC_COLOR = '#7f7f7f'       
SUM_LINE = '#d62728'        
SUM_FILL = 'rgba(214, 39, 40, 0.15)' 

# ==============================================================================
# DATA PROCESSING & CACHING
# ==============================================================================
def normalize_col(name):
    return re.sub(r'[^a-zA-Z0-9]', '', str(name)).lower()

def clean_and_normalize_sheet(raw_df):
    df = raw_df.copy()
    header_idx = 0
    for i in range(min(10, len(df))):
        row_vals = df.iloc[i].astype(str).str.lower()
        if any(row_vals.str.contains('date|time|timestamp', na=False)):
            header_idx = i
            break

    df.columns = df.iloc[header_idx]
    df = df.iloc[header_idx + 1:].reset_index(drop=True)
    
    ts_col = next((c for c in df.columns if any(k in str(c).lower() for k in ['time', 'date', 'timestamp'])), df.columns[0])
    df['timestamp'] = pd.to_datetime(df[ts_col], errors='coerce', dayfirst=True)
    df = df.dropna(subset=['timestamp']).sort_values('timestamp').reset_index(drop=True)
    
    if ts_col != 'timestamp':
        df = df.drop(columns=[ts_col], errors='ignore')

    new_cols = []
    for c in df.columns:
        if c == 'timestamp':
            new_cols.append(c)
            continue
        c_str = str(c)
        c_str = re.sub(r'[\(\[\{].*?[\)\]\}]', '', c_str)
        c_str = re.sub(r'(?i)\b(unknown|degc|deg c|tph|kg/cm2|kgcm2|mmwc|m3/hr|deg|c|kg|hr|%)\b', '', c_str)
        c_str = re.sub(r'[^a-zA-Z0-9]', ' ', c_str)
        c_str = re.sub(r'(?i)\bpress\b', 'Pressure', c_str)
        c_str = re.sub(r'(?i)\btemp\b', 'Temperature', c_str)
        c_str = ' '.join(c_str.split()).title()
        new_cols.append(c_str if c_str else 'Unnamed Parameter')

    seen = {}
    final_cols = []
    for c in new_cols:
        if c in seen:
            seen[c] += 1
            final_cols.append(f"{c} {seen[c]}")
        else:
            seen[c] = 0
            final_cols.append(c)
            
    df.columns = final_cols
    return df

@st.cache_data
def process_local_files(data_dir='./boiler_data'):
    cache = {}
    data_path = Path(data_dir)
    data_path.mkdir(parents=True, exist_ok=True)
    
    all_files = list(data_path.glob('*.*'))
    valid_files = [f for f in all_files if f.suffix in ['.xlsx', '.xls', '.csv']]
    
    if not valid_files:
        return None, None, []

    boiler_groups = {'Boiler 1': [], 'Boiler 2': [], 'Boiler 3': []}
    
    for f in valid_files:
        if '1' in f.name: boiler_groups['Boiler 1'].append(f)
        elif '2' in f.name: boiler_groups['Boiler 2'].append(f)
        elif '3' in f.name: boiler_groups['Boiler 3'].append(f)
        else: boiler_groups['Boiler 1'].append(f)

    for label, files in boiler_groups.items():
        if not files: continue
        df_list = []
        for target in files:
            try:
                if target.name.endswith(('.xlsx', '.xls')):
                    all_sheets = pd.read_excel(target, sheet_name=None, header=None)
                    for sheet_name, raw_sheet in all_sheets.items():
                        df = clean_and_normalize_sheet(raw_sheet)
                        if not df.empty: df_list.append(df)
                elif target.name.endswith('.csv'):
                    df = clean_and_normalize_sheet(pd.read_csv(target, header=None))
                    if not df.empty: df_list.append(df)
            except Exception as e:
                st.error(f"Error loading {target.name}: {e}")

        if df_list:
            merged_df = pd.concat(df_list, ignore_index=True)
            merged_df = merged_df.drop_duplicates(subset=['timestamp']).sort_values('timestamp').reset_index(drop=True)
            cache[label] = merged_df

    if not cache: return None, None, []
    
    all_params = sorted(list({str(c) for b in cache.values() for c in b.columns if c != 'timestamp'}))
    all_dates = pd.concat([b['timestamp'] for b in cache.values()])
    return cache, all_params, (all_dates.min().date(), all_dates.max().date())

@st.cache_data
def extract_events(data_cache, min_dur_minutes):
    events = []
    idx = 1
    def detect_steam_flow_col(columns):
        cols_no_ts = [c for c in columns if c != 'timestamp']
        for c in cols_no_ts:
            if any(k in normalize_col(c) for k in ['steamflow', 'flowmeter', 'boilerflow', 'flowtot']): return c
        for c in cols_no_ts:
            if any(k in normalize_col(c) for k in ['flow', 'steam', 'capacity']): return c
        return cols_no_ts[8] if len(cols_no_ts) >= 9 else cols_no_ts[-1]

    for b_name, b_df in data_cache.items():
        flow_col = detect_steam_flow_col(b_df.columns)
        flow_vals = pd.to_numeric(b_df[flow_col], errors='coerce').fillna(0)
        is_zero = flow_vals <= 0.05
        event_groups = b_df[is_zero].groupby((~is_zero).cumsum())
        
        for _, g in event_groups:
            st_time, et_time = g['timestamp'].iloc[0], g['timestamp'].iloc[-1]
            dur = (et_time - st_time).total_seconds() / 60.0
            if dur >= min_dur_minutes and dur <= 2880:
                events.append({
                    'boiler': b_name, 'event_num': idx,
                    'date': st_time.strftime('%Y-%m-%d'),
                    'label': f"Event {idx} ({st_time.strftime('%H:%M')} to {et_time.strftime('%H:%M')}) | {dur:.1f}m",
                    'start_time': st_time, 'end_time': et_time,
                    'duration_mins': dur,
                    'window_start': st_time - timedelta(hours=1),
                    'window_end': et_time + timedelta(hours=1)
                })
                idx += 1
    return pd.DataFrame(events)

def find_matching_param(columns, target_param):
    target_clean = normalize_col(target_param)
    for c in columns:
        if normalize_col(c) == target_clean: return c
    for c in columns:
        col_clean = normalize_col(c)
        if target_clean in col_clean or col_clean in target_clean: return c
    for kw in ['flow', 'steam', 'pressure', 'temperature', 'oxygen', 'level', 'feedwater']:
        if kw in target_clean:
            for c in columns:
                if kw in normalize_col(c): return c
    return None

def calculate_window_generation(cache, target_boilers, start_time, end_time, primary_param):
    totals = {}
    for b_name in target_boilers:
        if b_name not in cache: continue
        b_df = cache[b_name]
        m_param = find_matching_param(b_df.columns, primary_param)
        if m_param:
            e_df = b_df[(b_df['timestamp'] >= pd.to_datetime(start_time)) & (b_df['timestamp'] <= pd.to_datetime(end_time))].copy()
            if len(e_df) > 1:
                dt_hours = e_df['timestamp'].diff().dt.total_seconds() / 3600.0
                gen = (pd.to_numeric(e_df[m_param], errors='coerce') * dt_hours).sum()
                totals[b_name] = round(gen, 2)
            else:
                totals[b_name] = 0.0
        else:
            totals[b_name] = 0.0
    totals['Total Generation'] = sum(totals.values())
    return totals

def set_legend_bottom(fig):
    fig.update_layout(
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=-0.2,
            xanchor="center",
            x=0.5
        )
    )
    return fig

# ==============================================================================
# INITIALIZATION 
# ==============================================================================
cache_data_result = process_local_files('./boiler_data')
cache, all_params, dates_tuple = cache_data_result if cache_data_result[0] is not None else ({}, [], (datetime.now().date(), datetime.now().date()))
min_date, max_date = dates_tuple

default_flow_idx = 0
default_press_idx = 1
default_o2_idx = 0
if all_params:
    for i, p in enumerate(all_params):
        p_lower = p.lower()
        if p_lower == 'steam flow meter': default_flow_idx = i
        elif ('steam flow' in p_lower or 'flow meter' in p_lower) and all_params[default_flow_idx].lower() != 'steam flow meter': default_flow_idx = i
        if p_lower == 'boiler pressure': default_press_idx = i
        elif ('boiler pressure' in p_lower or 'steam pressure' in p_lower) and all_params[default_press_idx].lower() != 'boiler pressure': default_press_idx = i
        if 'oxygen' in p_lower or 'o2' in p_lower: default_o2_idx = i

# ==============================================================================
# SEAMLESS VERTICAL SIDEBAR NAVIGATION
# ==============================================================================
app_mode = st.sidebar.radio("Navigation", [
    "Boiler operation and Flow",
    "Loading pattern",
    "Steam flow vs oxygen variation",
    "System Cross-Analysis",
    "Parameter Correlation Matrix",
    "Data Management"
], label_visibility="collapsed")

# ==============================================================================
# DATA MANAGEMENT TAB
# ==============================================================================
if app_mode == "Data Management":
    st.title("Data Management")
    st.markdown("Upload new raw data files. Ensure you upload the correct file for the corresponding Boiler.")
    st.markdown("*(Any previously uploaded files for the selected boiler will be maintained alongside the new data).*")
    st.markdown("---")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.subheader("Boiler 1")
        b1_file = st.file_uploader("Upload Data for Boiler 1", accept_multiple_files=False, key="up_b1", label_visibility="collapsed")
    with col2:
        st.subheader("Boiler 2")
        b2_file = st.file_uploader("Upload Data for Boiler 2", accept_multiple_files=False, key="up_b2", label_visibility="collapsed")
    with col3:
        st.subheader("Boiler 3")
        b3_file = st.file_uploader("Upload Data for Boiler 3", accept_multiple_files=False, key="up_b3", label_visibility="collapsed")

    if st.button("Process & Save Active Uploads", type="primary"):
        data_dir = Path('./boiler_data')
        data_dir.mkdir(parents=True, exist_ok=True)
        files_saved = 0
        
        if b1_file:
            with open(data_dir / f"Boiler1_{b1_file.name}", "wb") as f: f.write(b1_file.getbuffer())
            files_saved += 1
        if b2_file:
            with open(data_dir / f"Boiler2_{b2_file.name}", "wb") as f: f.write(b2_file.getbuffer())
            files_saved += 1
        if b3_file:
            with open(data_dir / f"Boiler3_{b3_file.name}", "wb") as f: f.write(b3_file.getbuffer())
            files_saved += 1
            
        if files_saved > 0:
            st.success(f"Successfully processed and saved {files_saved} file(s).")
            st.cache_data.clear()
            st.rerun()
        else:
            st.warning("No files were selected for upload.")

elif not cache:
    st.warning("No valid data found. Please navigate to the 'Data Management' tab and upload your boiler files.")
    st.stop()

# ==============================================================================
# 1. BOILER OPERATION AND FLOW
# ==============================================================================
elif app_mode == "Boiler operation and Flow":
    st.title("Boiler Operation and Flow")
    
    with st.expander("Event Parameters", expanded=True):
        colA, colB = st.columns(2)
        sel_min_dur = colA.slider("Minimum Zero-Flow Duration (mins)", 0, 60, 2)
        target_boilers = colB.multiselect("Select Boiler(s) to Analyze", list(cache.keys()), default=list(cache.keys()), key="z_boilers")
        
        c1, c2 = st.columns(2)
        sel_param = c1.selectbox("Primary Parameter (Y1 / Flow Metric)", options=all_params, index=default_flow_idx, key="z_p1")
        sel_param2 = c2.selectbox("Secondary Parameter (Y2)", options=all_params, index=default_press_idx, key="z_p2")

    events_df = extract_events(cache, sel_min_dur)
    
    if events_df.empty or not target_boilers:
        st.warning("No zero-flow events match the specified criteria or no boilers selected.")
    else:
        filtered_events = events_df[events_df['boiler'].isin(target_boilers)]
        dates = sorted(filtered_events['date'].unique()) if not filtered_events.empty else []
        
        c_date, c_event = st.columns(2)
        sel_date = c_date.selectbox("Event Date", options=dates if dates else ["No Events"])
        
        date_events = filtered_events[filtered_events['date'] == sel_date] if sel_date != "No Events" else pd.DataFrame()
        event_opts = {f"{row['boiler']} - {row['label']}": idx for idx, row in date_events.iterrows()} if not date_events.empty else {"No matching events": None}
        sel_event_label = c_event.selectbox("Select Specific Time Window", options=list(event_opts.keys()))
        
        event_id = event_opts.get(sel_event_label)
        if event_id is not None:
            ev = events_df.loc[event_id]
            
            st.markdown("---")
            if 'flow' in sel_param.lower():
                totals = calculate_window_generation(cache, target_boilers, ev['start_time'], ev['end_time'], sel_param)
                cols = st.columns(len(totals) + 1)
                cols[0].metric("Event Duration", f"{ev['duration_mins']:.1f} min")
                for idx, (label, val) in enumerate(totals.items()):
                    cols[idx + 1].metric(f"{label} (Tons)", f"{val:.1f}")

            st.markdown(f"#### Primary Timeline: {sel_param}")
            fig1 = go.Figure()
            for b_name in target_boilers:
                if b_name not in cache: continue
                b_df = cache[b_name]
                m_param_found = find_matching_param(b_df.columns, sel_param)
                if not m_param_found: continue
                w_df = b_df[(b_df['timestamp'] >= ev['window_start']) & (b_df['timestamp'] <= ev['window_end'])]
                fig1.add_trace(go.Scatter(
                    x=w_df['timestamp'], y=pd.to_numeric(w_df[m_param_found], errors='coerce'),
                    mode='lines+markers', name=f"{b_name}", line=dict(color=B_COLORS.get(b_name), width=2), marker=dict(size=4)
                ))
            fig1.add_vrect(x0=ev['start_time'], x1=ev['end_time'], fillcolor="rgba(220, 38, 38, 0.15)", line_width=1, line_color="#dc2626")
            fig1.update_layout(title=f"Date: {sel_date}", template="plotly_white", hovermode="x unified", height=450, margin=dict(t=40, b=50))
            fig1 = set_legend_bottom(fig1)
            st.plotly_chart(fig1, use_container_width=True)

            st.markdown(f"#### Correlation Analysis: {sel_param} (Solid) vs {sel_param2} (Dotted)")
            for b_name in target_boilers:
                if b_name not in cache: continue
                b_df = cache[b_name]
                m_param1 = find_matching_param(b_df.columns, sel_param)
                m_param2 = find_matching_param(b_df.columns, sel_param2)
                w_df = b_df[(b_df['timestamp'] >= ev['window_start']) & (b_df['timestamp'] <= ev['window_end'])]
                
                fig_dual = make_subplots(specs=[[{"secondary_y": True}]])
                if m_param1 and not w_df.empty:
                    fig_dual.add_trace(go.Scatter(
                        x=w_df['timestamp'], y=pd.to_numeric(w_df[m_param1], errors='coerce'),
                        name=f"{sel_param}", line=dict(color=B_COLORS.get(b_name), width=2)
                    ), secondary_y=False)
                if m_param2 and not w_df.empty:
                    fig_dual.add_trace(go.Scatter(
                        x=w_df['timestamp'], y=pd.to_numeric(w_df[m_param2], errors='coerce'),
                        name=f"{sel_param2}", line=dict(color=SEC_COLOR, width=2, dash='dot')
                    ), secondary_y=True)
                fig_dual.add_vrect(x0=ev['start_time'], x1=ev['end_time'], fillcolor="rgba(220, 38, 38, 0.15)", line_width=0)
                fig_dual.update_layout(title=f"{b_name} Breakdown | Date: {sel_date}", template="plotly_white", hovermode="x unified", height=350, margin=dict(t=40, b=50))
                fig_dual = set_legend_bottom(fig_dual)
                st.plotly_chart(fig_dual, use_container_width=True)

            st.markdown(f"#### Aggregate Factory Sum ({sel_param})")
            sum_df = pd.DataFrame()
            for b_name in target_boilers:
                if b_name not in cache: continue
                b_df = cache[b_name]
                m_param_found = find_matching_param(b_df.columns, sel_param)
                if m_param_found:
                    w_df = b_df[(b_df['timestamp'] >= ev['window_start']) & (b_df['timestamp'] <= ev['window_end'])].copy()
                    w_df = w_df.set_index('timestamp')[m_param_found]
                    w_df = pd.to_numeric(w_df, errors='coerce').resample('1min').mean().interpolate(method='time')
                    sum_df[b_name] = w_df

            if not sum_df.empty:
                sum_df['Aggregate'] = sum_df.sum(axis=1)
                fig_sum = go.Figure()
                fig_sum.add_trace(go.Scatter(
                    x=sum_df.index, y=sum_df['Aggregate'], mode='lines', fill='tozeroy', name="Overall Sum",
                    line=dict(color=SUM_LINE, width=2), fillcolor=SUM_FILL
                ))
                fig_sum.add_vrect(x0=ev['start_time'], x1=ev['end_time'], fillcolor="rgba(220, 38, 38, 0.1)", line_width=1)
                fig_sum.update_layout(title=f"Date: {sel_date}", template="plotly_white", hovermode="x unified", height=350, margin=dict(t=40, b=50))
                fig_sum = set_legend_bottom(fig_sum)
                st.plotly_chart(fig_sum, use_container_width=True)

# ==============================================================================
# 2. LOADING PATTERN
# ==============================================================================
elif app_mode == "Loading pattern":
    st.title("Loading Pattern")
    
    with st.expander("Analysis Configuration", expanded=True):
        c1, c2, c3 = st.columns([1.5, 1, 1])
        target_boilers = c1.multiselect("Select Boiler(s)", list(cache.keys()), default=list(cache.keys()), key="s_boilers")
        sel_param = c2.selectbox("Primary Metric (Flow)", options=all_params, index=default_flow_idx, key="s_param")
        sel_param2 = c3.selectbox("Secondary Metric (Pressure)", options=all_params, index=default_press_idx, key="s_param2")

    st.markdown("### Daily & Shift Consumption Totalizer")
    target_date = st.date_input("Select Production Date", value=min_date, min_value=min_date, max_value=max_date)
    
    if target_date and target_boilers:
        shift_A_start = datetime.combine(target_date - timedelta(days=1), time(22, 0))
        shift_A_end = datetime.combine(target_date, time(6, 0))
        shift_B_start = datetime.combine(target_date, time(6, 0))
        shift_B_end = datetime.combine(target_date, time(14, 0))
        shift_C_start = datetime.combine(target_date, time(14, 0))
        shift_C_end = datetime.combine(target_date, time(22, 0))
        
        shift_A = calculate_window_generation(cache, target_boilers, shift_A_start, shift_A_end, sel_param)
        shift_B = calculate_window_generation(cache, target_boilers, shift_B_start, shift_B_end, sel_param)
        shift_C = calculate_window_generation(cache, target_boilers, shift_C_start, shift_C_end, sel_param)
        
        full_day = {k: shift_A.get(k, 0) + shift_B.get(k, 0) + shift_C.get(k, 0) for k in shift_A.keys()}
        shift_data = {
            "Shift A (10 PM - 6 AM)": shift_A,
            "Shift B (6 AM - 2 PM)": shift_B,
            "Shift C (2 PM - 10 PM)": shift_C,
            "Full Day Total": full_day
        }
        st.dataframe(pd.DataFrame.from_dict(shift_data, orient='index').style.format("{:.1f} Tons"), use_container_width=True)

    st.markdown("---")
    st.markdown("### Custom Timeline Explorer")
    
    colX, colY = st.columns(2)
    explore_date = colX.date_input("Select Date to Explore", value=min_date, min_value=min_date, max_value=max_date, key="exp_date")
    time_range = colY.slider("Select Time Range", value=(time(0, 0), time(23, 59)), format="HH:mm", key="exp_time")
    
    if explore_date and target_boilers:
        start_dt = datetime.combine(explore_date, time_range[0])
        end_dt = datetime.combine(explore_date, time_range[1])
        
        fig_exp = go.Figure()
        for b_name in target_boilers:
            if b_name not in cache: continue
            b_df = cache[b_name]
            m_param_found = find_matching_param(b_df.columns, sel_param)
            if not m_param_found: continue
            
            w_df = b_df[(b_df['timestamp'] >= start_dt) & (b_df['timestamp'] <= end_dt)]
            if not w_df.empty:
                fig_exp.add_trace(go.Scatter(
                    x=w_df['timestamp'], y=pd.to_numeric(w_df[m_param_found], errors='coerce'),
                    mode='lines', name=f"{b_name} ({m_param_found})", line=dict(color=B_COLORS.get(b_name), width=1.5)
                ))
        fig_exp.update_layout(title=f"Combined Timeline: {sel_param} | Date: {explore_date}", template="plotly_white", hovermode="x unified", height=450, margin=dict(t=40, b=50))
        fig_exp = set_legend_bottom(fig_exp)
        st.plotly_chart(fig_exp, use_container_width=True)

        st.markdown("---")
        st.markdown("### Steam Flow vs Boiler Pressure Analysis")
        for b_name in target_boilers:
            if b_name not in cache: continue
            b_df = cache[b_name]
            m_param1 = find_matching_param(b_df.columns, sel_param)
            m_param2 = find_matching_param(b_df.columns, sel_param2)
            
            w_df = b_df[(b_df['timestamp'] >= start_dt) & (b_df['timestamp'] <= end_dt)]
            if not w_df.empty:
                fig_dual = make_subplots(specs=[[{"secondary_y": True}]])
                if m_param1:
                    fig_dual.add_trace(go.Scatter(
                        x=w_df['timestamp'], y=pd.to_numeric(w_df[m_param1], errors='coerce'),
                        name=f"{m_param1}", line=dict(color=B_COLORS.get(b_name), width=2)
                    ), secondary_y=False)
                if m_param2:
                    fig_dual.add_trace(go.Scatter(
                        x=w_df['timestamp'], y=pd.to_numeric(w_df[m_param2], errors='coerce'),
                        name=f"{m_param2}", line=dict(color=SEC_COLOR, width=2, dash='dot')
                    ), secondary_y=True)
                
                fig_dual.update_layout(title=f"{b_name}: {m_param1} (Solid) vs {m_param2} (Dotted) | Date: {explore_date}", template="plotly_white", hovermode="x unified", height=350, margin=dict(t=40, b=50))
                fig_dual.update_yaxes(title_text=m_param1, secondary_y=False, color=B_COLORS.get(b_name))
                fig_dual.update_yaxes(title_text=m_param2, secondary_y=True, color=SEC_COLOR)
                fig_dual = set_legend_bottom(fig_dual)
                st.plotly_chart(fig_dual, use_container_width=True)

# ==============================================================================
# 3. STEAM FLOW VS OXYGEN VARIATION
# ==============================================================================
elif app_mode == "Steam flow vs oxygen variation":
    st.title("Steam flow vs oxygen variation")
    
    with st.expander("Analysis Configuration", expanded=True):
        col1, col2 = st.columns([1, 1.5])
        target_boilers = col1.multiselect("Select Boiler(s)", list(cache.keys()), default=list(cache.keys()), key="o2_boilers")
        preset_shift = col2.selectbox("Analysis Window", [
            "Custom Time (Single Day)", 
            "Custom Date Range", 
            "Shift A (22:00 - 06:00)", 
            "Shift B (06:00 - 14:00)", 
            "Shift C (14:00 - 22:00)", 
            "Full Day (00:00 - 23:59)"
        ])
        
        show_timeline = True
        if preset_shift == "Custom Date Range":
            d1, d2 = st.columns(2)
            start_d = d1.date_input("Start Date", value=min_date, min_value=min_date, max_value=max_date, key="o2_start_d")
            end_d = d2.date_input("End Date", value=max_date, min_value=min_date, max_value=max_date, key="o2_end_d")
            start_t = datetime.combine(start_d, time(0, 0))
            end_t = datetime.combine(end_d, time(23, 59))
            show_timeline = False 
        else:
            target_o2_date = st.date_input("Target Date", value=min_date, min_value=min_date, max_value=max_date, key="o2_date")
            if preset_shift == "Shift A (22:00 - 06:00)":
                start_t = datetime.combine(target_o2_date - timedelta(days=1), time(22, 0))
                end_t = datetime.combine(target_o2_date, time(6, 0))
            elif preset_shift == "Shift B (06:00 - 14:00)":
                start_t = datetime.combine(target_o2_date, time(6, 0))
                end_t = datetime.combine(target_o2_date, time(14, 0))
            elif preset_shift == "Shift C (14:00 - 22:00)":
                start_t = datetime.combine(target_o2_date, time(14, 0))
                end_t = datetime.combine(target_o2_date, time(22, 0))
            elif preset_shift == "Full Day (00:00 - 23:59)":
                start_t = datetime.combine(target_o2_date, time(0, 0))
                end_t = datetime.combine(target_o2_date, time(23, 59))
            else:
                custom_tr = st.slider("Custom Time Window", value=(time(0, 0), time(23, 59)), format="HH:mm", key="o2_time")
                start_t = datetime.combine(target_o2_date, custom_tr[0])
                end_t = datetime.combine(target_o2_date, custom_tr[1])

        col4, col5, col6 = st.columns([2, 2, 1])
        flow_col_sel = col4.selectbox("X-Axis (Flow Metric)", options=all_params, index=default_flow_idx, key="o2_x")
        o2_col_sel = col5.selectbox("Y-Axis (Oxygen Metric)", options=all_params, index=default_o2_idx, key="o2_y")
        op_threshold = col6.number_input("Active Boiler Threshold (Flow >)", value=1.0, step=0.5, help="Filters out shutdowns to reveal true operating stats.")
    
    if target_boilers:
        fig_scat = go.Figure()
        fig_dist_flow = go.Figure()
        fig_dist_o2 = go.Figure()
        fig_3d = go.Figure()
        
        stats_data = []
        line_charts = []
        pooled_flow = []
        pooled_o2 = []
        
        for b_name in target_boilers:
            if b_name in cache:
                b_df_o2 = cache[b_name]
                col_f = find_matching_param(b_df_o2.columns, flow_col_sel)
                col_o = find_matching_param(b_df_o2.columns, o2_col_sel)
                
                if col_f and col_o:
                    w_df_o2 = b_df_o2[(b_df_o2['timestamp'] >= start_t) & (b_df_o2['timestamp'] <= end_t)].copy()
                    w_df_o2['Flow_Num'] = pd.to_numeric(w_df_o2[col_f], errors='coerce')
                    w_df_o2['O2_Num'] = pd.to_numeric(w_df_o2[col_o], errors='coerce')
                    w_df_o2 = w_df_o2.dropna(subset=['Flow_Num', 'O2_Num'])
                    
                    if not w_df_o2.empty:
                        stats_df_o2 = w_df_o2[w_df_o2['Flow_Num'] >= op_threshold]
                        
                        if not stats_df_o2.empty:
                            stats_data.append({
                                "Boiler": b_name,
                                f"Min {flow_col_sel}": stats_df_o2['Flow_Num'].min(),
                                f"Avg {flow_col_sel}": stats_df_o2['Flow_Num'].mean(),
                                f"Max {flow_col_sel}": stats_df_o2['Flow_Num'].max(),
                                f"Min {o2_col_sel}": stats_df_o2['O2_Num'].min(),
                                f"Avg {o2_col_sel}": stats_df_o2['O2_Num'].mean(),
                                f"Max {o2_col_sel}": stats_df_o2['O2_Num'].max(),
                            })
                            
                            pooled_flow.extend(stats_df_o2['Flow_Num'].values)
                            pooled_o2.extend(stats_df_o2['O2_Num'].values)
                            
                            fig_dist_flow.add_trace(go.Histogram(
                                x=stats_df_o2['Flow_Num'], histnorm='probability density',
                                name=b_name, marker_color=B_COLORS.get(b_name), opacity=0.7
                            ))
                            fig_dist_o2.add_trace(go.Histogram(
                                x=stats_df_o2['O2_Num'], histnorm='probability density',
                                name=b_name, marker_color=B_COLORS.get(b_name), opacity=0.7
                            ))
                        else:
                            stats_data.append({
                                "Boiler": b_name,
                                f"Min {flow_col_sel}": 0.0, f"Avg {flow_col_sel}": 0.0, f"Max {flow_col_sel}": 0.0,
                                f"Min {o2_col_sel}": 0.0, f"Avg {o2_col_sel}": 0.0, f"Max {o2_col_sel}": 0.0,
                            })
                        
                        if show_timeline:
                            fig_line = make_subplots(specs=[[{"secondary_y": True}]])
                            fig_line.add_trace(go.Scatter(
                                x=w_df_o2['timestamp'], y=w_df_o2['Flow_Num'],
                                name=f"{flow_col_sel}", line=dict(color=B_COLORS.get(b_name), width=2)
                            ), secondary_y=False)
                            fig_line.add_trace(go.Scatter(
                                x=w_df_o2['timestamp'], y=w_df_o2['O2_Num'],
                                name=f"{o2_col_sel}", line=dict(color=SEC_COLOR, width=2, dash='dot')
                            ), secondary_y=True)
                            fig_line.update_layout(title=f"{b_name} Breakdown | Date: {start_t.date()}", template="plotly_white", hovermode="x unified", height=300, margin=dict(t=40, b=50))
                            fig_line = set_legend_bottom(fig_line)
                            line_charts.append(fig_line)
                        
                        fig_scat.add_trace(go.Scattergl(
                            x=stats_df_o2['Flow_Num'], y=stats_df_o2['O2_Num'], mode='markers',
                            name=b_name, marker=dict(color=B_COLORS.get(b_name), size=5, opacity=0.6),
                            text=stats_df_o2['timestamp'].dt.strftime('%Y-%m-%d %H:%M'), hoverinfo="text+x+y+name"
                        ))
        
        if stats_data:
            st.markdown("#### Period Statistics Summary (Active Operating Flow Only)")
            st.dataframe(pd.DataFrame(stats_data).set_index("Boiler").style.format("{:.2f}"), use_container_width=True)
            
            if show_timeline:
                st.markdown("#### Timeline Breakdowns")
                for fig in line_charts:
                    st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("💡 Timelines are intentionally hidden in 'Custom Date Range' to prevent browser lag. Scroll down for aggregated plots.")
            
            st.markdown("#### 2D Scatter Correlation")
            fig_scat.update_layout(title=f"Date: {start_t.date()}", xaxis_title=flow_col_sel, yaxis_title=o2_col_sel, template="plotly_white", height=450, margin=dict(t=40, b=50))
            fig_scat = set_legend_bottom(fig_scat)
            st.plotly_chart(fig_scat, use_container_width=True)
            
            st.markdown("#### 1D Parameter Variations (Probability Density)")
            d_col1, d_col2 = st.columns(2)
            fig_dist_flow.update_layout(barmode='overlay', title=f"{flow_col_sel} Distribution | Date: {start_t.date()}", template="plotly_white", height=350, margin=dict(t=40, b=50))
            fig_dist_flow = set_legend_bottom(fig_dist_flow)
            
            fig_dist_o2.update_layout(barmode='overlay', title=f"{o2_col_sel} Distribution | Date: {start_t.date()}", template="plotly_white", height=350, margin=dict(t=40, b=50))
            fig_dist_o2 = set_legend_bottom(fig_dist_o2)
            
            d_col1.plotly_chart(fig_dist_flow, use_container_width=True)
            d_col2.plotly_chart(fig_dist_o2, use_container_width=True)
            
            if pooled_flow and pooled_o2:
                st.markdown("#### 3D Bivariate Density Map (Flow vs Oxygen)")
                H, xedges, yedges = np.histogram2d(pooled_flow, pooled_o2, bins=30, density=True)
                fig_3d.add_trace(go.Surface(z=H.T, x=xedges[:-1], y=yedges[:-1], colorscale='Viridis', opacity=0.9))
                fig_3d.update_layout(
                    title=f"Date: {start_t.date()}",
                    scene=dict(xaxis_title="Steam Flow", yaxis_title="Oxygen", zaxis_title="Probability Density", camera=dict(eye=dict(x=1.5, y=-1.5, z=1.2))),
                    height=600, margin=dict(t=40, b=50)
                )
                st.plotly_chart(fig_3d, use_container_width=True, config={'scrollZoom': False})
        else:
            st.warning("No valid overlapping data points found.")

# ==============================================================================
# 4. SYSTEM CROSS-ANALYSIS (DYNAMIC)
# ==============================================================================
elif app_mode == "System Cross-Analysis":
    st.title("System Cross-Analysis")
    st.markdown("Select any two parameters across the boiler system to discover deep mechanical and operational correlations.")
    
    with st.expander("Analysis Configuration", expanded=True):
        col1, col2 = st.columns([1, 1.5])
        target_boilers = col1.multiselect("Select Boiler(s)", list(cache.keys()), default=[list(cache.keys())[0]], key="crs_boilers")
        preset_shift = col2.selectbox("Analysis Window", [
            "Full Day (00:00 - 23:59)", 
            "Shift A (22:00 - 06:00)", 
            "Shift B (06:00 - 14:00)", 
            "Shift C (14:00 - 22:00)"
        ], key="crs_preset")
        
        target_crs_date = st.date_input("Target Date", value=min_date, min_value=min_date, max_value=max_date, key="crs_date")
        
        if preset_shift == "Shift A (22:00 - 06:00)":
            start_t = datetime.combine(target_crs_date - timedelta(days=1), time(22, 0))
            end_t = datetime.combine(target_crs_date, time(6, 0))
        elif preset_shift == "Shift B (06:00 - 14:00)":
            start_t = datetime.combine(target_crs_date, time(6, 0))
            end_t = datetime.combine(target_crs_date, time(14, 0))
        elif preset_shift == "Shift C (14:00 - 22:00)":
            start_t = datetime.combine(target_crs_date, time(14, 0))
            end_t = datetime.combine(target_crs_date, time(22, 0))
        else:
            start_t = datetime.combine(target_crs_date, time(0, 0))
            end_t = datetime.combine(target_crs_date, time(23, 59))

        col3, col4 = st.columns(2)
        cross_p1 = col3.selectbox("Primary Metric (Y1)", options=all_params, index=default_flow_idx, key="crs_p1")
        cross_p2 = col4.selectbox("Secondary Metric (Y2)", options=all_params, index=default_press_idx, key="crs_p2")

    if not target_boilers:
        st.stop()

    for target_boiler in target_boilers:
        if target_boiler in cache:
            b_df = cache[target_boiler]
            w_df = b_df[(b_df['timestamp'] >= start_t) & (b_df['timestamp'] <= end_t)].copy()
            
            if not w_df.empty:
                col_y1 = find_matching_param(w_df.columns, cross_p1)
                col_y2 = find_matching_param(w_df.columns, cross_p2)
                
                if col_y1 and col_y2:
                    st.markdown(f"#### {target_boiler}: {col_y1} vs {col_y2}")
                    fig_eff = make_subplots(specs=[[{"secondary_y": True}]])
                    fig_eff.add_trace(go.Scatter(x=w_df['timestamp'], y=pd.to_numeric(w_df[col_y1], errors='coerce'), name=col_y1, line=dict(color=B_COLORS.get(target_boiler))), secondary_y=False)
                    fig_eff.add_trace(go.Scatter(x=w_df['timestamp'], y=pd.to_numeric(w_df[col_y2], errors='coerce'), name=col_y2, line=dict(color='#d62728', dash='dot')), secondary_y=True)
                    fig_eff.update_layout(title=f"Date: {start_t.date()}", template="plotly_white", hovermode="x unified", height=400, margin=dict(t=40, b=50))
                    fig_eff = set_legend_bottom(fig_eff)
                    st.plotly_chart(fig_eff, use_container_width=True)
                    
            st.markdown("---")

# ==============================================================================
# 5. PARAMETER CORRELATION MATRIX
# ==============================================================================
elif app_mode == "Parameter Correlation Matrix":
    st.title("Parameter Correlation Matrix")
    
    with st.expander("Analysis Configuration", expanded=True):
        col1, col2 = st.columns([1, 1.5])
        target_boilers = col1.multiselect("Select Boiler(s)", list(cache.keys()), default=[list(cache.keys())[0]], key="corr_boilers")
        preset_shift = col2.selectbox("Analysis Window", [
            "Full Day (00:00 - 23:59)", 
            "Shift A (22:00 - 06:00)", 
            "Shift B (06:00 - 14:00)", 
            "Shift C (14:00 - 22:00)"
        ], key="corr_preset")
        
        target_corr_date = st.date_input("Target Date", value=min_date, min_value=min_date, max_value=max_date, key="corr_date")
        
        if preset_shift == "Shift A (22:00 - 06:00)":
            start_t = datetime.combine(target_corr_date - timedelta(days=1), time(22, 0))
            end_t = datetime.combine(target_corr_date, time(6, 0))
        elif preset_shift == "Shift B (06:00 - 14:00)":
            start_t = datetime.combine(target_corr_date, time(6, 0))
            end_t = datetime.combine(target_corr_date, time(14, 0))
        elif preset_shift == "Shift C (14:00 - 22:00)":
            start_t = datetime.combine(target_corr_date, time(14, 0))
            end_t = datetime.combine(target_corr_date, time(22, 0))
        else:
            start_t = datetime.combine(target_corr_date, time(0, 0))
            end_t = datetime.combine(target_corr_date, time(23, 59))

    target_heatmap_keywords = [
        'boiler pressure', 'steam flow meter', 'boiler capacity', 'furnace pressure',
        'oxygen', 'eco inlet temp', 'deaerator level', 'deaerator temperature',
        'fuel feeding screw', 'rotary feeder screw', 'eco outlet temp',
        'pa flash temp', 'fw eco ol temperature'
    ]

    for target_boiler in target_boilers:
        st.markdown("---")
        st.markdown(f"#### Correlation Heatmap: {target_boiler}")
        if target_boiler in cache:
            b_df = cache[target_boiler]
            
            cols_to_keep = []
            for kw in target_heatmap_keywords:
                matched_col = find_matching_param(b_df.columns, kw)
                if matched_col and matched_col not in cols_to_keep:
                    cols_to_keep.append(matched_col)
            
            w_df = b_df[(b_df['timestamp'] >= start_t) & (b_df['timestamp'] <= end_t)].copy()
            
            if not w_df.empty and cols_to_keep:
                w_df_numeric = w_df[cols_to_keep].apply(pd.to_numeric, errors='coerce')
                w_df_numeric = w_df_numeric.dropna(axis=1, how='all')
                
                if not w_df_numeric.empty and w_df_numeric.shape[1] > 1:
                    corr_matrix = w_df_numeric.corr(numeric_only=True)
                    
                    fig_corr = go.Figure(data=go.Heatmap(
                        z=corr_matrix.values,
                        x=corr_matrix.columns,
                        y=corr_matrix.index,
                        colorscale='RdBu_r',
                        zmin=-1, zmax=1,
                        hovertemplate="Variable X: %{x}<br>Variable Y: %{y}<br>Pearson Correlation: %{z:.2f}<extra></extra>"
                    ))
                    
                    fig_corr.update_layout(
                        title=f"Date: {start_t.date()}",
                        template="plotly_white",
                        height=600,
                        margin=dict(t=40, b=150, l=150),
                        xaxis=dict(tickangle=45)
                    )
                    
                    st.plotly_chart(fig_corr, use_container_width=True)
                else:
                    st.warning(f"Not enough valid numeric data in {target_boiler} for the selected parameters to map correlations.")
            else:
                st.warning(f"No targeted parameters found or no data available for {target_boiler} during this shift.")
