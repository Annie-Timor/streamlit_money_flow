# pages/4_ETF_Extremum_Proximity.py
import streamlit as st
import akshare as ak
import pandas as pd
import numpy as np
from scipy.signal import find_peaks
from datetime import datetime, timedelta
import pandas_ta as ta # 导入库，通常简写为 ta

# --- 初始化 session_state ---
if 'debug_logs' not in st.session_state:
    st.session_state.debug_logs = []
if 'max_debug_logs' not in st.session_state:
    st.session_state.max_debug_logs = 100

# --- 调试信息记录函数 ---
def add_debug_log(message):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_msg = f"[{timestamp}] {message}"
    st.session_state.debug_logs.append(log_msg)
    if len(st.session_state.debug_logs) > st.session_state.max_debug_logs:
        st.session_state.debug_logs.pop(0)
    # print(f"DEBUG: {message}")

# --- 导入ETF映射 ---
try:
    from etf_industry_map import ETF_INDUSTRY_MAPPINGS
except ImportError:
    st.sidebar.warning("`etf_industry_map.py` 中未找到 `ETF_INDUSTRY_MAPPINGS`。将使用预设的行业ETF列表。")
    ETF_INDUSTRY_MAPPINGS = {
        "半导体": "512480", "医疗器械": "159883", "酿酒行业": "512690",
        "银行": "512800", "证券": "512880", "光伏设备": "159863",
    }

try:
    from etf_industry_map import ETF_SELECT_MAPPINGS
except ImportError:
    st.sidebar.warning("`etf_industry_map.py` 中未找到 `ETF_SELECT_MAPPINGS`。将使用预设的自选ETF列表。")
    ETF_SELECT_MAPPINGS = {
        "纳指ETF": "513100", "沪深300": "510300", "黄金ETF": "518880",
    }


st.set_page_config(page_title="ETF极值点靠近分析 (ATR)", layout="wide")
st.title("🔎 批量ETF极值点靠近分析 (基于ATR)")
st.markdown("分析多个ETF当前价格是否接近其历史局部高点或低点（使用ATR判断靠近程度）。")

# --- 侧边栏参数配置 ---
st.sidebar.header("分析参数配置")

# 1. NEW: 选择ETF来源
st.sidebar.subheader("数据源选择")
etf_source = st.sidebar.radio(
    "选择ETF列表:",
    ("行业ETF", "自选ETF"),
    key="etf_source_choice",
    help="选择要分析的ETF列表来源。"
)

# 2. 历史数据获取年限
st.sidebar.subheader("数据周期")
history_years_options = [1, 2]
selected_history_years = st.sidebar.selectbox(
    "历史数据年限:", options=history_years_options, index=1,
    help="获取多少年的历史数据进行极值点计算。"
)

# 3. 极值点计算参数
st.sidebar.subheader("极值点识别参数")
peak_distance_default = 10
peak_distance_input_batch = st.sidebar.number_input(
    "最小峰间距 (天/数据点):", min_value=5, max_value=60, value=peak_distance_default, step=1,
    key="peak_dist_batch", help="识别的波峰/波谷之间至少相隔多少个交易日。"
)
peak_prominence_std_factor = st.sidebar.slider(
    "突起高度因子 (乘以标准差):", min_value=0.1, max_value=2.0, value=0.5, step=0.1,
    key="peak_prom_factor_batch", help="波峰/波谷的突起程度，以收盘价标准差的倍数衡量。"
)

# 4. 靠近分析参数 (基于ATR)
st.sidebar.subheader("靠近程度分析参数 (ATR)")
atr_period_proximity = st.sidebar.slider(
    "ATR周期 (用于靠近判断):", min_value=5, max_value=50, value=14, step=1,
    key="atr_period_prox_batch", help="计算ATR时使用的周期天数。"
)
atr_multiplier_options_prox = [1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0]
atr_multiplier_proximity = st.sidebar.selectbox(
    "靠近ATR倍数 (n):", options=atr_multiplier_options_prox, index=2,
    key="atr_multiplier_prox_batch", help="当前价格与极值点相差 n * ATR 以内被认为是“靠近”。"
)

# 5. 选择分析的极值类型
st.sidebar.subheader("分析类型")
analyze_maxima = st.sidebar.checkbox("分析靠近局部高点", value=True, key="analyze_max_batch")
analyze_minima = st.sidebar.checkbox("分析靠近局部低点", value=True, key="analyze_min_batch")

# 6. NEW: 选择结果展示方式
st.sidebar.subheader("结果展示方式")
display_mode = st.sidebar.radio(
    "选择结果展示方式:",
    ("联合显示", "分开显示"),
    index=0,  # 默认选择“联合显示”
    key="display_mode_choice"
)

# 7. 分析按钮
analyze_button = st.sidebar.button("🚀 开始批量分析", key="analyze_extremes_btn")


# --- 数据获取与处理函数 ---
@st.cache_data(ttl=86400)
def fetch_raw_etf_data_with_atr(etf_code, years_of_history, atr_period_for_calc):
    """获取ETF原始OHLC数据并计算ATR。"""
    add_debug_log(f"Fetching raw data & ATR for {etf_code}, {years_of_history} years, ATR({atr_period_for_calc})")
    end_date = datetime.now()
    start_date = end_date - timedelta(days=int(years_of_history * 365.25))
    start_str = start_date.strftime('%Y%m%d')
    end_str = end_date.strftime('%Y%m%d')
    try:
        df = ak.fund_etf_hist_em(symbol=etf_code, period="daily", start_date=start_str, end_date=end_str, adjust="qfq")
        if df.empty or not all(col in df.columns for col in ['收盘', '最高', '最低']):
            return pd.DataFrame(), f"数据不足或缺少必要列(收盘/最高/最低) for {etf_code}"

        df['日期'] = pd.to_datetime(df['日期']).dt.normalize()
        df.set_index('日期', inplace=True)
        rename_map = {'开盘': 'Open', '最高': 'High', '最低': 'Low', '收盘': 'Close', '成交量': 'Volume'}
        df.rename(columns=rename_map, inplace=True)
        
        cols_to_numeric = ['Open', 'High', 'Low', 'Close', 'Volume']
        for col in cols_to_numeric:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')

        df.dropna(subset=['High', 'Low', 'Close'], inplace=True)

        if len(df) <= atr_period_for_calc:
            df['ATR'] = np.nan
            add_debug_log(f"Data points ({len(df)}) insufficient for ATR({atr_period_for_calc}) for {etf_code}. ATR set to NaN.")
            return df, f"数据点不足以计算ATR for {etf_code}" if df.empty else None
        
        # df['ATR'] = talib.ATR(df['High'].astype(float), df['Low'].astype(float), df['Close'].astype(float), timeperiod=atr_period_for_calc)
        # 如果您想自定义新列的名称，可以这样做：
        df['ATR'] = df.ta.atr(high='High', low='Low', close='Close', length=atr_period_for_calc)
        
        return df, None
    except Exception as e:
        return pd.DataFrame(), f"获取或计算ATR for {etf_code} 出错: {e}"

@st.cache_data(ttl=7200)
def find_extremes_from_series(etf_code, close_series, p_dist, p_prom_factor):
    """从已获取的收盘价序列中计算极值点。"""
    add_debug_log(f"Finding extremes for {etf_code} with p_dist={p_dist}, p_prom_factor={p_prom_factor}")
    if close_series.empty:
        return None, None, f"无收盘价序列 for {etf_code}"

    if len(close_series) < p_dist * 2:
        return None, None, f"数据点不足 ({len(close_series)}) for {etf_code} to find peaks with distance {p_dist}"

    price_std = close_series.std()
    actual_prominence = price_std * p_prom_factor if price_std > 0.00001 else 0.01

    try:
        max_locs, _ = find_peaks(close_series, distance=p_dist, prominence=actual_prominence)
        max_points_data = [(close_series.index[loc], close_series.iloc[loc]) for loc in max_locs]

        min_locs, _ = find_peaks(-close_series, distance=p_dist, prominence=actual_prominence)
        min_points_data = [(close_series.index[loc], close_series.iloc[loc]) for loc in min_locs]
        
        return max_points_data, min_points_data, None
    except Exception as e:
        return None, None, f"find_peaks for {etf_code} 出错: {e}"

# --- 主逻辑 ---
if analyze_button:
    # 1. 根据选择确定要分析的ETF列表
    if etf_source == "行业ETF":
        selected_etf_map = ETF_INDUSTRY_MAPPINGS
    else: # 自选ETF
        selected_etf_map = ETF_SELECT_MAPPINGS
    
    if not selected_etf_map:
        st.error(f"选择的 “{etf_source}” 列表为空，无法进行分析。请检查 `etf_industry_map.py`。")
    elif not analyze_maxima and not analyze_minima:
        st.warning("请至少选择一种分析类型（靠近局部高点或靠近局部低点）。")
    else:
        etf_codes_to_analyze = list(selected_etf_map.values())
        total_etfs = len(etf_codes_to_analyze)
        
        # 初始化结果存储列表
        results_near_maxima = []
        results_near_minima = []
        all_results = []
        
        progress_bar = st.progress(0)
        status_text = st.empty()

        for i, etf_code_iter in enumerate(etf_codes_to_analyze):
            etf_name = [k for k, v in selected_etf_map.items() if v == etf_code_iter][0] or "N/A"
            status_text.info(f"正在分析: {etf_name} ({etf_code_iter}) - [{i+1}/{total_etfs}]")

            df_etf_full, fetch_error = fetch_raw_etf_data_with_atr(
                etf_code_iter, selected_history_years, atr_period_proximity
            )
            if fetch_error or df_etf_full.empty:
                st.caption(f"跳过 {etf_code_iter}: {fetch_error or '无有效数据'}")
                progress_bar.progress((i + 1) / total_etfs)
                continue
            
            close_prices_series = df_etf_full['Close']
            
            maxima, minima, extremes_error = find_extremes_from_series(
                etf_code_iter, close_prices_series, peak_distance_input_batch, peak_prominence_std_factor
            )
            if extremes_error:
                st.caption(f"跳过 {etf_code_iter} (极值点识别): {extremes_error}")
                progress_bar.progress((i + 1) / total_etfs)
                continue

            if df_etf_full.empty or 'Close' not in df_etf_full.columns or 'ATR' not in df_etf_full.columns:
                st.caption(f"跳过 {etf_code_iter}: 数据不完整无法进行靠近分析。")
                progress_bar.progress((i + 1) / total_etfs)
                continue

            current_price = df_etf_full['Close'].iloc[-1]
            current_atr = df_etf_full['ATR'].iloc[-1]

            if pd.isna(current_price) or pd.isna(current_atr) or current_atr <= 0:
                st.caption(f"跳过 {etf_code_iter}: 当前价格或ATR无效 (Price: {current_price}, ATR: {current_atr})。")
                progress_bar.progress((i + 1) / total_etfs)
                continue

            # 分析靠近局部高点
            if analyze_maxima and maxima:
                for peak_date, peak_price in maxima:
                    upper_bound = peak_price + (atr_multiplier_proximity * current_atr)
                    lower_bound = peak_price - (atr_multiplier_proximity * current_atr)
                    if lower_bound <= current_price <= upper_bound:
                        proximity_in_atr = (current_price - peak_price) / current_atr if current_atr else np.nan
                        # 计算距离极大值的百分比
                        current_percent = (peak_price - current_price) / current_price * 100
                        result_item = {
                            "ETF代码": etf_code_iter,
                            "名称": etf_name,
                            "当前价格": current_price,
                            "极值点日期": peak_date.strftime('%Y-%m-%d'),
                            "极值点价格": peak_price,
                            "当前ATR": current_atr,
                            "距离ATR倍数": proximity_in_atr,
                            "距离百分比": current_percent
                        }
                        if display_mode == "联合显示":
                            result_item["分析类型"] = "靠近高点"
                            all_results.append(result_item)
                        else: # 分开显示
                            results_near_maxima.append(result_item)
            
            # 分析靠近局部低点
            if analyze_minima and minima:
                for valley_date, valley_price in minima:
                    upper_bound = valley_price + (atr_multiplier_proximity * current_atr)
                    lower_bound = valley_price - (atr_multiplier_proximity * current_atr)
                    if lower_bound <= current_price <= upper_bound:
                        proximity_in_atr = (current_price - valley_price) / current_atr if current_atr else np.nan
                        # 计算距离极小值的百分比
                        current_percent = (valley_price - current_price) / current_price * 100
                        result_item = {
                            "ETF代码": etf_code_iter,
                            "名称": etf_name,
                            "当前价格": current_price,
                            "极值点日期": valley_date.strftime('%Y-%m-%d'),
                            "极值点价格": valley_price,
                            "当前ATR": current_atr,
                            "距离ATR倍数": proximity_in_atr,
                            "距离百分比": current_percent
                        }
                        if display_mode == "联合显示":
                            result_item["分析类型"] = "靠近低点"
                            all_results.append(result_item)
                        else: # 分开显示
                            results_near_minima.append(result_item)

            progress_bar.progress((i + 1) / total_etfs)
        
        status_text.success(f"批量分析完成！共分析 {total_etfs} 个ETF。")

        # --- 显示结果 ---
        st.markdown("---")

        # 1. NEW: 创建并显示触及极值点的ETF名称摘要
        found_etf_names = set()
        # 从所有结果中收集ETF名称
        if display_mode == "联合显示":
            for item in all_results:
                found_etf_names.add(f"{item['名称']} ({item['ETF代码']})")
        else: # 分开显示模式
            for item in results_near_maxima:
                found_etf_names.add(f"{item['名称']} ({item['ETF代码']})")
            for item in results_near_minima:
                found_etf_names.add(f"{item['名称']} ({item['ETF代码']})")

        st.subheader("📣 触及极值点ETF一览")
        if found_etf_names:
            # 排序后显示，更清晰
            sorted_names = sorted(list(found_etf_names))
            # 使用多列布局以获得更好的视觉效果
            num_columns = 5
            cols = st.columns(num_columns)
            for i, name in enumerate(sorted_names):
                with cols[i % num_columns]:
                    st.success(name)
        else:
            st.info("本次分析未发现任何触及极值点的ETF。")
        
        st.markdown("---") # 添加分隔线，将摘要与详情分开

        if display_mode == "联合显示":
            st.subheader(f"📊 综合分析结果 (范围: 极值点 ± {atr_multiplier_proximity} * ATR)")
            if all_results:
                df_all = pd.DataFrame(all_results)
                # 格式化输出
                df_all['当前价格'] = df_all['当前价格'].map('{:.3f}'.format)
                df_all['极值点价格'] = df_all['极值点价格'].map('{:.3f}'.format)
                df_all['当前ATR'] = df_all['当前ATR'].map('{:.4f}'.format)
                df_all['距离ATR倍数'] = df_all['距离ATR倍数'].map('{:.2f}'.format)
                df_all['距离百分比'] = df_all['距离百分比'].map('{:.2f}'.format)
                # 调整列顺序
                cols_order = ["ETF代码", "名称", "分析类型", "当前价格", "极值点日期", "极值点价格", "当前ATR", "距离ATR倍数", "距离百分比"]
                st.dataframe(df_all[cols_order].reset_index(drop=True), use_container_width=True)
            else:
                st.info("没有找到符合条件（靠近局部高点或低点）的ETF。")

        else: # 分开显示
            if analyze_maxima:
                st.subheader(f"📈 靠近历史局部高点 (范围: ± {atr_multiplier_proximity} * ATR) 的ETF")
                if results_near_maxima:
                    df_max = pd.DataFrame(results_near_maxima)
                    df_max['当前价格'] = df_max['当前价格'].map('{:.3f}'.format)
                    df_max['极值点价格'] = df_max['极值点价格'].map('{:.3f}'.format)
                    df_max['当前ATR'] = df_max['当前ATR'].map('{:.4f}'.format)
                    df_max['距离ATR倍数'] = df_max['距离ATR倍数'].map('{:.2f}'.format)
                    df_max['距离百分比'] = df_max['距离百分比'].map('{:.2f}'.format)
                    st.dataframe(df_max.reset_index(drop=True), use_container_width=True)
                else:
                    st.info("没有找到符合条件（靠近局部高点）的ETF。")
                st.markdown("---")

            if analyze_minima:
                st.subheader(f"📉 靠近历史局部低点 (范围: ± {atr_multiplier_proximity} * ATR) 的ETF")
                if results_near_minima:
                    df_min = pd.DataFrame(results_near_minima)
                    df_min['当前价格'] = df_min['当前价格'].map('{:.3f}'.format)
                    df_min['极值点价格'] = df_min['极值点价格'].map('{:.3f}'.format)
                    df_min['当前ATR'] = df_min['当前ATR'].map('{:.4f}'.format)
                    df_min['距离ATR倍数'] = df_min['距离ATR倍数'].map('{:.2f}'.format)
                    df_min['距离百分比'] = df_min['距离百分比'].map('{:.2f}'.format)
                    st.dataframe(df_min.reset_index(drop=True), use_container_width=True)
                else:
                    st.info("没有找到符合条件（靠近局部低点）的ETF。")
        
        # --- 显示可折叠的调试日志 ---
        with st.expander("显示/隐藏 详细调试日志", expanded=False):
            if st.session_state.debug_logs:
                for log_entry in reversed(st.session_state.debug_logs):
                    st.code(log_entry, language=None)
                if st.button("清除调试日志", key="clear_debug_logs_btn"):
                    st.session_state.debug_logs = []
                    st.rerun()
            else:
                st.info("暂无调试日志。")
else:
    st.info("请在左侧配置参数，然后点击“开始批量分析”按钮。")