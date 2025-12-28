import streamlit as st
import pandas as pd
import altair as alt
from sklearn.linear_model import LinearRegression
import numpy as np
from datetime import datetime

# 1. 페이지 설정
st.set_page_config(page_title="울산 부동산 AI 분석기", page_icon="🔮", layout="wide")

st.title("🔮 울산 아파트 시장 동향 & AI 예측")
st.markdown("""
**데이터 로드 문제 해결 버전**입니다.
좌측 사이드바에서 파일을 업로드하고, 데이터가 안 보이면 **'설정'**을 조절해보세요.
""")

# 2. 사이드바: 파일 업로드 및 설정 제어
st.sidebar.header("📂 데이터 파일 & 설정")
uploaded_file = st.sidebar.file_uploader("CSV 파일을 업로드해주세요", type=['csv'])

st.sidebar.markdown("---")
st.sidebar.subheader("⚙️ 파일 읽기 설정")
st.sidebar.caption("데이터가 깨지거나 에러가 나면 아래 옵션을 변경하세요.")

# [핵심 수정] 파일 형식에 맞춰 사용자가 조절 가능한 옵션
skip_rows = st.sidebar.number_input(
    "상단 제외 행 수 (기본값: 15)", 
    min_value=0, 
    value=15, 
    help="국토부 원본 파일은 보통 15줄의 설명이 있습니다. 가공된 파일은 0으로 설정하세요."
)

encoding_opt = st.sidebar.radio(
    "파일 인코딩 (글자 깨짐 해결)", 
    ["cp949 (Windows기본)", "utf-8"], 
    index=0,
    help="한글이 외계어처럼 보이면 utf-8을 선택하세요."
)

# 3. 데이터 로드 함수 (에러 처리 강화)
@st.cache_data
def load_data(file, skip_n, enc):
    try:
        # 설정된 옵션으로 읽기 시도
        df = pd.read_csv(file, encoding=enc, skiprows=skip_n)
        
        # 컬럼명 앞뒤 공백 제거 (매우 중요)
        df.columns = df.columns.str.strip()
        return df
    except UnicodeDecodeError:
        return "EncodingError"
    except pd.errors.ParserError:
        return "ParserError"
    except Exception as e:
        return f"Error: {str(e)}"

# 4. 메인 로직 시작
if uploaded_file is None:
    st.info("👈 좌측 사이드바에서 데이터 파일(CSV)을 업로드해주세요.")
    st.stop()

# 데이터 로드 시도
raw_df = load_data(uploaded_file, skip_rows, encoding_opt)

# 에러 체크 및 가이드
if isinstance(raw_df, str):
    st.error(f"🚨 파일을 읽는 중 오류가 발생했습니다: {raw_df}")
    if raw_df == "EncodingError":
        st.warning("👉 팁: 좌측 사이드바의 **'파일 인코딩'**을 [utf-8]로 변경해보세요.")
    elif raw_df == "ParserError":
        st.warning("👉 팁: 좌측 사이드바의 **'상단 제외 행 수'**가 맞지 않을 수 있습니다. [0]으로 변경해보세요.")
    st.stop()

# 5. 데이터 전처리 및 미리보기
with st.expander("🔍 데이터 원본 미리보기 (여기를 눌러 확인)", expanded=True):
    st.write(f"현재 설정: 제외 행 수 {skip_rows}, 인코딩 {encoding_opt}")
    st.dataframe(raw_df.head(3))
    
    # 필수 컬럼 체크
    required_cols = ['시군구', '단지명', '전용면적(㎡)', '계약년월', '계약일', '거래금액(만원)']
    missing_cols = [col for col in required_cols if col not in raw_
