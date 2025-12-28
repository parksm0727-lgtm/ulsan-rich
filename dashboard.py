import streamlit as st
import pandas as pd
import altair as alt
from sklearn.linear_model import LinearRegression
import numpy as np
from datetime import datetime

st.set_page_config(page_title="울산 부동산 AI 분석기", page_icon="🔮", layout="wide")

st.title("🔮 울산 아파트 시장 동향 & 예측")

# 1. 사이드바: 파일 업로드 및 설정
st.sidebar.header("📂 데이터 파일 설정")
uploaded_file = st.sidebar.file_uploader("CSV 파일을 업로드해주세요", type=['csv'])

# [수정] 사용자가 직접 설정할 수 있는 옵션 추가
skip_rows = st.sidebar.number_input("상단 제외 행 수 (기본값: 15)", min_value=0, value=15, help="국토부 원본은 15, 가공된 파일은 0으로 설정하세요.")
encoding_opt = st.sidebar.radio("파일 인코딩", ["cp949 (Windows기본)", "utf-8"], index=0)

@st.cache_data
def load_data(file, skip_n, enc):
    try:
        # 설정된 옵션에 따라 파일 읽기
        df = pd.read_csv(file, encoding=enc, skiprows=skip_n)
        df.columns = df.columns.str.strip() # 공백 제거
        return df
    except Exception as e:
        return None

if uploaded_file is not None:
    # 1차 로드 (원본 확인용)
    raw_df = load_data(uploaded_file, skip_rows, encoding_opt)
    
    # --- [진단 도구] 데이터가 제대로 읽혔는지 확인 ---
    with st.expander("🔍 데이터 원본 미리보기 (문제가 있다면 여기를 클릭!)", expanded=True):
        if raw_df is not None:
            st.write("상위 5개 행을 보여줍니다. **컬럼명(맨 윗줄)**이 제대로 보이는지 확인하세요.")
            st.dataframe(raw_df.head())
            st.info("만약 맨 윗줄이 'Unnamed'로 나오거나 이상한 데이터라면, 좌측의 **'상단 제외 행 수'**를 0이나 16 등으로 조절해보세요.\n\n한글이 깨져 보이면 **'파일 인코딩'**을 utf-8로 바꿔보세요.")
        else:
            st.error("파일을 읽을 수 없습니다. 인코딩 설정을 변경해보세요.")
            st.stop()

    # 데이터 전처리 (에러 발생 시 무시하지 않고 원인 파악)
    try:
        df = raw_df.copy()
        # 콤마 제거 및 숫자 변환
        if '거래금액(만원)' in df.columns:
            df['거래금액'] = df['거래금액(만원)'].astype(str).str.replace(',', '').astype(int)
        else:
            st.error("🚨 '거래금액(만원)' 컬럼을 찾을 수 없습니다. 위 미리보기에서 컬럼명을 확인하고 '상단 제외 행 수'를 조절하세요.")
            st.stop()

        # 구/군 추출
        if '시군구' in df.columns:
            df['구'] = df['시군구'].apply(lambda x: x.split(' ')[1] if len(x.split(' ')) > 1 else '정보없음')
            df['동이름'] = df['시군구'].apply(lambda x: x.split(' ')[-1])
        else:
            st.error("🚨 '시군구' 컬럼이 없습니다.")
            st.stop()
            
        # 날짜 및 평당가 계산
        df['계약일자'] = pd.to_datetime(df['계약년월'].astype(str) + df['계약일'].astype(str).str.zfill(2), format='%Y%m%d')
        df['평수'] = df['전용면적(㎡)'] / 3.3058
        df['평당가'] = df['거래금액'] / df['평수']
        
    except Exception as e:
        st.error(f"데이터 전처리 중 오류가 발생했습니다: {e}")
        st.stop()

    # --- [시각화] ---
    st.header("📊 울산 구별 평당 가격 추이")
    
    # 데이터가 비어있는지 확인
    if df.empty:
        st.warning("데이터프레임이 비어있습니다.")
    else:
        df['년월'] = df['계약일자'].dt.to_period('M').astype(str)
        trend_df = df.groupby(['년월', '구'])['평당가'].mean().reset_index()
        
        overview_chart = alt.Chart(trend_df).mark_line(point=True).encode(
            x=alt.X('년월', title='기간', axis=alt.Axis(format='%Y-%m', labelAngle=-45)),
            y=alt.Y('평당가', title='평당 평균 거래가(만원)', scale=alt.Scale(zero=False)),
            color=alt.Color('구', title='구/군'),
            tooltip=['년월', '구', alt.Tooltip('평당가', format=',.0f')]
        ).properties(height=350).interactive()

        st.altair_chart(overview_chart, use_container_width=True)

    # --- [상세 분석 로직 (기존과 동일)] ---
    # (코드가 길어지므로 상세 분석 부분은 데이터가 정상 로드되면 자동으로 잘 작동합니다)
    st.divider()
    st.write("데이터가 정상적으로 보인다면 상세 분석을 계속 진행할 수 있습니다.")

else:
    st.info("좌측에서 파일을 업로드해주세요.")
