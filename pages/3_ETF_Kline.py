# pages/3_ETF_Kline_Chart.py
import streamlit as st
import akshare as ak
# import talib
import pandas_ta as ta # 导入库，通常简写为 ta
import numpy as np
import pandas as pd
import plotly.graph_objects as go # 使用 Plotly 绘制K线
from datetime import datetime, timedelta
from plotly.subplots import make_subplots
from scipy.signal import find_peaks # 导入 find_peaks


# 尝试导入映射，主要用于行业选择时预填ETF代码
try:
    from etf_industry_map import get_etf_for_industry, get_available_industries_with_etf
except ImportError:
    st.sidebar.warning("`etf_industry_map.py` 未找到。行业选择功能可能受限。")
    def get_etf_for_industry(industry_name): return None
    def get_available_industries_with_etf(): return []

st.set_page_config(page_title="ETF历史K线图", layout="wide")
st.title("📈 ETF 历史K线图查询与显示")
st.markdown("查询并显示指定ETF在特定时间范围内的历史日K线图、均线和成交量。")

# --- 侧边栏控件 ---
st.sidebar.header("参数配置")

# 1. 行业选择 (可选，用于辅助填充ETF代码)
available_industries = get_available_industries_with_etf()
selected_industry_for_etf = st.sidebar.selectbox(
    "选择行业以获取建议ETF代码:",
    options=[""] + available_industries, # 添加一个空选项作为默认
    index=0,
    help="选择一个行业，下方“指定ETF代码”框将尝试填充对应的ETF代码。"
)

# 2. 指定ETF代码 (文本输入)
default_etf_code = ""
if selected_industry_for_etf: # 如果选择了行业
    suggested_etf = get_etf_for_industry(selected_industry_for_etf)
    if suggested_etf:
        default_etf_code = suggested_etf

etf_code_input = st.sidebar.text_input(
    "指定ETF代码 (例如: 510300):",
    value=default_etf_code,
    key="etf_code_input_kline" # 为输入框提供一个唯一的key
)

# 3. 选择指定ETF (checkbox) - 这个控件的用途似乎与上面的文本输入有些重叠
# 如果意图是：勾选则使用文本框的ETF，不勾选则使用行业选择的ETF，可以这样设计
# 但目前的设计是行业选择辅助文本框，文本框是最终输入。
# 我们先按“文本输入框是最终决定ETF代码”的方式设计。
# 如果有其他意图，请告知。
# use_specified_etf_code = st.sidebar.checkbox(
#     "使用上方指定的ETF代码",
#     value=True, # 默认勾选，表示使用文本框输入
#     help="如果不勾选，且选择了行业，则尝试使用行业对应的ETF。"
# )
# 暂时注释掉上面这个checkbox，因为它的逻辑与当前流程不太明确。
# 当前：行业选择 -> 填充文本框建议值 -> 文本框是最终的ETF代码来源。

# 4. 时间范围选择
st.sidebar.markdown("---")
st.sidebar.subheader("时间范围")

use_default_time_range = st.sidebar.checkbox(
    "使用默认时间范围 (近2年)",
    value=True, # 默认勾选
    key="default_time_kline"
)

custom_start_date = None
custom_end_date = None

if use_default_time_range:
    end_date = datetime.now()
    start_date = end_date - timedelta(days=2*365) # 近2年
    # 在UI上禁用日期选择器，但仍显示默认值
    st.sidebar.date_input("开始日期 (默认):", start_date, disabled=True)
    st.sidebar.date_input("结束日期 (默认):", end_date, disabled=True)
else:
    default_custom_end_date = datetime.now()
    default_custom_start_date = default_custom_end_date - timedelta(days=30) # 默认自定义为近30天
    custom_start_date = st.sidebar.date_input("选择开始日期:", default_custom_start_date)
    custom_end_date = st.sidebar.date_input("选择结束日期:", default_custom_end_date)
    start_date = custom_start_date
    end_date = custom_end_date

st.sidebar.markdown("---")
st.sidebar.subheader("ATR 止损参考 (做多)")
atr_period_input = st.sidebar.slider("ATR周期 (天):", min_value=5, max_value=50, value=14, step=1, key="atr_p_k")
atr_multiplier_options = [1.0, 1.5, 2.0, 2.5, 3.0] # 增加选项
atr_multiplier_input = st.sidebar.selectbox("ATR倍数:", atr_multiplier_options, index=2, key="atr_m_k") # 默认2.0倍

refresh_button = st.sidebar.button("🔄 获取并显示K线数据", key="refresh_kline_data_btn")

# --- 数据获取与绘图逻辑 ---
@st.cache_data(ttl=3600) # 缓存1小时
def fetch_etf_kline_data(etf_code, start_date_dt, end_date_dt, atr_p_val = 14):
    """获取并处理ETF的K线数据，计算均线。"""
    if not etf_code:
        return pd.DataFrame(), "请输入有效的ETF代码。"

    start_str = start_date_dt.strftime('%Y%m%d')
    end_str = end_date_dt.strftime('%Y%m%d')

    try:
        df = ak.fund_etf_hist_em(symbol=etf_code, period="daily", start_date=start_str, end_date=end_str, adjust="qfq")
        if df.empty:
            return pd.DataFrame(), f"未能获取到ETF {etf_code} 在指定日期范围的数据。"

        # df['日期'] = pd.to_datetime(df['日期'])
        df.set_index('日期', inplace=True)
        df.rename(columns={'开盘': 'Open', '最高': 'High', '最低': 'Low', '收盘': 'Close', '成交量': 'Volume'}, inplace=True)
        
        # 数据类型转换，确保OHLCV是数值
        for col in ['Open', 'High', 'Low', 'Close', 'Volume']:
            df[col] = pd.to_numeric(df[col], errors='coerce')
        df.dropna(subset=['Open', 'High', 'Low', 'Close'], inplace=True) # 删除OHLC有空值的行

        if df.empty: # 再次检查，因为dropna可能导致为空
             return pd.DataFrame(), f"数据清洗后，ETF {etf_code} 无有效数据。"

        # 计算均线 (示例：MA5, MA20)
        df['MA5'] = df['Close'].rolling(window=5).mean()
        df['MA20'] = df['Close'].rolling(window=20).mean()

        if len(df) > atr_p_val : # 确保数据长度足够
            # df['ATR'] = talib.ATR(df['High'].astype(float),
            #                       df['Low'].astype(float),
            #                       df['Close'].astype(float),
            #                       timeperiod=atr_p_val)
            df['ATR'] = df.ta.atr(high='High', low='Low', close='Close', length=atr_p_val)
        else:
            df['ATR'] = np.nan # 数据不足则填充NaN

        return df, None # 返回DataFrame和None表示无错误
    except Exception as e:
        return pd.DataFrame(), f"获取或处理ETF {etf_code} 数据时出错: {e}"


# --- K线图绘制函数 ---
def plot_kline_with_extremes(df_etf, etf_code_display, peak_dist, peak_prom):
    """使用Plotly绘制K线图、均线和成交量。"""
    if df_etf.empty:
        st.warning("没有可供绘制的ETF数据。")
        return

    fig = make_subplots(rows=2, cols=1, shared_xaxes=True,
                        vertical_spacing=0.05, # 减少垂直间距
                        row_heights=[0.75, 0.25],
                        specs=[[{"secondary_y": False}], # 主K线图区域，成交量在副图
                               [{"secondary_y": False}]]) # 成交量图区域

    # 1. K线图
    fig.add_trace(go.Candlestick(x=df_etf.index,
                                 open=df_etf['Open'], high=df_etf['High'],
                                 low=df_etf['Low'], close=df_etf['Close'],
                                 name='K-Line',
                                 increasing_line_color='red',
                                 decreasing_line_color='green'),
                  row=1, col=1)

    # 2. 均线
    if 'MA5' in df_etf.columns:
        fig.add_trace(go.Scatter(x=df_etf.index, y=df_etf['MA5'], mode='lines', name='MA5', line=dict(color='orange', width=1)),
                      row=1, col=1)
    if 'MA20' in df_etf.columns:
        fig.add_trace(go.Scatter(x=df_etf.index, y=df_etf['MA20'], mode='lines', name='MA20', line=dict(color='purple', width=1)),
                      row=1, col=1)

    # 3. 成交量 (在第二个子图)
    # 根据涨跌决定成交量颜色：当天收盘价 > 开盘价 则红色，否则绿色
    volume_colors = ['red' if row['Close'] >= row['Open'] else 'green' for index, row in df_etf.iterrows()]
    fig.add_trace(go.Bar(x=df_etf.index, y=df_etf['Volume'], name='Volume', marker_color=volume_colors),
                  row=2, col=1)

    # --- 寻找并标记极值点 ---
    close_prices = df_etf['Close']
    if len(close_prices) > peak_dist:  # 确保数据足够进行find_peaks
        # 极大值 (波峰)
        max_locs, _ = find_peaks(close_prices, distance=peak_dist, prominence=peak_prom)
        if len(max_locs) > 0:
            fig.add_trace(go.Scatter(
                x=df_etf.index[max_locs], 
                y=close_prices.iloc[max_locs],
                mode='markers', 
                name='局部高点',
                marker=dict(
                    color='rgba(255, 127, 80, 0.0)',  # 核心：设置填充色为完全透明
                    size=12,                           # 稍微增大尺寸以突出边框
                    symbol='circle',                   # 使用实心圆符号
                    line=dict(
                        width=2,                       # 边框宽度
                        color='orangered'              # 边框颜色：亮眼的橙红色
                    )
                )
            ), row=1, col=1)

        # 极小值 (波谷)
        min_locs, _ = find_peaks(-close_prices, distance=peak_dist, prominence=peak_prom)
        if len(min_locs) > 0:
            fig.add_trace(go.Scatter(
                x=df_etf.index[min_locs], 
                y=close_prices.iloc[min_locs],
                mode='markers', 
                name='局部低点',
                marker=dict(
                    color='rgba(0, 206, 209, 0.0)',   # 核心：设置填充色为完全透明
                    size=12,                           # 稍微增大尺寸以突出边框
                    symbol='circle',                   # 使用实心圆符号
                    line=dict(
                        width=2,                       # 边框宽度
                        color='darkturquoise'          # 边框颜色：明亮的青色
                    )
                )
            ), row=1, col=1)

    fig.update_layout(
        title_text=f"{etf_code_display} 日K线图",
        height=700,
        xaxis_rangeslider_visible=False, # 隐藏K线图下方的滑块
        legend_orientation="h", legend_yanchor="bottom", legend_y=1.02, legend_xanchor="right", legend_x=1
    )

    # --- MODIFIED: X轴日期显示格式和频率 ---
    date_format = '%Y-%m-%d' # 日期格式：年-月-日
    # 尝试按月显示，如果数据范围过小，Plotly会自动调整
    # dtick="M1" 表示每个月一个主刻度。L1表示每月第一天。
    # 如果数据量很大，每月一个可能还是太多，可以考虑 "M3" (每季度) 或 nticks

    # X轴设置 (处理非交易日，让K线连续)
    fig.update_xaxes(
        type='category', # 使用category类型可以帮助更好地处理非连续日期
        rangebreaks=[dict(bounds=["sat", "sun"])], # 隐藏周末
        tickformat=date_format, # 应用日期格式
        # tickmode='auto', # 或者 'linear' 配合 dtick
        # dtick="M1", # 尝试每月一个刻度
        nticks=12, # 或者建议显示12个左右的刻度，让Plotly自动找合适月份
        row=1, col=1
    )
    fig.update_xaxes(
        type='category', # 确保底部X轴标签与K线图对齐且处理非交易日
        rangebreaks=[dict(bounds=["sat", "sun"])],
        tickformat=date_format, # 应用日期格式
        # dtick="M1",
        nticks=12,
        row=2, col=1,
        title_text="日期"
    )

    fig.update_yaxes(title_text="价格", row=1, col=1)
    fig.update_yaxes(title_text="成交量", row=2, col=1)

    st.plotly_chart(fig, use_container_width=True)

# --- 主逻辑：当按钮被点击或输入变化时执行 ---
# Streamlit中，输入控件的任何变化都会导致脚本重新运行。
# 我们可以直接使用 etf_code_input 和日期变量。
# 按钮主要用于强制重新获取数据（例如清除缓存）。

if refresh_button: # 如果按钮被点击
    st.cache_data.clear() # 清除所有缓存的数据
    # 重新运行页面以确保使用最新的输入值并重新获取数据
    # st.rerun() # st.rerun()会立即执行，可能导致下面的逻辑不完整

# 获取最终的ETF代码
final_etf_code = etf_code_input.strip() # 去除首尾空格

if final_etf_code: # 只有当有ETF代码时才尝试获取和绘图

    st.markdown(f"#### ETF: {final_etf_code} | 时间: {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}")

    df_etf_data, error_message = fetch_etf_kline_data(final_etf_code, start_date, end_date, atr_period_input)

    if error_message:
        st.error(error_message)
    elif df_etf_data.empty:
        st.warning(f"未找到ETF {final_etf_code} 的数据或数据为空。")
    else:
        # --- 极值点参数输入 ---
        st.subheader("局部极值点参数设置")
        cols_peaks = st.columns(2)
        # 动态计算默认prominence
        price_std_default = df_etf_data['Close'].std() if not df_etf_data.empty else 0.1
        default_prominence = round(price_std_default * 0.5, 4) if price_std_default > 0 else 0.05


        with cols_peaks[0]:
            peak_distance_input = st.number_input(
                "最小峰间距 (天/数据点数):",
                min_value=1, max_value=len(df_etf_data)//2 if len(df_etf_data)>2 else 1, # 避免过大
                value=10, step=1, key="peak_dist_k",
                help="寻找的波峰/波谷之间至少相隔多少个数据点。"
            )
        with cols_peaks[1]:
            peak_prominence_input = st.number_input(
                "最小突起高度 (价格单位):",
                min_value=0.0001, value=float(default_prominence), step=0.01, format="%.4f", key="peak_prom_k",
                help="波峰需要比周围高出多少，或波谷需要比周围低多少才被识别。基于0.5*收盘价标准差计算默认值。"
            )

        # --- 绘制K线图（现在包含极值点） ---
        plot_kline_with_extremes(df_etf_data, final_etf_code, peak_distance_input, peak_prominence_input)

        # --- ATR 和止损信息显示 ---
        st.markdown("---")
        st.subheader(f"ATR({atr_period_input}) 止损参考 (基于最新数据)")
        latest_data_main = df_etf_data.iloc[-1]
        latest_close_main = latest_data_main['Close']
        latest_atr_main = latest_data_main.get('ATR', np.nan) # 使用 .get 以防ATR列不存在

        cols_atr = st.columns(4)
        with cols_atr[0]:
            st.metric(label="最新收盘价", value=f"{latest_close_main:.3f}" if pd.notna(latest_close_main) else "N/A")
        with cols_atr[1]:
            st.metric(label=f"最新ATR({atr_period_input})", value=f"{latest_atr_main:.3f}" if pd.notna(latest_atr_main) else "N/A")

        if pd.notna(latest_close_main) and pd.notna(latest_atr_main) and latest_atr_main > 0: # 确保ATR有效
            stop_loss_price_main = latest_close_main - (atr_multiplier_input * latest_atr_main)
            stop_loss_percentage_main = ((latest_close_main - stop_loss_price_main) / latest_close_main) * 100
            with cols_atr[2]:
                st.metric(label=f"止损价 ({atr_multiplier_input}x ATR)", value=f"{stop_loss_price_main:.3f}")
            with cols_atr[3]:
                st.metric(label="止损百分比", value=f"{stop_loss_percentage_main:.3f}%")
            st.caption(f"计算公式: 止损价 = 收盘价 - (ATR倍数 * ATR({atr_period_input}))。")
        else:
            with cols_atr[2]:
                st.metric(label=f"止损价 ({atr_multiplier_input}x ATR)", value="N/A")
            with cols_atr[3]:
                st.metric(label="止损百分比", value="N/A")
            if not (pd.notna(latest_atr_main) and latest_atr_main > 0):
                st.caption("ATR值无效或为0，无法计算止损。")
        st.caption("ATR止损信息仅供参考，不构成投资建议。")
        st.markdown("---")
else:
    if refresh_button: # 如果点击了按钮但没有输入ETF代码
        st.warning("请输入有效的ETF代码后再点击获取。")
    else: # 页面加载时，如果输入框为空
        st.info("请在左侧配置参数并输入ETF代码，然后点击“获取并显示K线数据”按钮。")
