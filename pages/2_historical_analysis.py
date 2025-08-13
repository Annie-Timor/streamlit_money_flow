# pages/2_Historical_Analysis.py
import streamlit as st
import akshare as ak
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime, timedelta

# 尝试从同级目录导入映射 (如果 streamlit run 从项目根目录运行)
try:
    from etf_industry_map import get_etf_for_industry, get_available_industries_with_etf
except ImportError:
    # 如果直接运行此文件或导入失败，提供备用方案或提示
    st.warning("etf_industry_map.py 未找到或导入失败。将使用预设的行业列表和映射。")
    # 备用映射 (与 etf_industry_map.py 中的内容一致)
    ETF_INDUSTRY_MAPPINGS_FALLBACK = {
        "半导体": "512480", "医疗器械": "159883", "酿酒行业": "512690",
        "银行": "512800", "证券": "512880", "光伏设备": "159863",
        "电力行业": "159611", "通信服务": "159695", "电子元件": "515320",
    }
    def get_etf_for_industry(industry_name):
        return ETF_INDUSTRY_MAPPINGS_FALLBACK.get(industry_name)
    def get_available_industries_with_etf():
        return list(ETF_INDUSTRY_MAPPINGS_FALLBACK.keys())


st.set_page_config(page_title="历史资金流与ETF对比", layout="wide")
st.title("📜 行业历史资金流向与对应ETF涨跌对比")

# --- 侧边栏选择 ---
available_industries = get_available_industries_with_etf()
if not available_industries:
    st.sidebar.error("没有可用的行业ETF映射数据。请检查 `etf_industry_map.py`。")
    st.stop() # 如果没有行业可选，停止执行

selected_industry = st.sidebar.selectbox(
    "选择行业:",
    options=[""] + available_industries,
    index=0
)
etf_code = ""
if selected_industry:
    etf_code = get_etf_for_industry(selected_industry)

# 日期范围选择
default_end_date = datetime.now()
default_start_date = default_end_date - timedelta(days=365) # 默认一年

start_date_input = st.sidebar.date_input("开始日期", default_start_date)
end_date_input = st.sidebar.date_input("结束日期", default_end_date)

# 将日期转换为AkShare所需的格式 'YYYYMMDD'
start_date_str = start_date_input.strftime('%Y%m%d')
end_date_str = end_date_input.strftime('%Y%m%d')


# --- 数据获取 ---
@st.cache_data(ttl=3600) # 缓存数据1小时
def fetch_etf_history(etf_code_param, start, end):
    """获取ETF历史行情"""
    try:
        # fund_etf_hist_em 获取的是ETF历史行情
        df = ak.fund_etf_hist_em(symbol=etf_code_param, period="daily", start_date=start, end_date=end, adjust="qfq")
        if df.empty:
            return pd.DataFrame()
        # df['日期'] = pd.to_datetime(df['日期'])
        df.set_index('日期', inplace=True)
        # AkShare 返回的列名是中文，Plotly K线图需要 'Open', 'High', 'Low', 'Close'
        df.rename(columns={'开盘': 'Open', '最高': 'High', '最低': 'Low', '收盘': 'Close', '成交量': 'Volume'}, inplace=True)
        return df[['Open', 'High', 'Low', 'Close', 'Volume']]
    except Exception as e:
        st.error(f"获取ETF {etf_code_param} 行情失败: {e}")
        return pd.DataFrame()

@st.cache_data(ttl=3600)
def fetch_industry_flow_history(industry_name_param):
    """
    获取行业历史资金流。
    注意: AkShare 中直接获取精确的【板块/行业】日度历史资金流的接口可能不直接，
    或者返回的不是每日净流入额。
    `stock_board_fund_flow_hist_em` 可获取板块成分股资金流汇总历史。
    你需要根据 `industry_name_param` 找到对应的板块代码 (e.g., "BK0475" for 半导体).
    这个映射可能需要额外维护。
    """
    st.info(f"正在尝试获取“{industry_name_param}”板块的历史资金流。这可能需要板块代码。")
    
    try:
        df = ak.stock_sector_fund_flow_hist(symbol=industry_name_param)
        if df.empty:
            return pd.DataFrame()
        # df['日期'] = pd.to_datetime(df['日期'])
        df.set_index('日期', inplace=True)
        # 数据清洗和格式化 (例如，将金额从元转换为亿元)
        amount_cols = [col for col in df.columns if '净额' in col or '金额' in col]
        for col in amount_cols:
            if df[col].dtype in ['float64', 'int64']:
                df[col] = (df[col] / 1e8).round(3)
        df.rename(columns={'主力净流入-净额': '主力净流入亿元'}, inplace=True)
        return df
    except Exception as e:
        st.error(f"获取行业“{industry_name_param}”历史资金流失败: {e}")
        return pd.DataFrame()


# --- 主区域显示 ---
if not etf_code:
    # st.error(f"未找到行业“{selected_industry}”对应的ETF代码。请在 `etf_industry_map.py` 中配置。")
    st.write("请从侧边栏选择一个行业。")
else:
    st.markdown(f"### 行业: {selected_industry} (ETF: {etf_code})")

    df_industry_flow = fetch_industry_flow_history(selected_industry)
    start_date_str = df_industry_flow.index[0].strftime('%Y%m%d')
    end_date_str = df_industry_flow.index[-1].strftime('%Y%m%d')
    df_etf_hist = fetch_etf_history(etf_code, start_date_str, end_date_str)
    st.markdown(f"日期范围: {start_date_str} 到 {end_date_str}")
    

    if df_etf_hist.empty or df_industry_flow.empty:
        st.warning("未能加载ETF历史行情数据或行业资金流数据。") # 修改了提示信息
    else:
        # --- 绘图 ---
        fig = make_subplots(rows=2, cols=1, shared_xaxes=True,
                            vertical_spacing=0.1, row_heights=[0.7, 0.3],
                            specs=[[{"secondary_y": True}],  # MODIFIED: 为第一个子图指定次Y轴
                                   [{"secondary_y": False}]])

        # 1. ETF K线图
        fig.add_trace(go.Candlestick(x=df_etf_hist.index,
                                     open=df_etf_hist['Open'],
                                     high=df_etf_hist['High'],
                                     low=df_etf_hist['Low'],
                                     close=df_etf_hist['Close'],
                                     name=f'{etf_code} K线',
                                     increasing_line_color='red',  # MODIFIED: 上涨红色
                                     decreasing_line_color='green' # MODIFIED: 下跌绿色
                                    ),
                      row=1, col=1)

        # 将成交量柱状图添加到第一个子图的次Y轴
        fig.add_trace(go.Bar(x=df_etf_hist.index,
                             y=df_etf_hist['Volume'],
                             name='成交量',
                             marker_color='rgba(100,100,100,0.4)'),
                      secondary_y=True, row=1, col=1) # secondary_y=True

        # 为第一个子图的主Y轴和次Y轴设置标题
        # Plotly 会自动命名次Y轴为 yaxis2, yaxis3 等，取决于它在哪个子图和是第几个次轴
        # 对于 subplot(row=1, col=1) 的第一个次Y轴，它通常是 'yaxis2'
        # 如果不确定，可以先不设置 fig.update_layout 中的 yaxis2_title，
        # 而是用 fig.update_yaxes(title_text="成交量", secondary_y=True, row=1, col=1)
        fig.update_yaxes(title_text=f'{etf_code} 价格', secondary_y=False, row=1, col=1)
        fig.update_yaxes(title_text="成交量", secondary_y=True, row=1, col=1, showgrid=False)


        # 2. 行业资金流柱状图 (这个子图不需要次Y轴)
        if not df_industry_flow.empty and '主力净流入亿元' in df_industry_flow.columns:
            # 确保 '主力净流入亿元' 列是数值类型，以防万一
            df_industry_flow['主力净流入亿元'] = pd.to_numeric(df_industry_flow['主力净流入亿元'], errors='coerce')
            df_industry_flow.dropna(subset=['主力净流入亿元'], inplace=True) # 移除无法转换的行

            colors = ['red' if val >= 0 else 'green' for val in df_industry_flow['主力净流入亿元']]
            fig.add_trace(go.Bar(x=df_industry_flow.index,
                                 y=df_industry_flow['主力净流入亿元'],
                                 name='主力资金净流入(亿元)',
                                 marker_color=colors),
                          row=2, col=1) # 这个子图没有 secondary_y=True
            fig.update_yaxes(title_text="资金净流入(亿元)", row=2, col=1) # 为第二个子图的Y轴设置标题
        else:
            st.info("无行业历史资金流数据可供绘制或数据格式不符。")

        fig.update_layout(
            height=700,
            title_text=f"{selected_industry} ({etf_code}) 与 主力资金流向",
            xaxis_rangeslider_visible=False,
            legend_orientation="h",
            legend_yanchor="bottom",
            legend_y=1.02,
            legend_xanchor="right",
            legend_x=1
        )
        # 确保K线图的x轴标签显示 (通常默认会显示，但显式设置无害)
        fig.update_xaxes(type='category', # 使用category类型可以帮助更好地处理非连续日期
                        rangebreaks=[dict(bounds=["sat", "sun"])], # 隐藏周末
                        nticks=12, # 或者建议显示12个左右的刻度，让Plotly自动找合适月份
                        showticklabels=True, row=1, col=1)
        # 最后一个子图（资金流图）显示x轴标题
        fig.update_xaxes(title_text="日期",
                         type='category', # 确保底部X轴标签与K线图对齐且处理非交易日
                         rangebreaks=[dict(bounds=["sat", "sun"])],
                         nticks=12,
                         row=2, col=1)

        st.plotly_chart(fig, use_container_width=True)

# 刷新按钮
if st.button("🔄 刷新图表数据"):
    st.cache_data.clear()
    st.rerun()