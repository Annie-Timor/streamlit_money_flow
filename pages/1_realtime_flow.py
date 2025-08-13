# pages/1_Realtime_Flow.py
import streamlit as st
import akshare as ak
import pandas as pd

# 尝试从项目根目录的 etf_industry_map.py 导入 (假设 streamlit run 从项目根目录运行)
try:
    from etf_industry_map import ETF_INDUSTRY_MAPPINGS # 我们需要这个字典的键
except ImportError:
    st.sidebar.warning("`etf_industry_map.py` 未找到或导入失败。筛选功能可能受限。")
    # 提供一个空的备用列表，这样代码不会直接报错，但筛选功能将无效
    ETF_INDUSTRY_MAPPINGS = {}

st.set_page_config(page_title="实时板块资金流", layout="wide") # 单独设置页面配置（可选）
st.title("📊 实时板块资金流向")
st.markdown("查看不同时间维度下各板块的资金流入/流出排名。")

# --- 侧边栏选择 ---
indicator_options = {
    "今日": "今日",
    "近5日": "5日",
    "近10日": "10日"
}
selected_indicator_display = st.sidebar.selectbox(
    "选择时间维度:",
    options=list(indicator_options.keys()),
    index=0 # 默认选择 "今日"
)
ak_indicator_param = indicator_options[selected_indicator_display]

# --- 新增：Checkbox 用于筛选 ---
# 获取已映射的行业名称列表
mapped_industries = list(ETF_INDUSTRY_MAPPINGS.keys())

show_mapped_only = st.sidebar.checkbox(
    "仅显示已映射ETF的板块",
    value=False, # 默认不勾选，显示全部
    help="勾选此项后，将只显示在 `etf_industry_map.py` 中已配置对应ETF的板块资金流。"
)

# --- 数据获取与显示 ---
@st.cache_data(ttl=300) # 缓存数据5分钟
def fetch_realtime_flow_data(indicator):
    """获取实时板块资金流数据"""
    try:
        df = ak.stock_sector_fund_flow_rank(indicator=indicator)
        # 数据清洗和格式化 (例如，将金额从元转换为亿元)
        amount_cols = [col for col in df.columns if '净额' in col or '金额' in col]
        for col in amount_cols:
            if df[col].dtype in ['float64', 'int64']:
                df[col] = (df[col] / 1e8).round(3)
        # 你可以根据需要重命名列名，使其更易读
        # df.rename(columns={'old_name': '新名称'}, inplace=True)
        return df
    except Exception as e:
        st.error(f"获取数据失败 ({indicator}): {e}")
        return pd.DataFrame()

st.markdown(f"### {selected_indicator_display}板块资金流向排名")

df_flow_raw = fetch_realtime_flow_data(ak_indicator_param)

if not df_flow_raw.empty:
    df_to_display = df_flow_raw.copy() # 创建副本进行操作

    # 根据 checkbox 的状态进行筛选
    if show_mapped_only:
        if mapped_industries:
            # 假设AkShare返回的DataFrame中板块名称在名为“名称”的列
            # 你需要确认 `ak.stock_sector_fund_flow_rank` 返回的DataFrame中包含板块名称的列名
            # 通常是第一列或第二列，列名可能是 '名称', '板块' 等
            name_column = None
            if '名称' in df_to_display.columns: # 常见的列名
                name_column = '名称'
            elif '板块' in df_to_display.columns: # 另一种可能的列名
                name_column = '板块'
            # 你可能需要根据实际返回的列名调整这里
            # 如果不确定，可以先打印 df_flow_raw.columns 查看

            if name_column:
                df_to_display = df_to_display[df_to_display[name_column].isin(mapped_industries)]
                if df_to_display.empty:
                    st.info(f"在“{selected_indicator_display}”数据中，未找到与 `etf_industry_map.py` 中已映射ETF相匹配的板块。")
            else:
                st.warning("无法在数据中识别板块名称列，无法按已映射ETF筛选。将显示所有板块。")
        else:
            st.info("`etf_industry_map.py` 中没有配置任何ETF映射，将显示所有板块。")

    # 移除之前的高亮逻辑，直接显示DataFrame
    if not df_to_display.empty:
        st.dataframe(df_to_display.reset_index(drop=True), use_container_width=True, height=600, hide_index=True)
        st.caption(f"数据说明：金额单位已转换为“亿元”。")
        if show_mapped_only:
            st.caption(f"当前仅显示 {len(df_to_display)} 个已配置ETF的板块。共有 {len(mapped_industries)} 个已配置的映射。")
        else:
            st.caption(f"当前显示所有 {len(df_to_display)} 个板块。")

    elif df_to_display.empty and show_mapped_only: # 如果筛选后为空，但原始数据不为空
        pass # 提示信息已在筛选逻辑中处理
    else: # 如果原始数据就为空（或筛选后因其他原因也为空）
        st.warning("未能加载数据，或筛选后无数据显示。")


else:
    st.warning("未能加载数据，请稍后再试或检查网络连接。")

# 添加一个刷新按钮
if st.sidebar.button("🔄 刷新数据"):
    st.cache_data.clear() # 清除缓存，以便下次获取最新数据
    st.rerun()