@echo off
REM =================================================================
REM == Streamlit 应用自启动脚本 (start_streamlit.bat) - V2
REM == 兼容新版 Conda 激活方式
REM =================================================================

ECHO Starting Streamlit App...

REM --- 关键步骤1: 设置 Conda 的基础路径 ---
REM 这里设置为你的 Anaconda/Miniconda 的主安装目录。
SET "CONDA_BASE=C:\ProgramData\anaconda3"

REM --- 关键步骤2: 调用 Conda 的 hook 来初始化环境 ---
REM 这一步相当于在命令行里执行 `conda init` 后续的环境准备工作。
call "%CONDA_BASE%\Scripts\activate.bat" base

REM --- 关键步骤3: 激活你的目标环境 ---
REM 现在，在初始化完成后，我们可以安全地激活 `trade` 环境。
call conda activate trade

REM --- 关键步骤4: 切换到脚本所在的目录 ---
REM %~dp0 是一个神奇的变量，代表此.bat文件所在的文件夹路径。
cd /d %~dp0

ECHO Current Directory: %cd%
ECHO Starting Streamlit server...

REM --- 关键步骤5: 运行 Streamlit 应用 ---
streamlit run app.py