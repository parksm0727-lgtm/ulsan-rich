import streamlit as st
import pandas as pd
import altair as alt
from sklearn.linear_model import LinearRegression
import numpy as np
from datetime import datetime

# 1. 페이지 설정
st.set_page_config(page_title="울산 부동산 AI 분석기", page_icon="🔮", layout="wide")

st.title("🔮 울산 아파트 미래 가격 예측")
st.markdown("과거 데이터를 학습하여 **향후 6개월간의 가격 추세**를 예측합니다.")

# 2. 데이터 로드
@st.cache_data
def load_data():
    file_path = 'c:/tistory_auto/ulsan_data.csv'
    try:
        df = pd.read_csv(file_path, encoding='cp949', skiprows=15)
        df.columns = df.columns.str.strip()
        df['거래금액'] = df['거래금액(만원)'].astype(str).str.replace(',', '').astype(int)
        df['동이름'] = df['시군구'].apply(lambda x: x.split(' ')[-1])
        # 날짜 변환 (YYYYMM -> datetime)
        df['계약일자'] = pd.to_datetime(df['계약년월'].astype(str) + df['계약일'].astype(str).str.zfill(2), format='%Y%m%d')
        return df
    except Exception as e:
        return None

df = load_data()

if df is None:
    st.error("데이터 파일을 찾을 수 없습니다.")
    st.stop()

# 3. 사이드바: 아파트 선택
st.sidebar.header("🎯 분석 대상 선택")
gu_list = df['시군구'].apply(lambda x: x.split(' ')[1]).unique()
selected_gu = st.sidebar.selectbox("1. 구/군", gu_list, index=0)

dong_list = df[df['시군구'].str.contains(selected_gu)]['동이름'].unique()
selected_dong = st.sidebar.selectbox("2. 동네 (예: 덕하리)", dong_list)

# 해당 동네 아파트 리스트
apt_list = df[df['동이름'] == selected_dong]['단지명'].unique()
selected_apt = st.sidebar.selectbox("3. 아파트 단지", apt_list)

# 선택된 아파트 데이터 필터링
target_df = df[(df['동이름'] == selected_dong) & (df['단지명'] == selected_apt)].sort_values('계약일자')

# 4. 메인 화면: 분석 결과
st.subheader(f"🏢 {selected_apt} 가격 분석")

if len(target_df) < 5:
    st.warning("⚠️ 데이터가 너무 적어(5건 미만) 정확한 예측이 어렵습니다.")
else:
    # (1) 차트 그리기
    chart = alt.Chart(target_df).mark_circle(size=60).encode(
        x='계약일자',
        y=alt.Y('거래금액', title='거래금액(만원)'),
        tooltip=['계약일자', '거래금액', '전용면적(㎡)', '층']
    ).interactive()
    
    st.altair_chart(chart, use_container_width=True)

    # (2) AI 예측 버튼
    if st.button("🤖 AI 미래 가격 예측하기"):
        with st.spinner("AI가 과거 패턴을 분석 중입니다..."):
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
            base_line = alt.Chart(target_df).mark_circle(color='blue').encode(
                x='계약일자', y='거래금액', tooltip=['계약일자', '거래금액']
            )
            
            pred_line = alt.Chart(future_df).mark_line(color='red', strokeDash=[5, 5]).encode(
                x='계약일자', y=alt.Y('예측가격', title='가격(만원)'), tooltip=['계약일자', '예측가격']
            )

            st.success("분석 완료! 빨간 점선이 예상되는 가격 흐름입니다.")
            st.altair_chart(base_line + pred_line, use_container_width=True)
            
            # 텍스트 코멘트
            current_price = target_df.iloc[-1]['거래금액']
            future_price = future_df.iloc[-1]['예측가격']
            diff = future_price - current_price
            
            st.markdown("### 📊 AI 분석 리포트")
            if diff > 0:
                st.write(f"📈 현재 추세대로라면, 6개월 뒤 약 **{diff/10000:.1f}억원 상승**할 가능성이 보입니다.")
            else:
                st.write(f"📉 현재 추세가 꺾이고 있습니다. 6개월 뒤 약 **{abs(diff)/10000:.1f}억원 하락**하거나 조정받을 수 있습니다.")
                st.info("※ 주의: 이 예측은 과거 데이터의 '추세'만 반영한 결과입니다. 실제 시장 상황(금리 등)에 따라 달라질 수 있습니다.")
