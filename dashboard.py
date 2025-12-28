import streamlit as st
import pandas as pd
import altair as alt
from sklearn.linear_model import LinearRegression
import numpy as np
from datetime import datetime

# 1. 페이지 설정
st.set_page_config(page_title="울산 부동산 AI 분석기", page_icon="🔮", layout="wide")

st.title("🔮 울산 아파트 시장 동향 & 예측")
st.markdown("""
**데이터 기반 부동산 분석 도구**입니다. 
먼저 울산 전체의 흐름을 확인하고, 좌측 사이드바에서 특정 아파트를 선택해 상세 분석을 진행하세요.
""")

# 2. 데이터 로드 (파일 업로드 방식)
st.sidebar.header("📂 데이터 파일")
uploaded_file = st.sidebar.file_uploader("국토부 실거래가 CSV 파일을 업로드해주세요", type=['csv'])

@st.cache_data
def load_data(file):
    try:
        # 국토부 실거래가 데이터 로드 (상단 설명 skiprows=15 가정)
        df = pd.read_csv(file, encoding='cp949', skiprows=15)
        df.columns = df.columns.str.strip()
        
        # 전처리: 거래금액 콤마 제거 및 정수 변환
        df['거래금액'] = df['거래금액(만원)'].astype(str).str.replace(',', '').astype(int)
        
        # 전처리: 구/군 추출
        df['구'] = df['시군구'].apply(lambda x: x.split(' ')[1])
        
        # 전처리: 동이름 추출
        df['동이름'] = df['시군구'].apply(lambda x: x.split(' ')[-1])
        
        # 전처리: 날짜 변환
        df['계약일자'] = pd.to_datetime(df['계약년월'].astype(str) + df['계약일'].astype(str).str.zfill(2), format='%Y%m%d')
        
        # [NEW] 분석용 파생변수: 평당가 (거래금액 / 평수)
        # 전용면적을 평수로 환산 (1평 = 3.3058㎡)
        df['평수'] = df['전용면적(㎡)'] / 3.3058
        df['평당가'] = df['거래금액'] / df['평수']
        
        return df
    except Exception as e:
        st.error(f"데이터 로드 중 오류 발생: {e}")
        return None

# 파일이 없으면 안내 문구 표시 후 중단
if uploaded_file is None:
    st.info("👈 좌측 사이드바에서 데이터 파일(CSV)을 먼저 업로드해주세요.")
    st.stop()

df = load_data(uploaded_file)
if df is None: st.stop()

# --- [파트 1] 울산 전체 구별 트렌드 (메인 화면 상단) ---
st.header("📊 울산 구별 평당 가격 추이")
st.markdown("전용면적당 가격(평당가) 흐름을 통해 어느 지역이 시장을 주도하는지 확인합니다.")

# 월별, 구별 평균 평당가 계산
df['년월'] = df['계약일자'].dt.to_period('M').astype(str)
trend_df = df.groupby(['년월', '구'])['평당가'].mean().reset_index()

# 라인 차트 그리기
overview_chart = alt.Chart(trend_df).mark_line(point=True).encode(
    x=alt.X('년월', title='기간', axis=alt.Axis(format='%Y-%m', labelAngle=-45)),
    y=alt.Y('평당가', title='평당 평균 거래가(만원)', scale=alt.Scale(zero=False)),
    color=alt.Color('구', title='구/군', legend=alt.Legend(orient="top")),
    tooltip=['년월', '구', alt.Tooltip('평당가', format=',.0f', title='평당가(만원)')]
).properties(
    height=350
).interactive()

st.altair_chart(overview_chart, use_container_width=True)

st.divider() # 구분선

# --- [파트 2] 개별 아파트 상세 분석 ---
st.header("🏢 개별 아파트 상세 분석")
st.markdown("좌측 사이드바에서 관심 있는 아파트를 선택하면 **미래 가격**을 예측해 드립니다.")

# 사이드바: 필터링
st.sidebar.markdown("---")
st.sidebar.header("🎯 상세 분석 대상 선택")

# 1. 구/군
gu_list = sorted(df['구'].unique())
selected_gu = st.sidebar.selectbox("1. 구/군", gu_list)

# 2. 동네
dong_list = sorted(df[df['구'] == selected_gu]['동이름'].unique())
selected_dong = st.sidebar.selectbox("2. 동네", dong_list)

# 3. 아파트 단지
apt_list = sorted(df[df['동이름'] == selected_dong]['단지명'].unique())
selected_apt = st.sidebar.selectbox("3. 아파트 단지", apt_list)

# 4. 평수 (전용면적)
area_list = df[(df['동이름'] == selected_dong) & (df['단지명'] == selected_apt)]['전용면적(㎡)'].unique()
area_list = sorted(area_list)

def format_area(area):
    pyeong = area / 3.3058
    return f"{area}㎡ ({pyeong:.1f}평)"

selected_area = st.sidebar.selectbox("4. 전용면적 (평수)", area_list, format_func=format_area)

# 데이터 필터링
target_df = df[
    (df['동이름'] == selected_dong) & 
    (df['단지명'] == selected_apt) & 
    (df['전용면적(㎡)'] == selected_area)
].sort_values('계약일자')

# 상세 분석 결과 표시
pyeong_val = selected_area / 3.3058
st.subheader(f"📍 {selected_apt} {pyeong_val:.1f}평형")

if len(target_df) < 5:
    st.warning(f"⚠️ 거래 내역이 {len(target_df)}건 뿐입니다. 데이터가 적어 예측 모델을 실행할 수 없습니다.")
    # 단순 차트만 표시
    chart = alt.Chart(target_df).mark_circle(size=60).encode(
        x='계약일자',
        y=alt.Y('거래금액', title='거래금액(만원)', scale=alt.Scale(zero=False)),
        tooltip=['계약일자', '거래금액', '층']
    ).interactive()
    st.altair_chart(chart, use_container_width=True)

else:
    # 탭을 사용하여 과거 데이터와 예측 데이터를 분리해서 보여줄 수도 있지만, 
    # 직관적으로 한 화면에 보여줍니다.
    
    # (1) AI 예측 버튼
    if st.button("🤖 이 아파트의 미래 가격 예측하기", type="primary"):
        with st.spinner("AI가 과거 패턴을 분석하고 있습니다..."):
            # 학습 데이터 준비
            target_df['date_ord'] = target_df['계약일자'].map(datetime.toordinal)
            X = target_df[['date_ord']]
            y = target_df['거래금액']

            # 모델 학습
            model = LinearRegression()
            model.fit(X, y)

            # 미래 예측 (180일)
            last_date = target_df['계약일자'].max()
            future_dates = [last_date + pd.Timedelta(days=x) for x in range(15, 180, 15)] # 15일 간격
            future_ord = np.array([d.toordinal() for d in future_dates]).reshape(-1, 1)
            predictions = model.predict(future_ord)

            future_df = pd.DataFrame({
                '계약일자': future_dates,
                '예측가격': predictions.astype(int),
                '구분': '미래예측'
            })

            # 차트 시각화 (통합)
            base_chart = alt.Chart(target_df).mark_circle(color='#1f77b4', size=60).encode(
                x='계약일자', 
                y=alt.Y('거래금액', scale=alt.Scale(zero=False), title='가격(만원)'),
                tooltip=['계약일자', '거래금액']
            )
            
            pred_chart = alt.Chart(future_df).mark_line(color='#ff7f0e', strokeDash=[5, 5], strokeWidth=3).encode(
                x='계약일자', y='예측가격',
                tooltip=['계약일자', '예측가격']
            )

            st.altair_chart(base_chart + pred_chart, use_container_width=True)

            # 결과 코멘트
            current_price = target_df.iloc[-1]['거래금액']
            future_price = future_df.iloc[-1]['예측가격']
            diff = future_price - current_price
            
            diff_str = f"{abs(diff)/10000:.2f}억원" if abs(diff) >= 10000 else f"{abs(diff)}만원"
            
            st.info("📢 분석 리포트")
            if diff > 0:
                st.write(f"현재 추세상 6개월 뒤 약 **{diff_str} 상승**할 것으로 예측됩니다.")
            else:
                st.write(f"현재 추세상 6개월 뒤 약 **{diff_str} 하락** 조정이 예상됩니다.")
    else:
        # 버튼 누르기 전에는 기본 차트만 표시
        chart = alt.Chart(target_df).mark_circle(size=60).encode(
            x='계약일자',
            y=alt.Y('거래금액', title='거래금액(만원)', scale=alt.Scale(zero=False)),
            tooltip=['계약일자', '거래금액', '층']
        ).interactive()
        st.altair_chart(chart, use_container_width=True)
        st.caption("위 버튼을 누르면 미래 가격을 예측합니다.")
