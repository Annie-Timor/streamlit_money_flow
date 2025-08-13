# app.py
import streamlit as st

st.set_page_config(
    page_title="资金流向分析平台",
    page_icon="💰",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.sidebar.success("请从上方选择一个分析页面。")

st.title("欢迎来到资金流向分析平台 💰")
st.markdown(
    """
    本平台提供实时的板块资金流向查看以及行业历史资金流与ETF表现的对比分析。

    **请使用左侧导航栏选择您感兴趣的功能页面。**

    ### 功能简介:
    - **实时资金流**: 查看今日、近5日、近10日各大板块的资金流入/流出排名情况。
    - **历史分析与ETF对比**: 选择特定行业，查看其历史资金流向，并与该行业相关的ETF历史K线图进行对比。

    *数据来源: AkShare*
    """
)

# 你可以在这里添加一些全局的说明或者平台介绍