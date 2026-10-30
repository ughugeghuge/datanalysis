import streamlit as st
import pandas as pd
import numpy as np
import re
from datetime import timedelta, datetime, time
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import io
from pathlib import Path

st.set_page_config(page_title="Boiler Analytics Platform", layout="wide", initial_sidebar_state="expanded")

# ==============================================================================
# PROFESSIONAL LIGHT THEME COLORS
# ==============================================================================
B_COLORS = {
    'Boiler 1': '#1f77b4',  # Professional Blue
    'Boiler 2': '#2ca02c',  # Forest Green
    'Boiler 3': '#ff7f0e'   # Deep Orange
}
SEC_COLOR = '#7f7f7f'       # Slate Grey
SUM_LINE = '#d62728'        # Brick Red
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
    min_date = all_dates.min().date()
    max_date = all_dates.max().date()
    
    return cache, all_params, (min_date, max_date)

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

def calculate_window_generation(cache, start_time, end_time, primary_param):
    totals = {}
    for b_name, b_df in cache.items():
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
    totals['Total'] = sum(totals.values())
    return totals

# ==============================================================================
# STREAMLIT UI - MAIN LAYOUT
# ==============================================================================
st.title("Advanced Boiler Analytics Platform")

cache_data_result = process_local_files('./boiler_data')
if cache_data_result[0] is None:
    st.info("Awaiting data. Place Excel/CSV files into the './boiler_data' directory.")
    st.stop()
    
cache, all_params, (min_date, max_date) = cache_data_result

st.sidebar.markdown("### Global Parameters")

# Robust default selection logic
default_flow_idx = 0
default_press_idx = 1
for i, p in enumerate(all_params):
    p_lower = p.lower()
    if 'steam flow' in p_lower or 'flow meter' in p_lower:
        default_flow_idx = i
    if 'boiler pressure' in p_lower or 'steam pressure' in p_lower:
        default_press_idx = i

sel_param = st.sidebar.selectbox("Primary Parameter (Y1 / Flow Metric)", options=all_params, index=default_flow_idx)
sel_param2 = st.sidebar.selectbox("Secondary Parameter (Y2)", options=all_params, index=default_press_idx)
sel_view = st.sidebar.radio("View Mode", options=["Aligned Multi-Boiler", "Single Boiler Only"])

tab1, tab2, tab3 = st.tabs(["Zero-Flow Event Analytics", "Shift & Daily Totalizer", "Custom Day Explorer"])

# ==============================================================================
# TAB 1: ZERO-FLOW EVENT ANALYTICS
# ==============================================================================
with tab1:
    st.markdown("### Event Detection & Analysis")
    
    colA, colB, colC = st.columns(3)
    sel_min_dur = colA.slider("Minimum Zero-Flow Duration (mins)", 0, 60, 2)
    sel_boiler = colB.selectbox("Reference Boiler", options=list(cache.keys()))
    
    events_df = extract_events(cache, sel_min_dur)
    
    if events_df.empty:
        st.warning("No zero-flow events match the specified duration criteria.")
    else:
        filtered_events = events_df[events_df['boiler'] == sel_boiler]
        dates = sorted(filtered_events['date'].unique()) if not filtered_events.empty else []
        sel_date = colC.selectbox("Event Date", options=dates if dates else ["No Events"])
        
        date_events = filtered_events[filtered_events['date'] == sel_date] if sel_date != "No Events" else pd.DataFrame()
        event_opts = {row['label']: idx for idx, row in date_events.iterrows()} if not date_events.empty else {"No matching events": None}
        sel_event_label = st.selectbox("Select Specific Time Window", options=list(event_opts.keys()))
        
        event_id = event_opts.get(sel_event_label)
        if event_id is not None:
            ev = events_df.loc[event_id]
            boilers_to_plot = [ev['boiler']] if sel_view == "Single Boiler Only" else list(cache.keys())
            
            st.markdown("---")
            if 'flow' in sel_param.lower():
                totals = calculate_window_generation(cache, ev['start_time'], ev['end_time'], sel_param)
                m1, m2, m3, m4, m5 = st.columns(5)
                m1.metric("Event Duration", f"{ev['duration_mins']:.1f} min")
                m2.metric("Overall Lost/Gen (Tons)", f"{totals['Total']:.1f}")
                m3.metric("B1 Generation (Tons)", f"{totals.get('Boiler 1', 0):.1f}")
                m4.metric("B2 Generation (Tons)", f"{totals.get('Boiler 2', 0):.1f}")
                m5.metric("B3 Generation (Tons)", f"{totals.get('Boiler 3', 0):.1f}")

            # 1. Primary Timeline
            st.markdown(f"#### Primary Timeline: {sel_param}")
            fig1 = go.Figure()
            for b_name in boilers_to_plot:
                if b_name not in cache: continue
                b_df = cache[b_name]
                m_param = find_matching_param(b_df.columns, sel_param)
                if not m_param: continue
                w_df = b_df[(b_df['timestamp'] >= ev['window_start']) & (b_df['timestamp'] <= ev['window_end'])]
                fig1.add_trace(go.Scatter(
                    x=w_df['timestamp'], y=pd.to_numeric(w_df[m_param], errors='coerce'),
                    mode='lines+markers', name=f"{b_name}", line=dict(color=B_COLORS.get(b_name), width=2), marker=dict(size=4)
                ))
            fig1.add_vrect(x0=ev['start_time'], x1=ev['end_time'], fillcolor="rgba(220, 38, 38, 0.15)", line_width=1, line_color="#dc2626")
            fig1.update_layout(template="plotly_white", hovermode="x unified", height=400, margin=dict(t=10, b=10))
            st.plotly_chart(fig1, use_container_width=True)

            # 2. Dual Axis Full Width
            st.markdown(f"#### Correlation Analysis: {sel_param} (Solid) vs {sel_param2} (Dotted)")
            for b_name in boilers_to_plot:
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
                fig_dual.update_layout(title=f"{b_name} Breakdown", template="plotly_white", hovermode="x unified", height=300, margin=dict(t=40, b=10))
                st.plotly_chart(fig_dual, use_container_width=True)

            # 3. Overall Sum
            st.markdown(f"#### Aggregate Factory Sum ({sel_param})")
            sum_df = pd.DataFrame()
            for b_name in boilers_to_plot:
                if b_name not in cache: continue
                b_df = cache[b_name]
                m_param = find_matching_param(b_df.columns, sel_param)
                if m_param:
                    w_df = b_df[(b_df['timestamp'] >= ev['window_start']) & (b_df['timestamp'] <= ev['window_end'])].copy()
                    w_df = w_df.set_index('timestamp')[m_param]
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
                fig_sum.update_layout(template="plotly_white", hovermode="x unified", height=350, margin=dict(t=10, b=10))
                st.plotly_chart(fig_sum, use_container_width=True)

# ==============================================================================
# TAB 2: SHIFT & DAILY TOTALIZER
# ==============================================================================
with tab2:
    st.markdown("### Daily & Shift Consumption")
    st.info("Calculates total generated volume (Tons) during standard shifts based on the area under the curve of the selected Flow Metric.")
    
    target_date = st.date_input("Select Production Date", value=min_date, min_value=min_date, max_value=max_date)
    
    if target_date:
        shift_A_start = datetime.combine(target_date - timedelta(days=1), time(22, 0))
        shift_A_end = datetime.combine(target_date, time(6, 0))
        shift_B_start = datetime.combine(target_date, time(6, 0))
        shift_B_end = datetime.combine(target_date, time(14, 0))
        shift_C_start = datetime.combine(target_date, time(14, 0))
        shift_C_end = datetime.combine(target_date, time(22, 0))
        
        shift_A = calculate_window_generation(cache, shift_A_start, shift_A_end, sel_param)
        shift_B = calculate_window_generation(cache, shift_B_start, shift_B_end, sel_param)
        shift_C = calculate_window_generation(cache, shift_C_start, shift_C_end, sel_param)
        
        full_day = {k: shift_A.get(k, 0) + shift_B.get(k, 0) + shift_C.get(k, 0) for k in shift_A.keys()}
        
        shift_data = {
            "Shift A (10 PM - 6 AM)": shift_A,
            "Shift B (6 AM - 2 PM)": shift_B,
            "Shift C (2 PM - 10 PM)": shift_C,
            "Full Day Total": full_day
        }
        
        shift_df = pd.DataFrame.from_dict(shift_data, orient='index')
        st.dataframe(shift_df.style.format("{:.1f} Tons"), use_container_width=True)

# ==============================================================================
# TAB 3: CUSTOM DAY EXPLORER
# ==============================================================================
with tab3:
    st.markdown("### Custom Timeline Explorer")
    
    colX, colY = st.columns(2)
    explore_date = colX.date_input("Select Date to Explore", value=min_date, min_value=min_date, max_value=max_date, key="exp_date")
    time_range = colY.slider("Select Time Range", value=(time(0, 0), time(23, 59)), format="HH:mm")
    
    if explore_date:
        start_dt = datetime.combine(explore_date, time_range[0])
        end_dt = datetime.combine(explore_date, time_range[1])
        
        boilers_to_plot_exp = [sel_boiler] if sel_view == "Single Boiler Only" else list(cache.keys())
        
        fig_exp = go.Figure()
        for b_name in boilers_to_plot_exp:
            if b_name not in cache: continue
            b_df = cache[b_name]
            m_param = find_matching_param(b_df.columns, sel_param)
            if not m_param: continue
            
            w_df = b_df[(b_df['timestamp'] >= start_dt) & (b_df['timestamp'] <= end_dt)]
            if not w_df.empty:
                fig_exp.add_trace(go.Scatter(
                    x=w_df['timestamp'], y=pd.to_numeric(w_df[m_param], errors='coerce'),
                    mode='lines', name=f"{b_name} ({m_param})", line=dict(color=B_COLORS.get(b_name), width=1.5)
                ))
                
        fig_exp.update_layout(title=f"Custom Timeline: {sel_param}", template="plotly_white", hovermode="x unified", height=550)
        st.plotly_chart(fig_exp, use_container_width=True)