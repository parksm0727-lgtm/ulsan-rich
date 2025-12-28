import streamlit as st
import pandas as pd
import altair as alt
from sklearn.linear_model import LinearRegression
import numpy as np
from datetime import datetime

# 1. 페이지 설정
st.set_page_config(page_title="울산 부동산 AI 분석기", page_icon="🔮", layout="wide")

st.title("🔮 울산 아파트 시장 동향 & AI 예측")
st.markdown("데이터의 띄어쓰기가 달라도 정확하게 **구/군**을 찾아내도록 개선된 버전입니다.")

# 2. 사이드바: 파일 업로드 및 설정
st.sidebar.header("📂 데이터 파일 & 설정")
uploaded_file = st.sidebar.file_uploader("CSV 파일을 업로드해주세요", type=['csv'])

st.sidebar.markdown("---")
skip_rows = st.sidebar.number_input("상단 제외 행 수 (기본값: 15)", min_value=0, value=15)
encoding_label = st.sidebar.radio("파일 인코딩", ["cp949 (Windows기본)", "utf-8"], index=0)
encoding_opt = "cp949" if "cp949" in encoding_label else "utf-8"

@st.cache_data
def load_data(file, skip_n, enc):
    try:
        df = pd.read_csv(file, encoding=enc, skiprows=skip_n)
        df.columns = df.columns.str.strip() 
        return df
    except Exception as e:
        return str(e)

if uploaded_file is None:
    st.info("👈 좌측 사이드바에서 데이터 파일(CSV)을 업로드해주세요.")
    st.stop()

raw_df = load_data(uploaded_file, skip_rows, encoding_opt)

if isinstance(raw_df, str): 
    st.error(f"파일 읽기 오류: {raw_df}")
    st.stop()

# 3. 데이터 전처리 (스마트 주소 분석 적용)
try:
    df = raw_df.copy()
    
    # (1) 거래금액: 콤마 제거
    df['거래금액'] = df['거래금액(만원)'].astype(str).str.replace(',', '').astype(int)
    
    # (2) [핵심 수정] 스마트 주소 분석기
    # 띄어쓰기가 몇 개든 상관없이 '~구', '~군'으로 끝나는 단어를 찾음
    def find_gu(address):
        if not isinstance(address, str): return "확인불가"
        for part in address.split(): # 공백 기준으로 쪼개기 (이중 공백도 해결)
            if part.endswith('구') or part.endswith('군'):
                return part
        return "기타" # 구/군을 못 찾은 경우

    def find_dong(address):
        if not isinstance(address, str): return ""
        # 구/군 다음에 오는 단어를 동으로 간주하거나, '~동', '~리', '~가' 로 끝나는 말 찾기
        for part in address.split():
            if part.endswith('동') or part.endswith('리') or part.endswith('가'):
                return part
        return ""

    df['구'] = df['시군구'].apply(find_gu)
    df['동이름'] = df['시군구'].apply(find_dong)
    df['단지명'] = df['단지명'].astype(str).str.strip()

    # (3) 날짜 및 평수
    df['계약일자'] = pd.to_datetime(df['계약년월'].astype(str) + df['계약일'].astype(str).str.zfill(2), format='%Y%m%d')
    df['평수'] = df['전용면적(㎡)'] / 3.3058
    df['평당가'] = df['거래금액'] / df['평수']

except Exception as e:
    st.error(f"데이터 전처리 중 문제가 발생했습니다: {e}")
    st.dataframe(raw_df.head()) # 문제 파악을 위해 원본 표시
    st.stop()

# 4. 상단 그래프: 울산 구별 평당 가격
st.header("📊 울산 구별 평당 가격 추이")

# 그래프 데이터 만들기
df['년월'] = df['계약일자'].dt.to_period('M').astype(str)
trend_df = df.groupby(['년월', '구'])['평당가'].mean().reset_index()

# 데이터가 비었는지 확인하는 안전장치
if trend_df.empty:
    st.error("🚨 그래프를 그릴 데이터가 없습니다. '시군구' 컬럼 형식을 확인해주세요.")
    st.write("추출된 데이터 샘플:", df[['시군구', '구', '동이름']].head())
else:
    # Altair 차트 그리기
    chart = alt.Chart(trend_df).mark_line(point=True).encode(
        x=alt.X('년월', title='기간', axis=alt.Axis(format='%Y-%m', labelAngle=-45)),
        y=alt.Y('평당가', title='평당가(만원)', scale=alt.Scale(zero=False)),
        color=alt.Color('구', title='구/군', scale=alt.Scale(scheme='category10')),
        tooltip=['년월', '구', alt.Tooltip('평당가', format=',.0f')]
    ).properties(height=350).interactive()
    
    st.altair_chart(chart, use_container_width=True)

st.divider()

# 5. 하단: 개별 분석
st.header("🏢 개별 아파트 상세 분석")

col1, col2, col3, col4 = st.columns(4)

# 필터링 로직 (데이터가 있는 것만 보여줌)
valid_gu = sorted([g for g in df['구'].unique() if g != "기타"])
with col1:
    selected_gu = st.selectbox("1. 구/군", valid_gu if valid_gu else ["데이터없음"])

with col2:
    dong_list = sorted(df[df['구'] == selected_gu]['동이름'].unique())
    selected_dong = st.selectbox("2. 동네", dong_list)

with col3:
    apt_list = sorted(df[(df['구'] == selected_gu) & (df['동이름'] == selected_dong)]['단지명'].unique())
    selected_apt = st.selectbox("3. 아파트", apt_list)

with col4:
    apt_df = df[(df['단지명'] == selected_apt) & (df['동이름'] == selected_dong)]
    area_list = sorted(apt_df['전용면적(㎡)'].unique())
    
    def fmt(x): return f"{x}㎡ ({x/3.3058:.1f}평)"
    selected_area = st.selectbox("4. 평수", area_list, format_func=fmt)

# 분석 대상 데이터
target_df = apt_df[apt_df['전용면적(㎡)'] == selected_area].sort_values('계약일자')

pyeong_val = selected_area / 3.3058 if selected_area else 0
st.subheader(f"📍 {selected_apt} {pyeong_val:.1f}평형")

if target_df.empty:
    st.info("선택된 아파트 정보가 없습니다.")
elif len(target_df) < 5:
    st.warning(f"데이터가 부족하여({len(target_df)}건) 차트만 표시합니다.")
    c = alt.Chart(target_df).mark_circle(size=60).encode(
        x='계약일자', y=alt.Y('거래금액', scale=alt.Scale(zero=False)), tooltip=['거래금액']
    ).interactive()
    st.altair_chart(c, use_container_width=True)
else:
    if st.button("🤖 미래 가격 예측 실행"):
        target_df['date_ord'] = target_df['계약일자'].map(datetime.toordinal)
        X = target_df[['date_ord']]
        y = target_df['거래금액']
        
        model = LinearRegression()
        model.fit(X, y)
        
        last_date = target_df['계약일자'].max()
        future_dates = [last_date + pd.Timedelta(days=x) for x in range(15, 180, 15)]
        future_ord = np.array([d.toordinal() for d in future_dates]).reshape(-1, 1)
        pred = model.predict(future_ord)
        
        future_df = pd.DataFrame({'계약일자': future_dates, '예측가격': pred.astype(int)})
        
        # 차트 병합
        c1 = alt.Chart(target_df).mark_circle(size=60, color='#1f77b4').encode(x='계약일자', y=alt.Y('거래금액', scale=alt.Scale(zero=False)), tooltip=['거래금액'])
        c2 = alt.Chart(future_df).mark_line(strokeDash=[5,5], color='#ff7f0e').encode(x='계약일자', y='예측가격', tooltip=['예측가격'])
        
        st.altair_chart(c1 + c2, use_container_width=True)
        
        # 결론 도출
        diff = future_df.iloc[-1]['예측가격'] - target_df.iloc[-1]['거래금액']
        msg = "상승" if diff > 0 else "하락"
        st.success(f"📈 예측 결과: 6개월 뒤 약 {abs(diff)/10000:.2f}억원 {msg}할 것으로 보입니다.")
    else:
        c = alt.Chart(target_df).mark_circle(size=60).encode(
            x='계약일자', y=alt.Y('거래금액', scale=alt.Scale(zero=False)), tooltip=['거래금액']
        ).interactive()
        st.altair_chart(c, use_container_width=True)
