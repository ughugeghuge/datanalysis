import streamlit as st
import pandas as pd
import numpy as np
import re
from datetime import timedelta, datetime, time
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from pathlib import Path
from collections import defaultdict
import warnings
warnings.filterwarnings('ignore')

st.set_page_config(page_title="Boiler Analytics Platform", layout="wide", initial_sidebar_state="expanded")

# ==============================================================================
# UI/UX: PREMIUM APPLE-STYLE SIDEBAR NAVIGATION CSS
# ==============================================================================
st.markdown("""
<style>
[data-testid="stSidebar"] { background-color: #fbfbfd; }
[data-testid="stSidebar"] div[role="radiogroup"] { gap: 0px !important; display: flex !important; flex-direction: column !important; width: 100% !important; padding: 0px !important; }
[data-testid="stSidebar"] div[role="radiogroup"] > div { width: 100% !important; margin: 0px !important; padding: 0px !important; }
[data-testid="stSidebar"] div[role="radiogroup"] label { width: 100% !important; padding: 14px 16px !important; margin: 0px !important; border-radius: 0px !important; background-color: transparent !important; border: none !important; cursor: pointer; display: flex !important; align-items: center !important; justify-content: flex-start !important; transition: background-color 0.2s ease; }
[data-testid="stSidebar"] div[role="radiogroup"] > div:first-child label { border-top-left-radius: 8px !important; border-top-right-radius: 8px !important; }
[data-testid="stSidebar"] div[role="radiogroup"] > div:nth-last-child(2) label { border-bottom-left-radius: 8px !important; border-bottom-right-radius: 8px !important; }
[data-testid="stSidebar"] div[role="radiogroup"] label > div:first-child, [data-testid="stSidebar"] div[role="radiogroup"] label div[data-baseweb="radio"] { display: none !important; width: 0px !important; height: 0px !important; margin: 0px !important; padding: 0px !important; opacity: 0 !important; visibility: hidden !important; }
[data-testid="stSidebar"] div[role="radiogroup"] label div[data-testid="stMarkdownContainer"] { display: flex !important; width: 100% !important; justify-content: flex-start !important; }
[data-testid="stSidebar"] div[role="radiogroup"] label p { margin: 0 !important; font-size: 14.5px !important; color: #1d1d1f !important; font-weight: 500 !important; text-align: left !important; width: 100% !important; position: relative; z-index: 2; }
[data-testid="stSidebar"] div[role="radiogroup"] label:hover { background-color: #f0f0f5 !important; }
[data-testid="stSidebar"] div[role="radiogroup"] label[data-checked="true"], [data-testid="stSidebar"] div[role="radiogroup"] label:has(input:checked) { background-color: #0071e3 !important; position: relative; overflow: hidden; }
[data-testid="stSidebar"] div[role="radiogroup"] label[data-checked="true"] p, [data-testid="stSidebar"] div[role="radiogroup"] label:has(input:checked) p { color: #ffffff !important; font-weight: 600 !important; letter-spacing: 0.2px; }
[data-testid="stSidebar"] div[role="radiogroup"] label[data-checked="true"]::before, [data-testid="stSidebar"] div[role="radiogroup"] label:has(input:checked)::before { content: ''; position: absolute; top: 0; left: -100%; width: 50%; height: 100%; background: linear-gradient(90deg, transparent, rgba(255, 255, 255, 0.3), transparent); animation: light-sweep 3s infinite cubic-bezier(0.4, 0, 0.2, 1); z-index: 1; pointer-events: none; }
@keyframes light-sweep { 0% { left: -100%; } 50% { left: 200%; } 100% { left: 200%; } }
[data-testid="stSidebar"] div[role="radiogroup"] > div:last-child { margin-top: 60px !important; }
[data-testid="stSidebar"] div[role="radiogroup"] > div:last-child label { border-radius: 8px !important; border: 1px solid #d2d2d7 !important; background-color: #f5f5f7 !important; }
[data-testid="stSidebar"] div[role="radiogroup"] > div:last-child label:hover { background-color: #e8e8ed !important; }
[data-testid="stSidebar"] div[role="radiogroup"] > div:last-child label[data-checked="true"], [data-testid="stSidebar"] div[role="radiogroup"] > div:last-child label:has(input:checked) { background-color: #0071e3 !important; border: 1px solid #0071e3 !important; }
</style>
""", unsafe_allow_html=True)

# ==============================================================================
# PROFESSIONAL LIGHT THEME COLORS
# ==============================================================================
B_COLORS = {'Boiler 1': '#1f77b4', 'Boiler 2': '#2ca02c', 'Boiler 3': '#ff7f0e'}
MULTI_COLORS = ['#1f77b4', '#d62728', '#2ca02c', '#ff7f0e', '#9467bd', '#8c564b', '#e377c2', '#7f7f7f', '#bcbd22', '#17becf']
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
    
    if not valid_files: return None, None, []
    
    boiler_groups = {'Boiler 1': [], 'Boiler 2': [], 'Boiler 3': []}
    for f in valid_files:
        # Prevent the Audit/Production file from being misclassified as a boiler log
        f_lower = f.name.lower()
        if 'audit' in f_lower or 'fuel' in f_lower or 'production' in f_lower:
            continue
            
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
                    try:
                        all_sheets = pd.read_excel(target, sheet_name=None, header=None)
                        for sheet_name, raw_sheet in all_sheets.items():
                            df = clean_and_normalize_sheet(raw_sheet)
                            if not df.empty: df_list.append(df)
                    except Exception as e:
                        if "zip" in str(e).lower() or "magic" in str(e).lower():
                            df = clean_and_normalize_sheet(pd.read_csv(target, header=None))
                            if not df.empty: df_list.append(df)
                elif target.name.endswith('.csv'):
                    df = clean_and_normalize_sheet(pd.read_csv(target, header=None))
                    if not df.empty: df_list.append(df)
            except Exception:
                pass
                
        if df_list:
            merged_df = pd.concat(df_list, ignore_index=True)
            merged_df = merged_df.drop_duplicates(subset=['timestamp']).sort_values('timestamp').reset_index(drop=True)
            cache[label] = merged_df
            
    if not cache: return None, None, []
    all_params = sorted(list({str(c) for b in cache.values() for c in b.columns if c != 'timestamp'}))
    all_dates = pd.concat([b['timestamp'] for b in cache.values()])
    return cache, all_params, (all_dates.min().date(), all_dates.max().date())

@st.cache_data
def load_audit_data(data_dir='./boiler_data'):
    data_path = Path(data_dir)
    valid_files = list(data_path.glob('*.xlsx')) + list(data_path.glob('*.xls'))
    
    prod_day_df, prod_mo_df = pd.DataFrame(), pd.DataFrame()
    sf_day_df, sf_mo_df = pd.DataFrame(), pd.DataFrame()
    
    for f in valid_files:
        try:
            xls = pd.ExcelFile(f)
            if 'Day Wise Production Data' in xls.sheet_names and 'Steam Generation & Fuel Consump' in xls.sheet_names:
                # 1. Day Wise Production
                raw_prod = pd.read_excel(xls, sheet_name='Day Wise Production Data', header=None)
                all_data = []
                row2 = raw_prod.iloc[2].values
                date_cols = [i for i, val in enumerate(row2) if str(val).strip() == 'Date']
                for dc in date_cols:
                    if dc + 3 < len(raw_prod.columns):
                        chunk = raw_prod.iloc[3:, [dc, dc+1, dc+2, dc+3]].copy()
                        chunk.columns = ['Date', 'Line', 'Desc', 'Volume']
                        chunk['Date'] = pd.to_datetime(chunk['Date'], errors='coerce').ffill()
                        chunk = chunk.dropna(subset=['Line', 'Volume'])
                        all_data.append(chunk)
                if all_data:
                    prod_day_df = pd.concat(all_data, ignore_index=True)
                    prod_day_df['Volume'] = pd.to_numeric(prod_day_df['Volume'], errors='coerce').fillna(0)
                
                # 2. Month Wise Production
                if 'Month Wise Production Data' in xls.sheet_names:
                    raw_prod_mo = pd.read_excel(xls, sheet_name='Month Wise Production Data', header=None)
                    prod_mo_df = raw_prod_mo.iloc[3:, [0, 1]].copy()
                    if len(prod_mo_df.columns) == 2:
                        prod_mo_df.columns = ['Date', 'Volume']
                        prod_mo_df['Date'] = pd.to_datetime(prod_mo_df['Date'], errors='coerce')
                        prod_mo_df['Volume'] = pd.to_numeric(prod_mo_df['Volume'], errors='coerce').fillna(0)
                        prod_mo_df = prod_mo_df.dropna(subset=['Date'])
                
                # 3. Day Wise Steam & Fuel
                raw_sf = pd.read_excel(xls, sheet_name='Steam Generation & Fuel Consump', header=None)
                sf_temp = raw_sf.iloc[4:, [2, 3, 4, 5, 6, 7, 8]].copy()
                sf_temp.columns = ['Date', 'B1_Fuel', 'B2_Fuel', 'B3_Fuel', 'B1_Steam', 'B2_Steam', 'B3_Steam']
                sf_temp['Date'] = pd.to_datetime(sf_temp['Date'], errors='coerce')
                sf_temp = sf_temp.dropna(subset=['Date'])
                for c in sf_temp.columns[1:]: sf_temp[c] = pd.to_numeric(sf_temp[c], errors='coerce').fillna(0)
                sf_day_df = sf_temp
                
                # 4. Month Wise Steam & Fuel
                if 'Month Wise Steam Generation' in xls.sheet_names:
                    raw_sf_mo = pd.read_excel(xls, sheet_name='Month Wise Steam Generation', header=None)
                    sf_mo_temp = raw_sf_mo.iloc[4:, [2, 3, 4, 5, 6, 7, 8]].copy()
                    sf_mo_temp.columns = ['Date', 'B1_Fuel', 'B2_Fuel', 'B3_Fuel', 'B1_Steam', 'B2_Steam', 'B3_Steam']
                    sf_mo_temp['Date'] = pd.to_datetime(sf_mo_temp['Date'], errors='coerce')
                    sf_mo_temp = sf_mo_temp.dropna(subset=['Date'])
                    for c in sf_mo_temp.columns[1:]: sf_mo_temp[c] = pd.to_numeric(sf_mo_temp[c], errors='coerce').fillna(0)
                    sf_mo_df = sf_mo_temp
                break 
        except Exception:
            pass
            
    return sf_day_df, prod_day_df, sf_mo_df, prod_mo_df

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
    for kw in ['flow', 'steam', 'pressure', 'temperature', 'oxygen', 'level', 'feedwater', 'header']:
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
    fig.update_layout(legend=dict(orientation="h", yanchor="bottom", y=-0.2, xanchor="center", x=0.5))
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
flow_a_idx = None

if all_params:
    for i, p in enumerate(all_params):
        p_lower = p.lower()
        if p_lower == 'steam flow meter': default_flow_idx = i
        elif ('steam flow' in p_lower or 'flow meter' in p_lower) and all_params[default_flow_idx].lower() != 'steam flow meter': default_flow_idx = i
        
        # Strict logic for Meter A
        if p_lower == 'steam flow meter a': flow_a_idx = i
        elif 'flow meter a' in p_lower and 'tot' not in p_lower and flow_a_idx is None: flow_a_idx = i
            
        if p_lower == 'boiler pressure': default_press_idx = i
        elif ('boiler pressure' in p_lower or 'steam pressure' in p_lower) and all_params[default_press_idx].lower() != 'boiler pressure': default_press_idx = i
        
        if 'oxygen' in p_lower or 'o2' in p_lower: default_o2_idx = i

app_mode = st.sidebar.radio("Navigation", [
    "Boiler operation and Flow",
    "Loading pattern",
    "Statistical & Scatter Analysis",
    "System Cross-Analysis",
    "Parameter Correlation Matrix",
    "Mass & Energy Balance",
    "Steam to Fuel Analysis",
    "Production Efficiency",
    "Data Management"
], label_visibility="collapsed")

# ==============================================================================
# DATA MANAGEMENT TAB
# ==============================================================================
if app_mode == "Data Management":
    st.title("Data Management")
    st.markdown("Upload new raw data files. Ensure you upload the correct file for the corresponding Boiler.")
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

    st.markdown("### Process Audit Report")
    audit_file = st.file_uploader("Upload Production & Fuel Logs (Excel)", accept_multiple_files=False, key="up_audit")

    if st.button("Process & Save Active Uploads", type="primary"):
        data_dir = Path('./boiler_data')
        data_dir.mkdir(parents=True, exist_ok=True)
        files_saved = 0
        
        if b1_file:
            with open(data_dir / f"Boiler1_{b1_file.name}", "wb") as f: f.write(b1_file.getvalue())
            files_saved += 1
        if b2_file:
            with open(data_dir / f"Boiler2_{b2_file.name}", "wb") as f: f.write(b2_file.getvalue())
            files_saved += 1
        if b3_file:
            with open(data_dir / f"Boiler3_{b3_file.name}", "wb") as f: f.write(b3_file.getvalue())
            files_saved += 1
        if audit_file:
            with open(data_dir / audit_file.name, "wb") as f: f.write(audit_file.getvalue())
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
    
    tab_custom, tab_a = st.tabs(["Custom Parameter Analysis", "Steam Flow Meter A"])
    
    with tab_custom:
        with st.expander("Analysis Configuration", expanded=True):
            colA, colB, colC = st.columns([1.5, 1, 1.5])
            target_boilers = colA.multiselect("Select Target Boiler(s)", list(cache.keys()), default=list(cache.keys()), key="z_boilers")
            sel_min_dur = colB.slider("Zero-Flow Threshold (mins)", 0, 60, 2)
            target_params = colC.multiselect("Select Parameters to Display", options=all_params, default=[all_params[default_flow_idx], all_params[default_press_idx]], key="z_params")
            
            if not target_params or not target_boilers: st.warning("Please select at least one boiler and one parameter."); st.stop()
            sel_param = target_params[0]

        events_df = extract_events(cache, sel_min_dur)
        
        if events_df.empty:
            st.warning("No zero-flow events match the specified criteria.")
        else:
            filtered_events = events_df[events_df['boiler'].isin(target_boilers)]
            dates = sorted(filtered_events['date'].unique()) if not filtered_events.empty else []
            
            c_date, c_event = st.columns([1, 2])
            sel_date = c_date.selectbox("Event Date", options=dates if dates else ["No Events"])
            date_events = filtered_events[filtered_events['date'] == sel_date] if sel_date != "No Events" else pd.DataFrame()
            event_opts = {f"{row['boiler']} - {row['label']}": idx for idx, row in date_events.iterrows()} if not date_events.empty else {"No matching events": None}
            sel_event_label = c_event.selectbox("Select Specific Time Window", options=list(event_opts.keys()))
            
            event_id = event_opts.get(sel_event_label)
            if event_id is not None:
                ev = events_df.loc[event_id]
                st.markdown("---")
                
                totals = calculate_window_generation(cache, target_boilers, ev['start_time'], ev['end_time'], sel_param)
                cols = st.columns(len(totals) + 1)
                cols[0].metric("Event Duration", f"{ev['duration_mins']:.1f} min")
                for idx, (label, val) in enumerate(totals.items()):
                    cols[idx + 1].metric(f"{label} Loss/Gen", f"{val:.1f} Tons")
    
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
                    fig_sum.add_trace(go.Scatter(x=sum_df.index, y=sum_df['Aggregate'], mode='lines', fill='tozeroy', name="Overall Sum", line=dict(color=SUM_LINE, width=2), fillcolor=SUM_FILL))
                    
                    overlapping_events = events_df[events_df['boiler'].isin(target_boilers) & (events_df['start_time'] <= ev['window_end']) & (events_df['end_time'] >= ev['window_start'])]
                    for _, b_ev in overlapping_events.iterrows():
                        fig_sum.add_vrect(x0=b_ev['start_time'], x1=b_ev['end_time'], fillcolor="rgba(220, 38, 38, 0.15)", line_width=0)
                        
                    fig_sum.update_layout(title=f"Date: {sel_date}", template="plotly_white", hovermode="x unified", height=350, xaxis_title="Time", margin=dict(t=40, b=50))
                    fig_sum = set_legend_bottom(fig_sum)
                    st.plotly_chart(fig_sum, use_container_width=True)
                
                st.markdown(f"#### Boiler Event Breakdowns")
                for b_name in target_boilers:
                    if b_name not in cache: continue
                    b_df = cache[b_name]
                    w_df = b_df[(b_df['timestamp'] >= ev['window_start']) & (b_df['timestamp'] <= ev['window_end'])]
                    
                    if not w_df.empty:
                        if len(target_params) <= 2:
                            fig = make_subplots(specs=[[{"secondary_y": True}]])
                            m1 = find_matching_param(b_df.columns, target_params[0])
                            if m1: fig.add_trace(go.Scatter(x=w_df['timestamp'], y=pd.to_numeric(w_df[m1], errors='coerce'), name=m1, line=dict(color=B_COLORS.get(b_name), width=2)), secondary_y=False)
                            if len(target_params) == 2:
                                m2 = find_matching_param(b_df.columns, target_params[1])
                                if m2: fig.add_trace(go.Scatter(x=w_df['timestamp'], y=pd.to_numeric(w_df[m2], errors='coerce'), name=m2, line=dict(color=SEC_COLOR, width=2, dash='dot')), secondary_y=True)
                            
                            b_events = events_df[(events_df['boiler'] == b_name) & (events_df['start_time'] <= ev['window_end']) & (events_df['end_time'] >= ev['window_start'])]
                            for _, b_ev in b_events.iterrows():
                                fig.add_vrect(x0=b_ev['start_time'], x1=b_ev['end_time'], fillcolor="rgba(220, 38, 38, 0.15)", line_width=0)
                                
                            fig.update_layout(title=f"{b_name} Analysis | Date: {sel_date}", template="plotly_white", hovermode="x unified", height=350, xaxis_title="Time", margin=dict(t=40, b=50))
                            fig = set_legend_bottom(fig)
                            st.plotly_chart(fig, use_container_width=True)
                        else:
                            fig_multi = make_subplots(rows=len(target_params), cols=1, shared_xaxes=True, vertical_spacing=0.05, subplot_titles=target_params)
                            for idx, p in enumerate(target_params):
                                m_param = find_matching_param(b_df.columns, p)
                                if m_param:
                                    c_color = MULTI_COLORS[idx % len(MULTI_COLORS)]
                                    fig_multi.add_trace(go.Scatter(x=w_df['timestamp'], y=pd.to_numeric(w_df[m_param], errors='coerce'), name=m_param, line=dict(color=c_color)), row=idx+1, col=1)
                                    
                            b_events = events_df[(events_df['boiler'] == b_name) & (events_df['start_time'] <= ev['window_end']) & (events_df['end_time'] >= ev['window_start'])]
                            for _, b_ev in b_events.iterrows():
                                fig_multi.add_vrect(x0=b_ev['start_time'], x1=b_ev['end_time'], fillcolor="rgba(220, 38, 38, 0.15)", line_width=0)
                                
                            fig_multi.update_layout(title=f"{b_name} Multi-Metric Analysis | Date: {sel_date}", template="plotly_white", hovermode="x unified", height=200*len(target_params), xaxis_title="Time", margin=dict(t=40, b=50))
                            fig_multi = set_legend_bottom(fig_multi)
                            st.plotly_chart(fig_multi, use_container_width=True)
                                
    with tab_a:
        with st.expander("Analysis Configuration", expanded=True):
            c_boilers, c_params = st.columns([1.5, 1.5])
            t_boilers_a = c_boilers.multiselect("Select Boilers to Aggregate (Total)", list(cache.keys()), default=list(cache.keys()), key="za_boilers")
            
            default_za_params = [all_params[default_flow_idx]]
            if flow_a_idx is not None: default_za_params.append(all_params[flow_a_idx])
            
            za_params = c_params.multiselect("Select Parameters (Main vs Reference Meter)", options=all_params, default=default_za_params, key="za_params")
            
            c_shift, c_date = st.columns(2)
            preset_shift = c_shift.selectbox("Analysis Window", ["Full Day", "Shift A", "Shift B", "Shift C", "Custom Date Range"], key="za_shift")
            
            show_timeline_za = True
            if preset_shift == "Custom Date Range":
                dr1, dr2 = st.columns(2)
                start_d = dr1.date_input("Start Date", value=min_date, min_value=min_date, max_value=max_date, key="za_start_d")
                end_d = dr2.date_input("End Date", value=max_date, min_value=min_date, max_value=max_date, key="za_end_d")
                start_t = datetime.combine(start_d, time(0, 0))
                end_t = datetime.combine(end_d, time(23, 59))
                show_timeline_za = False
            else:
                t_date_a = c_date.date_input("Target Date", value=min_date, min_value=min_date, max_value=max_date, key="za_date")
                if preset_shift == "Shift A":
                    start_t = datetime.combine(t_date_a - timedelta(days=1), time(22, 0)); end_t = datetime.combine(t_date_a, time(6, 0))
                elif preset_shift == "Shift B":
                    start_t = datetime.combine(t_date_a, time(6, 0)); end_t = datetime.combine(t_date_a, time(14, 0))
                elif preset_shift == "Shift C":
                    start_t = datetime.combine(t_date_a, time(14, 0)); end_t = datetime.combine(t_date_a, time(22, 0))
                else:
                    start_t = datetime.combine(t_date_a, time(0, 0)); end_t = datetime.combine(t_date_a, time(23, 59))
        
        if len(za_params) < 2:
            st.warning("Please select at least two parameters (e.g., Main Flow and Flow Meter A) to compare.")
        elif not t_boilers_a:
            st.warning("Please select at least one boiler.")
        else:
            st.markdown("---")
            p_main = za_params[0]
            p_ref = za_params[1]
            
            sum_df = pd.DataFrame()
            node_df = pd.DataFrame()
            
            fig1 = go.Figure()
            fig2 = go.Figure()
            
            for b_name in t_boilers_a:
                if b_name not in cache: continue
                b_df = cache[b_name]
                w_df = b_df[(b_df['timestamp'] >= start_t) & (b_df['timestamp'] <= end_t)].copy()
                if w_df.empty: continue
                
                m1 = find_matching_param(b_df.columns, p_main)
                m2 = find_matching_param(b_df.columns, p_ref)
                
                if m1:
                    series = pd.to_numeric(w_df.set_index('timestamp')[m1], errors='coerce').resample('1min').mean().interpolate(method='time')
                    sum_df[b_name] = series
                    fig2.add_trace(go.Scatter(x=series.index, y=series.values, name=f"{b_name} ({p_main})", line=dict(color=B_COLORS.get(b_name), width=1.5)))
                
                if m2:
                    series2 = pd.to_numeric(w_df.set_index('timestamp')[m2], errors='coerce').resample('1min').mean().interpolate(method='time')
                    node_df[b_name] = series2

            if not node_df.empty:
                node_df['NodeAvg'] = node_df.mean(axis=1)
                ref_trace = go.Scatter(x=node_df.index, y=node_df['NodeAvg'], name=f"Reference ({p_ref})", line=dict(color='#000000', width=2.5, dash='dot'))
                fig1.add_trace(ref_trace)
                fig2.add_trace(ref_trace)

            if not sum_df.empty:
                sum_df['Total'] = sum_df.sum(axis=1)
                fig1.add_trace(go.Scatter(x=sum_df.index, y=sum_df['Total'], name=f"Total Aggregated Flow ({p_main})", line=dict(color=SUM_LINE, width=3)))

            if show_timeline_za:
                st.markdown("#### Total Aggregate Flow vs Reference Meter (Same Axis)")
                fig1.update_layout(template="plotly_white", hovermode="x unified", height=450, xaxis_title="Time", yaxis_title="Flow", margin=dict(t=10, b=50))
                fig1 = set_legend_bottom(fig1)
                st.plotly_chart(fig1, use_container_width=True)
                
                st.markdown("#### Individual Boiler Flows vs Reference Meter (Same Axis)")
                fig2.update_layout(template="plotly_white", hovermode="x unified", height=450, xaxis_title="Time", yaxis_title="Flow", margin=dict(t=10, b=50))
                fig2 = set_legend_bottom(fig2)
                st.plotly_chart(fig2, use_container_width=True)

# ==============================================================================
# 2. LOADING PATTERN
# ==============================================================================
elif app_mode == "Loading pattern":
    st.title("Loading Pattern")
    
    with st.expander("Analysis Configuration", expanded=True):
        c1, c2 = st.columns([1.5, 1.5])
        target_boilers = c1.multiselect("Select Boiler(s)", list(cache.keys()), default=list(cache.keys()), key="s_boilers")
        target_params = c2.multiselect("Select Parameters to Display", options=all_params, default=[all_params[default_flow_idx], all_params[default_press_idx]], key="s_params")
        if not target_params or not target_boilers: st.warning("Please select at least one boiler and parameter."); st.stop()
        sel_param = target_params[0] 

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
    colX, colY = st.columns([1, 2])
    explore_date = colX.date_input("Select Date to Explore", value=min_date, min_value=min_date, max_value=max_date, key="exp_date")
    time_range = colY.slider("Select Time Range", value=(time(0, 0), time(23, 59)), format="HH:mm", key="exp_time")
    
    if explore_date and target_boilers:
        start_dt = datetime.combine(explore_date, time_range[0])
        end_dt = datetime.combine(explore_date, time_range[1])
        
        fig_exp = go.Figure()
        sum_flow_df = pd.DataFrame()
        header_press_df = pd.DataFrame()
        
        h_press_col = next((c for c in all_params if 'header' in c.lower() and 'pressure' in c.lower()), None)
        
        for b_name in target_boilers:
            if b_name not in cache: continue
            b_df = cache[b_name]
            w_df = b_df[(b_df['timestamp'] >= start_dt) & (b_df['timestamp'] <= end_dt)]
            if w_df.empty: continue
            
            m_param_found = find_matching_param(b_df.columns, sel_param)
            if m_param_found:
                fig_exp.add_trace(go.Scatter(x=w_df['timestamp'], y=pd.to_numeric(w_df[m_param_found], errors='coerce'), mode='lines', name=f"{b_name} ({m_param_found})", line=dict(color=B_COLORS.get(b_name), width=1.5)))
                sum_flow_df[b_name] = pd.to_numeric(w_df.set_index('timestamp')[m_param_found], errors='coerce').resample('1min').mean().interpolate()
            
            if h_press_col:
                m_h = find_matching_param(b_df.columns, h_press_col)
                if m_h: header_press_df[b_name] = pd.to_numeric(w_df.set_index('timestamp')[m_h], errors='coerce').resample('1min').mean().interpolate()
            else:
                m_h = find_matching_param(b_df.columns, 'boiler pressure')
                if m_h: header_press_df[b_name] = pd.to_numeric(w_df.set_index('timestamp')[m_h], errors='coerce').resample('1min').mean().interpolate()

        fig_exp.update_layout(title=f"Combined Timeline: {sel_param} | Date: {explore_date}", template="plotly_white", hovermode="x unified", height=450, xaxis_title="Time", margin=dict(t=40, b=50))
        fig_exp = set_legend_bottom(fig_exp)
        st.plotly_chart(fig_exp, use_container_width=True)

        st.markdown("---")
        st.markdown("### Secondary Analysis Overlays")
        for b_name in target_boilers:
            if b_name not in cache: continue
            b_df = cache[b_name]
            w_df = b_df[(b_df['timestamp'] >= start_dt) & (b_df['timestamp'] <= end_dt)]
            if not w_df.empty:
                if len(target_params) <= 2:
                    fig_dual = make_subplots(specs=[[{"secondary_y": True}]])
                    m1 = find_matching_param(b_df.columns, target_params[0])
                    if m1: fig_dual.add_trace(go.Scatter(x=w_df['timestamp'], y=pd.to_numeric(w_df[m1], errors='coerce'), name=m1, line=dict(color=B_COLORS.get(b_name), width=2)), secondary_y=False)
                    if len(target_params) == 2:
                        m2 = find_matching_param(b_df.columns, target_params[1])
                        if m2: fig_dual.add_trace(go.Scatter(x=w_df['timestamp'], y=pd.to_numeric(w_df[m2], errors='coerce'), name=m2, line=dict(color=SEC_COLOR, width=2, dash='dot')), secondary_y=True)
                    
                    fig_dual.update_layout(title=f"{b_name} Analysis | Date: {explore_date}", template="plotly_white", hovermode="x unified", height=350, xaxis_title="Time", margin=dict(t=40, b=50))
                    fig_dual = set_legend_bottom(fig_dual)
                    st.plotly_chart(fig_dual, use_container_width=True)
                else:
                    fig_multi = make_subplots(rows=len(target_params), cols=1, shared_xaxes=True, vertical_spacing=0.05, subplot_titles=target_params)
                    for idx, p in enumerate(target_params):
                        m_param = find_matching_param(b_df.columns, p)
                        if m_param:
                            c_color = MULTI_COLORS[idx % len(MULTI_COLORS)]
                            fig_multi.add_trace(go.Scatter(x=w_df['timestamp'], y=pd.to_numeric(w_df[m_param], errors='coerce'), name=m_param, line=dict(color=c_color)), row=idx+1, col=1)
                    fig_multi.update_layout(title=f"{b_name} Multi-Metric Analysis | Date: {explore_date}", template="plotly_white", hovermode="x unified", height=200*len(target_params), xaxis_title="Time", margin=dict(t=40, b=50))
                    fig_multi = set_legend_bottom(fig_multi)
                    st.plotly_chart(fig_multi, use_container_width=True)

        if not sum_flow_df.empty and not header_press_df.empty:
            st.markdown("---")
            st.markdown("### Total Plant Load vs Header Pressure")
            fig_total = make_subplots(specs=[[{"secondary_y": True}]])
            
            sum_flow_df['Total'] = sum_flow_df.sum(axis=1)
            header_press_df['Avg'] = header_press_df.mean(axis=1)
            
            fig_total.add_trace(go.Scatter(x=sum_flow_df.index, y=sum_flow_df['Total'], name="Aggregate Steam Flow", line=dict(color=SUM_LINE, width=2)), secondary_y=False)
            fig_total.add_trace(go.Scatter(x=header_press_df.index, y=header_press_df['Avg'], name="Header Pressure", line=dict(color='#000000', width=2, dash='dot')), secondary_y=True)
            
            fig_total.update_layout(template="plotly_white", hovermode="x unified", height=400, xaxis_title="Time", margin=dict(t=10, b=50))
            fig_total = set_legend_bottom(fig_total)
            st.plotly_chart(fig_total, use_container_width=True)

# ==============================================================================
# 3. STATISTICAL & SCATTER ANALYSIS
# ==============================================================================
elif app_mode == "Statistical & Scatter Analysis":
    st.title("Statistical & Scatter Analysis")
    
    with st.expander("Analysis Configuration", expanded=True):
        col1, col2 = st.columns([1.5, 1.5])
        target_boilers = col1.multiselect("Select Boiler(s)", list(cache.keys()), default=list(cache.keys()), key="o2_boilers")
        target_params = col2.multiselect("Select Parameters", options=all_params, default=[all_params[default_flow_idx], all_params[default_o2_idx]], key="o2_params")
        
        if not target_params or not target_boilers: st.warning("Please select at least one boiler and one parameter."); st.stop()
        
        c_shift, c_date, c_thresh = st.columns([1, 1, 1])
        preset_shift = c_shift.selectbox("Analysis Window", ["Custom Time (Single Day)", "Custom Date Range", "Shift A", "Shift B", "Shift C", "Full Day"])
        op_threshold = c_thresh.number_input(f"Active Threshold ({target_params[0]} >)", value=1.0, step=0.5)
        
        show_timeline = True
        if preset_shift == "Custom Date Range":
            dr1, dr2 = st.columns(2)
            start_d = dr1.date_input("Start Date", value=min_date, min_value=min_date, max_value=max_date, key="o2_start_d")
            end_d = dr2.date_input("End Date", value=max_date, min_value=min_date, max_value=max_date, key="o2_end_d")
            start_t = datetime.combine(start_d, time(0, 0))
            end_t = datetime.combine(end_d, time(23, 59))
            show_timeline = False 
        else:
            target_o2_date = c_date.date_input("Target Date", value=min_date, min_value=min_date, max_value=max_date, key="o2_date")
            if preset_shift == "Shift A":
                start_t = datetime.combine(target_o2_date - timedelta(days=1), time(22, 0)); end_t = datetime.combine(target_o2_date, time(6, 0))
            elif preset_shift == "Shift B":
                start_t = datetime.combine(target_o2_date, time(6, 0)); end_t = datetime.combine(target_o2_date, time(14, 0))
            elif preset_shift == "Shift C":
                start_t = datetime.combine(target_o2_date, time(14, 0)); end_t = datetime.combine(target_o2_date, time(22, 0))
            elif preset_shift == "Full Day":
                start_t = datetime.combine(target_o2_date, time(0, 0)); end_t = datetime.combine(target_o2_date, time(23, 59))
            else:
                custom_tr = st.slider("Custom Time Window", value=(time(0, 0), time(23, 59)), format="HH:mm", key="o2_time")
                start_t = datetime.combine(target_o2_date, custom_tr[0]); end_t = datetime.combine(target_o2_date, custom_tr[1])

    st.markdown("---")
    
    stats_data = []
    line_charts = []
    generate_scatter = (len(target_params) == 2)
    fig_scat = go.Figure() if generate_scatter else None
    fig_3d = go.Figure() if generate_scatter else None
    pooled_x, pooled_y = [], []
    dist_figs = {p: go.Figure() for p in target_params}
    
    for b_name in target_boilers:
        if b_name not in cache: continue
        b_df_o2 = cache[b_name]
        
        mapped_cols = [find_matching_param(b_df_o2.columns, p) for p in target_params]
        if not all(mapped_cols): continue
        
        w_df_o2 = b_df_o2[(b_df_o2['timestamp'] >= start_t) & (b_df_o2['timestamp'] <= end_t)].copy()
        for mc in mapped_cols: w_df_o2[f'{mc}_Num'] = pd.to_numeric(w_df_o2[mc], errors='coerce')
        w_df_o2 = w_df_o2.dropna(subset=[f'{mc}_Num' for mc in mapped_cols])
        
        if not w_df_o2.empty:
            stats_df_o2 = w_df_o2[w_df_o2[f'{mapped_cols[0]}_Num'] >= op_threshold]
            b_stats = {"Boiler": b_name}
            
            if not stats_df_o2.empty:
                for mc, p in zip(mapped_cols, target_params):
                    b_stats[f"Min {p}"] = stats_df_o2[f'{mc}_Num'].min()
                    b_stats[f"Avg {p}"] = stats_df_o2[f'{mc}_Num'].mean()
                    b_stats[f"Max {p}"] = stats_df_o2[f'{mc}_Num'].max()
                    
                    counts, bins = np.histogram(stats_df_o2[f'{mc}_Num'], bins=30, density=True)
                    bin_centers = 0.5 * (bins[:-1] + bins[1:])
                    dist_figs[p].add_trace(go.Scatter(x=bin_centers, y=counts, mode='lines', name=b_name, line=dict(color=B_COLORS.get(b_name), width=2), fill='tozeroy', fillcolor=B_COLORS.get(b_name).replace(')', ', 0.2)').replace('rgb', 'rgba') if 'rgb' in B_COLORS.get(b_name) else None))
                
                if generate_scatter:
                    pooled_x.extend(stats_df_o2[f'{mapped_cols[0]}_Num'].values)
                    pooled_y.extend(stats_df_o2[f'{mapped_cols[1]}_Num'].values)
                    fig_scat.add_trace(go.Scattergl(x=stats_df_o2[f'{mapped_cols[0]}_Num'], y=stats_df_o2[f'{mapped_cols[1]}_Num'], mode='markers', name=b_name, marker=dict(color=B_COLORS.get(b_name), size=5, opacity=0.6), text=stats_df_o2['timestamp'].dt.strftime('%Y-%m-%d %H:%M'), hoverinfo="text+x+y+name"))
            else:
                for p in target_params:
                    b_stats[f"Min {p}"] = 0.0; b_stats[f"Avg {p}"] = 0.0; b_stats[f"Max {p}"] = 0.0
            stats_data.append(b_stats)
            
            if show_timeline:
                if len(target_params) <= 2:
                    fig_line = make_subplots(specs=[[{"secondary_y": True}]])
                    fig_line.add_trace(go.Scatter(x=w_df_o2['timestamp'], y=w_df_o2[f'{mapped_cols[0]}_Num'], name=target_params[0], line=dict(color=B_COLORS.get(b_name), width=2)), secondary_y=False)
                    if len(target_params) == 2:
                        fig_line.add_trace(go.Scatter(x=w_df_o2['timestamp'], y=w_df_o2[f'{mapped_cols[1]}_Num'], name=target_params[1], line=dict(color=SEC_COLOR, width=2, dash='dot')), secondary_y=True)
                    fig_line.update_layout(title=f"{b_name} Breakdown", template="plotly_white", hovermode="x unified", height=300, xaxis_title="Time", margin=dict(t=40, b=50))
                    fig_line = set_legend_bottom(fig_line)
                    line_charts.append(fig_line)
                else:
                    fig_multi = make_subplots(rows=len(target_params), cols=1, shared_xaxes=True, vertical_spacing=0.05, subplot_titles=target_params)
                    for idx, (mc, p) in enumerate(zip(mapped_cols, target_params)):
                        c_color = MULTI_COLORS[idx % len(MULTI_COLORS)]
                        fig_multi.add_trace(go.Scatter(x=w_df_o2['timestamp'], y=w_df_o2[f'{mc}_Num'], name=p, line=dict(color=c_color)), row=idx+1, col=1)
                    fig_multi.update_layout(title=f"{b_name} Multi-Metric Analysis", template="plotly_white", hovermode="x unified", height=200*len(target_params), xaxis_title="Time", margin=dict(t=40, b=50))
                    fig_multi = set_legend_bottom(fig_multi)
                    line_charts.append(fig_multi)
    
    if stats_data:
        st.markdown(f"#### Period Statistics Summary (Calculated strictly when {target_params[0]} > {op_threshold})")
        st.dataframe(pd.DataFrame(stats_data).set_index("Boiler").style.format("{:.2f}"), use_container_width=True)
        
        if show_timeline:
            st.markdown("#### Timeline Breakdowns")
            for fig in line_charts: st.plotly_chart(fig, use_container_width=True)
        
        if generate_scatter:
            st.markdown("#### 2D Scatter Correlation (All Selected Boilers)")
            date_str = f"{start_t.date()} to {end_t.date()}" if preset_shift == "Custom Date Range" else str(start_t.date())
            fig_scat.update_layout(title=f"Date: {date_str}", xaxis_title=target_params[0], yaxis_title=target_params[1], template="plotly_white", height=500, margin=dict(t=40, b=50))
            fig_scat = set_legend_bottom(fig_scat)
            st.plotly_chart(fig_scat, use_container_width=True)
        
        st.markdown("#### Standard Deviation Distributions (Line Density)")
        d_cols = st.columns(2)
        date_str = f"{start_t.date()} to {end_t.date()}" if preset_shift == "Custom Date Range" else str(start_t.date())
        for idx, p in enumerate(target_params):
            dist_figs[p].update_layout(title=f"{p} Distribution | Date: {date_str}", template="plotly_white", height=350, margin=dict(t=40, b=50), xaxis_title=p, yaxis_title="Density")
            dist_figs[p] = set_legend_bottom(dist_figs[p])
            d_cols[idx % 2].plotly_chart(dist_figs[p], use_container_width=True)
        
        if generate_scatter and pooled_x and pooled_y:
            st.markdown(f"#### 3D Bivariate Density Map ({target_params[0]} vs {target_params[1]})")
            H, xedges, yedges = np.histogram2d(pooled_x, pooled_y, bins=30, density=True)
            fig_3d.add_trace(go.Surface(z=H.T, x=xedges[:-1], y=yedges[:-1], colorscale='Viridis', opacity=0.9))
            fig_3d.update_layout(
                title=f"Date: {date_str}",
                scene=dict(xaxis_title=target_params[0], yaxis_title=target_params[1], zaxis_title="Probability Density", camera=dict(eye=dict(x=1.5, y=-1.5, z=1.2))),
                height=600, margin=dict(t=40, b=50)
            )
            st.plotly_chart(fig_3d, use_container_width=True, config={'scrollZoom': False})
    else:
        st.warning("No valid overlapping data points found.")

# ==============================================================================
# 4. SYSTEM CROSS-ANALYSIS
# ==============================================================================
elif app_mode == "System Cross-Analysis":
    st.title("System Cross-Analysis")
    
    with st.expander("Analysis Configuration", expanded=True):
        col1, col2 = st.columns([1.5, 1.5])
        target_boilers = col1.multiselect("Select Boiler(s)", list(cache.keys()), default=[list(cache.keys())[0]], key="crs_boilers")
        target_params = col2.multiselect("Select Parameters to Cross-Analyze", options=all_params, default=[all_params[default_flow_idx], all_params[default_press_idx]], key="crs_params")
        
        c_shift, c_date = st.columns(2)
        preset_shift = c_shift.selectbox("Analysis Window", ["Full Day", "Shift A", "Shift B", "Shift C"])
        target_crs_date = c_date.date_input("Target Date", value=min_date, min_value=min_date, max_value=max_date, key="crs_date")
        
        if preset_shift == "Shift A":
            start_t = datetime.combine(target_crs_date - timedelta(days=1), time(22, 0)); end_t = datetime.combine(target_crs_date, time(6, 0))
        elif preset_shift == "Shift B":
            start_t = datetime.combine(target_crs_date, time(6, 0)); end_t = datetime.combine(target_crs_date, time(14, 0))
        elif preset_shift == "Shift C":
            start_t = datetime.combine(target_crs_date, time(14, 0)); end_t = datetime.combine(target_crs_date, time(22, 0))
        else:
            start_t = datetime.combine(target_crs_date, time(0, 0)); end_t = datetime.combine(target_crs_date, time(23, 59))

    if not target_boilers or not target_params: st.stop()

    fig_multi = go.Figure()
    fig_scat_all = go.Figure() if len(target_params) == 2 else None
    
    for b_name in target_boilers:
        if b_name in cache:
            b_df = cache[b_name]
            w_df = b_df[(b_df['timestamp'] >= start_t) & (b_df['timestamp'] <= end_t)].copy()
            
            if not w_df.empty:
                valid_cols = []
                for p in target_params:
                    match = find_matching_param(w_df.columns, p)
                    if match: valid_cols.append(match)
                
                # Dedicated Boilerwise diagrams
                if len(valid_cols) == 1:
                    st.markdown(f"#### {b_name}: Timeline ({valid_cols[0]})")
                    fig_eff = go.Figure()
                    fig_eff.add_trace(go.Scatter(x=w_df['timestamp'], y=pd.to_numeric(w_df[valid_cols[0]], errors='coerce'), name=valid_cols[0], line=dict(color=B_COLORS.get(b_name))))
                    fig_eff.update_layout(title=f"Date: {start_t.date()}", template="plotly_white", hovermode="x unified", height=400, xaxis_title="Time", margin=dict(t=40, b=50))
                    fig_eff = set_legend_bottom(fig_eff)
                    st.plotly_chart(fig_eff, use_container_width=True)

                elif len(valid_cols) == 2:
                    st.markdown(f"#### {b_name}: {valid_cols[0]} vs {valid_cols[1]}")
                    fig_eff = make_subplots(specs=[[{"secondary_y": True}]])
                    fig_eff.add_trace(go.Scatter(x=w_df['timestamp'], y=pd.to_numeric(w_df[valid_cols[0]], errors='coerce'), name=valid_cols[0], line=dict(color=B_COLORS.get(b_name))), secondary_y=False)
                    fig_eff.add_trace(go.Scatter(x=w_df['timestamp'], y=pd.to_numeric(w_df[valid_cols[1]], errors='coerce'), name=valid_cols[1], line=dict(color='#d62728', dash='dot')), secondary_y=True)
                    fig_eff.update_layout(title=f"Date: {start_t.date()}", template="plotly_white", hovermode="x unified", height=400, xaxis_title="Time", margin=dict(t=40, b=50))
                    fig_eff = set_legend_bottom(fig_eff)
                    st.plotly_chart(fig_eff, use_container_width=True)
                    
                    fig_scat_all.add_trace(go.Scattergl(
                        x=pd.to_numeric(w_df[valid_cols[0]], errors='coerce'), 
                        y=pd.to_numeric(w_df[valid_cols[1]], errors='coerce'), 
                        mode='markers', name=b_name,
                        marker=dict(color=B_COLORS.get(b_name), size=6, opacity=0.6)
                    ))

                elif len(valid_cols) > 2:
                    st.markdown(f"#### {b_name}: Multi-Parameter Cross Analysis")
                    fig_b_multi = make_subplots(rows=len(valid_cols), cols=1, shared_xaxes=True, vertical_spacing=0.05, subplot_titles=valid_cols)
                    for idx, c_name in enumerate(valid_cols):
                        c_color = MULTI_COLORS[idx % len(MULTI_COLORS)]
                        fig_b_multi.add_trace(go.Scatter(x=w_df['timestamp'], y=pd.to_numeric(w_df[c_name], errors='coerce'), name=c_name, line=dict(color=c_color)), row=idx+1, col=1)
                    
                    dynamic_height = 200 * len(valid_cols)
                    fig_b_multi.update_layout(title=f"Date: {start_t.date()}", template="plotly_white", hovermode="x unified", height=dynamic_height, xaxis_title="Time", margin=dict(t=40, b=50))
                    fig_b_multi = set_legend_bottom(fig_b_multi)
                    st.plotly_chart(fig_b_multi, use_container_width=True)
                
                # Aggregate Timeline Construction
                for idx, c_name in enumerate(valid_cols):
                    c_color = MULTI_COLORS[idx % len(MULTI_COLORS)] if len(target_boilers) == 1 else B_COLORS.get(b_name, '#000000')
                    dash_style = 'solid' if len(target_boilers) == 1 else ['solid', 'dot', 'dash', 'dashdot'][idx % 4]
                    fig_multi.add_trace(go.Scatter(x=w_df['timestamp'], y=pd.to_numeric(w_df[c_name], errors='coerce'), name=f"{b_name} - {c_name}", line=dict(color=c_color, width=2, dash=dash_style)))
                    
    st.markdown("---")
    
    if fig_multi.data:
        st.markdown(f"#### Multi-Parameter Overlay Timeline")
        fig_multi.update_layout(title=f"Date: {start_t.date()}", template="plotly_white", hovermode="x unified", height=500, xaxis_title="Time", margin=dict(t=40, b=50))
        fig_multi = set_legend_bottom(fig_multi)
        st.plotly_chart(fig_multi, use_container_width=True)

    if fig_scat_all is not None:
        st.markdown(f"#### Unified Scatter Comparison ({target_params[0]} vs {target_params[1]})")
        fig_scat_all.update_layout(xaxis_title=target_params[0], yaxis_title=target_params[1], template="plotly_white", height=500, margin=dict(t=40, b=50))
        fig_scat_all = set_legend_bottom(fig_scat_all)
        st.plotly_chart(fig_scat_all, use_container_width=True)

# ==============================================================================
# 5. PARAMETER CORRELATION MATRIX 
# ==============================================================================
elif app_mode == "Parameter Correlation Matrix":
    st.title("Parameter Correlation Matrix")
    
    target_heatmap_keywords = ['boiler pressure', 'steam flow meter', 'boiler capacity', 'furnace pressure', 'oxygen', 'eco inlet temp', 'deaerator level', 'deaerator temperature', 'fuel feeding screw', 'rotary feeder screw', 'eco outlet temp', 'pa flash temp', 'fw eco ol temperature']
    
    common_cols = []
    if list(cache.keys()):
        b_df = cache[list(cache.keys())[0]]
        for kw in target_heatmap_keywords:
            m_col = find_matching_param(b_df.columns, kw)
            if m_col and m_col not in common_cols: common_cols.append(m_col)

    with st.expander("Analysis Configuration", expanded=True):
        col1, col2 = st.columns([1.5, 1.5])
        target_boilers = col1.multiselect("Select Boiler(s)", list(cache.keys()), default=[list(cache.keys())[0]], key="corr_boilers")
        analysis_mode = col2.radio("Analysis Mode", ["Single Fixed Window", "Cinematic Time-Lapse Animation"], horizontal=True)
        
        if analysis_mode == "Single Fixed Window":
            c_shift, c_date = st.columns(2)
            preset_shift = c_shift.selectbox("Analysis Window", ["Full Day", "Shift A", "Shift B", "Shift C"])
            target_corr_date = c_date.date_input("Target Date", value=min_date, min_value=min_date, max_value=max_date)
            
            if preset_shift == "Shift A":
                start_t = datetime.combine(target_corr_date - timedelta(days=1), time(22, 0)); end_t = datetime.combine(target_corr_date, time(6, 0))
            elif preset_shift == "Shift B":
                start_t = datetime.combine(target_corr_date, time(6, 0)); end_t = datetime.combine(target_corr_date, time(14, 0))
            elif preset_shift == "Shift C":
                start_t = datetime.combine(target_corr_date, time(14, 0)); end_t = datetime.combine(target_corr_date, time(22, 0))
            else:
                start_t = datetime.combine(target_corr_date, time(0, 0)); end_t = datetime.combine(target_corr_date, time(23, 59))
        else:
            d1, d2 = st.columns(2)
            tl_start = d1.date_input("Animation Start Date", value=min_date, min_value=min_date, max_value=max_date)
            tl_end = d2.date_input("Animation End Date", value=max_date, min_value=min_date, max_value=max_date)
            if tl_end < tl_start: st.error("End Date must be after Start Date"); st.stop()
            if (tl_end - tl_start).days > 60: st.warning("Range too large for animation memory (Max 60 days)."); st.stop()
            
            st.markdown("#### Configure Trend Tracking")
            c_tr1, c_tr2 = st.columns(2)
            trace_p1 = c_tr1.selectbox("Metric 1 to track over time:", options=common_cols, index=0)
            trace_p2 = c_tr2.selectbox("Metric 2 to track over time:", options=common_cols, index=min(1, len(common_cols)-1) if common_cols else 0)

    unified_trend_data = {}

    for target_boiler in target_boilers:
        st.markdown("---")
        if target_boiler in cache:
            b_df = cache[target_boiler]
            cols_to_keep = []
            for kw in target_heatmap_keywords:
                matched_col = find_matching_param(b_df.columns, kw)
                if matched_col and matched_col not in cols_to_keep: cols_to_keep.append(matched_col)
                    
            if not cols_to_keep:
                st.warning(f"No targeted parameters found for {target_boiler}.")
                continue
                
            if analysis_mode == "Single Fixed Window":
                st.markdown(f"#### Correlation Heatmap: {target_boiler}")
                w_df = b_df[(b_df['timestamp'] >= start_t) & (b_df['timestamp'] <= end_t)].copy()
                if not w_df.empty:
                    w_df_numeric = w_df[cols_to_keep].apply(pd.to_numeric, errors='coerce').dropna(axis=1, how='all')
                    if not w_df_numeric.empty and w_df_numeric.shape[1] > 1:
                        corr_matrix = w_df_numeric.corr(numeric_only=True)
                        fig_corr = go.Figure(data=go.Heatmap(
                            z=corr_matrix.values, x=corr_matrix.columns, y=corr_matrix.index,
                            colorscale='RdBu_r', zmin=-1, zmax=1,
                            hovertemplate="Variable X: %{x}<br>Variable Y: %{y}<br>Pearson Correlation: %{z:.2f}<extra></extra>"
                        ))
                        fig_corr.update_layout(title=f"Date: {start_t.date()}", template="plotly_white", height=600, margin=dict(t=40, b=150, l=150), xaxis=dict(tickangle=45))
                        st.plotly_chart(fig_corr, use_container_width=True)
                    else:
                        st.warning("Not enough valid numeric data in this time window.")
                else:
                    st.warning("No data available for this shift.")
                    
            else: 
                st.markdown(f"#### Dynamic Correlation Map: {target_boiler}")
                frames = []
                slider_steps = []
                trend_dates = []
                trend_corrs = []
                first_z, valid_cols = None, None
                current_d = tl_start
                
                b_trace_p1 = find_matching_param(b_df.columns, trace_p1)
                b_trace_p2 = find_matching_param(b_df.columns, trace_p2)
                
                while current_d <= tl_end:
                    d_start = datetime.combine(current_d, time(0,0))
                    d_end = datetime.combine(current_d, time(23,59))
                    w_df = b_df[(b_df['timestamp'] >= d_start) & (b_df['timestamp'] <= d_end)].copy()
                    
                    if not w_df.empty:
                        w_df_numeric = w_df[cols_to_keep].apply(pd.to_numeric, errors='coerce').dropna(axis=1, how='all')
                        if w_df_numeric.shape[1] > 1:
                            corr_matrix = w_df_numeric.corr(numeric_only=True).fillna(0)
                            if first_z is None:
                                first_z = corr_matrix.values
                                valid_cols = corr_matrix.columns
                                
                            if b_trace_p1 and b_trace_p2 and b_trace_p1 in corr_matrix.columns and b_trace_p2 in corr_matrix.columns:
                                trend_dates.append(current_d)
                                trend_corrs.append(corr_matrix.loc[b_trace_p1, b_trace_p2])
                                
                            frame_name = current_d.strftime("%Y-%m-%d")
                            frames.append(go.Frame(data=[go.Heatmap(z=corr_matrix.values)], name=frame_name))
                            slider_steps.append({
                                "args": [[frame_name], {"frame": {"duration": 780, "redraw": True}, "mode": "immediate", "transition": {"duration": 780}}],
                                "label": frame_name, "method": "animate"
                            })
                    current_d += timedelta(days=1)
                    
                if trend_dates:
                    unified_trend_data[target_boiler] = {'dates': trend_dates, 'corrs': trend_corrs}
                    
                if frames and first_z is not None:
                    fig_anim = go.Figure(data=[go.Heatmap(z=first_z, x=valid_cols, y=valid_cols, colorscale='RdBu_r', zmin=-1, zmax=1)], frames=frames)
                    fig_anim.update_layout(
                        template="plotly_white", height=700, margin=dict(t=40, b=150, l=150), xaxis=dict(tickangle=45),
                        updatemenus=[dict(
                            type="buttons",
                            buttons=[
                                dict(label="▶ Play", method="animate", args=[None, {"frame": {"duration": 780, "redraw": True}, "fromcurrent": True, "transition": {"duration": 780}}]),
                                dict(label="⏸ Pause", method="animate", args=[[None], {"frame": {"duration": 0, "redraw": False}, "mode": "immediate", "transition": {"duration": 0}}])
                            ],
                            direction="left", pad={"r": 10, "t": 87}, showactive=False, x=0.1, y=0, xanchor="right", yanchor="top"
                        )],
                        sliders=[dict(
                            active=0, yanchor="top", xanchor="left",
                            currentvalue={"font": {"size": 16}, "prefix": "Analyzing Date: ", "visible": True, "xanchor": "right"},
                            transition={"duration": 780, "easing": "cubic-in-out"},
                            pad={"b": 10, "t": 50}, len=0.9, x=0.1, y=0, steps=slider_steps
                        )]
                    )
                    st.plotly_chart(fig_anim, use_container_width=True)
                else:
                    st.warning("Could not calculate enough correlation frames for the selected date range.")
                    
    if analysis_mode == "Cinematic Time-Lapse Animation" and unified_trend_data:
        st.markdown("---")
        st.markdown(f"#### Unified Correlation Magnitude Tracker: {trace_p1} vs {trace_p2}")
        fig_trend = go.Figure()
        for b_name, t_data in unified_trend_data.items():
            fig_trend.add_trace(go.Scatter(x=t_data['dates'], y=t_data['corrs'], mode='lines+markers', name=b_name, line=dict(color=B_COLORS.get(b_name, '#ff7f0e'), width=3), marker=dict(size=8)))
        fig_trend.update_layout(
            template="plotly_white", height=400, hovermode="x unified",
            xaxis_title="Date", yaxis=dict(title="Pearson Correlation (r)", range=[-1.1, 1.1]),
            margin=dict(t=10, b=40)
        )
        fig_trend.add_hline(y=0, line_dash="dot", line_color="black")
        fig_trend = set_legend_bottom(fig_trend)
        st.plotly_chart(fig_trend, use_container_width=True)

# ==============================================================================
# 6. MASS & ENERGY BALANCE (SANKEY)
# ==============================================================================
elif app_mode == "Mass & Energy Balance":
    st.title("Mass & Energy Balance Diagram")
    
    col1, col2 = st.columns([1, 1.5])
    analysis_type = col1.radio("Balance Type", ["Mass Balance (Tons)", "Energy Balance (kCal)"], horizontal=True)
    
    default_sankey_data = [
        {"Source": "Feed Water", "Value": 598461, "Target": "Steam Generation"},
        {"Source": "Feed Water", "Value": 21731, "Target": "Blowdown"},
        {"Source": "Steam Generation", "Value": 485432, "Target": "Steam Consumption"},
        {"Source": "Steam Generation", "Value": 88837, "Target": "Losses"},
        {"Source": "Steam Consumption", "Value": 38607, "Target": "Flash steam"},
        {"Source": "Steam Consumption", "Value": 446825, "Target": "Condensate"},
        {"Source": "Flash steam", "Value": 3943, "Target": "Flash Local Vent"},
        {"Source": "Flash steam", "Value": 34664, "Target": "Flash steam to Boiler house"},
        {"Source": "Flash steam to Boiler house", "Value": 8044, "Target": "Flash Venting at boiler"},
        {"Source": "Flash steam to Boiler house", "Value": 26620, "Target": "Flash To Deaerator tank"},
        {"Source": "Condensate", "Value": 12191, "Target": "Flash Local Vent"},
        {"Source": "Condensate", "Value": 434634, "Target": "Condensate to Boiler House"},
        {"Source": "Losses", "Value": 18870, "Target": "Mainline drain"},
        {"Source": "Losses", "Value": 2495, "Target": "Steam Leakages"},
        {"Source": "Losses", "Value": 2147, "Target": "Stam Venting"},
        {"Source": "Losses", "Value": 65325, "Target": "Trap loss"},
        {"Source": "Flash To Deaerator tank", "Value": 26620, "Target": "Condensate to Deaerator"},
        {"Source": "Condensate to Boiler House", "Value": 377768, "Target": "Condensate to Deaerator"},
        {"Source": "Condensate to Boiler House", "Value": 56866, "Target": "Unaccounted"}
    ]
    
    if 'sankey_df' not in st.session_state:
        st.session_state.sankey_df = pd.DataFrame(default_sankey_data)
        
    st.markdown("### Interactive Parameter Editor")
    c_mode1, c_mode2 = st.columns(2)
    editor_mode = c_mode1.radio("Input Editor Mode", ["Interactive Table", "Raw Text (Fallback)"], horizontal=True)
    
    if editor_mode == "Interactive Table":
        try:
            edited_df = st.data_editor(st.session_state.sankey_df, num_rows="dynamic", use_container_width=True, height=300)
            st.session_state.sankey_df = edited_df
        except Exception:
            st.error("Dynamic table failed to load. Please switch to 'Raw Text (Fallback)'.")
            edited_df = st.session_state.sankey_df
    else:
        st.info("Format: `Source [Value] Target`")
        raw_text = st.text_area("Edit Configuration", value="\n".join([f"{row['Source']} [{row['Value']}] {row['Target']}" for _, row in st.session_state.sankey_df.iterrows()]), height=300)
        parsed_data = []
        for line in raw_text.split('\n'):
            match = re.search(r'(.*)\[(.*)\](.*)', line)
            if match:
                src, val_str, tgt = match.groups()
                try:
                    parsed_data.append({"Source": src.strip(), "Value": float(val_str.strip()), "Target": tgt.strip()})
                except ValueError:
                    continue
        edited_df = pd.DataFrame(parsed_data)
        if not edited_df.empty: st.session_state.sankey_df = edited_df

    st.markdown("---")
    
    if not edited_df.empty:
        csv = edited_df.to_csv(index=False).encode('utf-8')
        st.download_button(label="📥 Download Data Table (CSV)", data=csv, file_name='sankey_balance.csv', mime='text/csv')
        
        nodes = []
        for src in edited_df['Source'].dropna().astype(str):
            if src not in nodes: nodes.append(src)
        for tgt in edited_df['Target'].dropna().astype(str):
            if tgt not in nodes: nodes.append(tgt)
            
        links_src = [nodes.index(str(src)) for src in edited_df['Source'].dropna()]
        links_tgt = [nodes.index(str(tgt)) for tgt in edited_df['Target'].dropna()]
        links_val = pd.to_numeric(edited_df['Value'].dropna(), errors='coerce').fillna(0).tolist()
        
        node_colors = ['#e377c2', '#7f7f7f', '#bcbd22', '#17becf', '#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd', '#8c564b']
        dynamic_node_colors = [node_colors[i % len(node_colors)] for i in range(len(nodes))]
        link_colors = [dynamic_node_colors[src].replace('rgb', 'rgba').replace(')', ', 0.4)') if 'rgb' in dynamic_node_colors[src] else 'rgba(180, 180, 180, 0.4)' for src in links_src]

        fig_sankey = go.Figure(data=[go.Sankey(
            arrangement = "snap",
            node = dict(
                pad = 30,
                thickness = 40,
                line = dict(color = "black", width = 0.5),
                label = nodes,
                color = dynamic_node_colors
            ),
            link = dict(
                source = links_src,
                target = links_tgt,
                value = links_val,
                color = link_colors
            )
        )])
        
        fig_sankey.update_layout(
            title_text=f"System Flow Visualization - {analysis_type}",
            font=dict(size=14, color="black"),
            height=800,
            template="plotly_white",
            margin=dict(t=50, b=50, l=50, r=50)
        )
        st.plotly_chart(fig_sankey, use_container_width=True)
    else:
        st.warning("Table is empty. Please add parameters to generate the diagram.")
