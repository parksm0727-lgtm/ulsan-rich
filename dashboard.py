import streamlit as st
import pandas as pd
import altair as alt
from sklearn.linear_model import LinearRegression
import numpy as np
from datetime import datetime

# 1. 페이지 설정
st.set_page_config(page_title="울산 부동산 AI 분석기", page_icon="🔮", layout="wide")

st.title("🔮 울산 아파트 미래 가격 예측")
st.markdown("""
과거 실거래가 데이터를 학습하여 **향후 6개월간의 가격 추세**를 예측합니다.
같은 아파트라도 **평수(전용면적)**에 따라 가격이 다르므로, 평형별로 구분하여 분석합니다.
""")

# 2. 데이터 로드 (파일 업로드 방식 적용)
st.sidebar.header("📂 데이터 파일")
uploaded_file = st.sidebar.file_uploader("국토부 실거래가 CSV 파일을 업로드해주세요", type=['csv'])

@st.cache_data
def load_data(file):
    try:
        # 국토부 데이터는 보통 상단에 설명이 있어 skiprows=15가 필요합니다.
        # 만약 직접 가공한 파일이라면 skiprows=15를 지워야 할 수도 있습니다.
        df = pd.read_csv(file, encoding='cp949', skiprows=15)
        
        # 컬럼명 공백 제거
        df.columns = df.columns.str.strip()
        
        # 전처리: 거래금액 콤마 제거 및 숫자 변환
        df['거래금액'] = df['거래금액(만원)'].astype(str).str.replace(',', '').astype(int)
        
        # 전처리: 동이름 추출
        df['동이름'] = df['시군구'].apply(lambda x: x.split(' ')[-1])
        
        # 전처리: 날짜 변환 (YYYYMM + D -> datetime)
        df['계약일자'] = pd.to_datetime(df['계약년월'].astype(str) + df['계약일'].astype(str).str.zfill(2), format='%Y%m%d')
        
        return df
    except Exception as e:
        st.error(f"데이터 로드 중 오류 발생: {e}")
        return None

# 파일이 없으면 안내 문구 표시 후 중단
if uploaded_file is None:
    st.info("👈 좌측 사이드바에서 데이터 파일(CSV)을 먼저 업로드해주세요.")
    st.stop()

df = load_data(uploaded_file)

if df is None:
    st.stop()

# 3. 사이드바: 분석 대상 선택
st.sidebar.header("🎯 분석 대상 선택")

# 3-1. 구/군
gu_list = df['시군구'].apply(lambda x: x.split(' ')[1]).unique()
selected_gu = st.sidebar.selectbox("1. 구/군", gu_list)

# 3-2. 동네
dong_list = df[df['시군구'].str.contains(selected_gu)]['동이름'].unique()
selected_dong = st.sidebar.selectbox("2. 동네", dong_list)

# 3-3. 아파트 단지
apt_list = df[df['동이름'] == selected_dong]['단지명'].unique()
selected_apt = st.sidebar.selectbox("3. 아파트 단지", apt_list)

# 3-4. 평수 (전용면적) - [추가된 기능]
# 선택된 아파트의 전용면적 목록 추출
area_list = df[(df['동이름'] == selected_dong) & (df['단지명'] == selected_apt)]['전용면적(㎡)'].unique()
area_list = sorted(area_list)

def format_area(area):
    pyeong = area / 3.3058
    return f"{area}㎡ ({pyeong:.1f}평)"

selected_area = st.sidebar.selectbox("4. 전용면적 (평수)", area_list, format_func=format_area)

# 4. 데이터 필터링 (아파트명 + 전용면적)
target_df = df[
    (df['동이름'] == selected_dong) & 
    (df['단지명'] == selected_apt) & 
    (df['전용면적(㎡)'] == selected_area)
].sort_values('계약일자')

# 5. 메인 화면: 분석 결과
pyeong_val = selected_area / 3.3058
st.subheader(f"🏢 {selected_apt} {pyeong_val:.1f}평형 분석 결과")

if len(target_df) < 5:
    st.warning(f"⚠️ 거래 내역이 너무 적습니다 (총 {len(target_df)}건). 정확한 예측을 위해 5건 이상의 데이터가 필요합니다.")
    # 데이터가 적어도 차트는 보여줌
    chart = alt.Chart(target_df).mark_circle(size=60).encode(
        x='계약일자',
        y=alt.Y('거래금액', title='거래금액(만원)', scale=alt.Scale(zero=False)),
        tooltip=['계약일자', '거래금액', '층']
    ).interactive()
    st.altair_chart(chart, use_container_width=True)

else:
    # (1) 과거 데이터 차트
    chart = alt.Chart(target_df).mark_circle(size=60).encode(
        x='계약일자',
        y=alt.Y('거래금액', title='거래금액(만원)', scale=alt.Scale(zero=False)),
        tooltip=['계약일자', '거래금액', '층']
    ).interactive()
    
    st.altair_chart(chart, use_container_width=True)

    # (2) AI 예측 버튼
    if st.button("🤖 AI 미래 가격 예측하기"):
        with st.spinner("AI가 가격 추세를 분석하고 있습니다..."):
            # 학습 데이터 준비 (날짜를 숫자로 변환)
            target_df['date_ord'] = target_df['계약일자'].map(datetime.toordinal)
            X = target_df[['date_ord']]
            y = target_df['거래금액']

            # 모델 학습 (선형 회귀)
            model = LinearRegression()
            model.fit(X, y)

            # 미래 날짜 생성 (오늘부터 +180일)
            last_date = target_df['계약일자'].max()
            future_dates = [last_date + pd.Timedelta(days=x) for x in range(0, 180, 15)]
            future_ord = np.array([d.toordinal() for d in future_dates]).reshape(-1, 1)

            # 예측 수행
            predictions = model.predict(future_ord)

            # 결과 데이터프레임
            future_df = pd.DataFrame({
                '계약일자': future_dates,
                '예측가격': predictions.astype(int),
                '구분': '미래예측'
            })

            # 시각화 (과거 + 미래)
            # 과거 데이터 (파란 점)
            base_line = alt.Chart(target_df).mark_circle(color='#1f77b4', size=60).encode(
                x='계약일자', 
                y=alt.Y('거래금액', scale=alt.Scale(zero=False)),
                tooltip=['계약일자', '거래금액']
            )
            
            # 미래 데이터 (빨간 점선)
            pred_line = alt.Chart(future_df).mark_line(color='#ff7f0e', strokeDash=[5, 5], strokeWidth=3).encode(
                x='계약일자', 
                y='예측가격',
                tooltip=['계약일자', '예측가격']
            )

            st.success("분석 완료! 주황색 점선이 예상되는 가격 흐름입니다.")
            st.altair_chart(base_line + pred_line, use_container_width=True)
            
            # 텍스트 코멘트
            current_price = target_df.iloc[-1]['거래금액']
            future_price = future_df.iloc[-1]['예측가격']
            diff = future_price - current_price
            
            st.markdown("### 📊 AI 분석 리포트")
            
            diff_text = f"{abs(diff)/10000:.1f}억원"
            if abs(diff) < 10000: # 1억 미만일 경우 천만원 단위로 표시
                diff_text = f"{abs(diff)}만원"

            if diff > 0:
                st.write(f"📈 현재 추세대로라면, 6개월 뒤 약 **{diff_text} 상승**할 가능성이 보입니다.")
            else:
                st.write(f"📉 현재 추세가 꺾이고 있습니다. 6개월 뒤 약 **{diff_text} 하락**하거나 조정받을 수 있습니다.")

            st.info("※ 참고: 이 예측은 과거 거래 데이터의 통계적 추세선(Linear Regression)입니다. 금리 변화나 정책 변수는 반영되지 않았습니다.")
