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
**데이터 로드 문제 해결 최종 버전**입니다.
좌측 사이드바에서 파일을 업로드하고, 데이터가 안 보이면 **'설정'**을 조절해보세요.
""")

# 2. 사이드바: 파일 업로드 및 설정 제어
st.sidebar.header("📂 데이터 파일 & 설정")
uploaded_file = st.sidebar.file_uploader("CSV 파일을 업로드해주세요", type=['csv'])

st.sidebar.markdown("---")
st.sidebar.subheader("⚙️ 파일 읽기 설정")
st.sidebar.caption("데이터가 깨지거나 에러가 나면 아래 옵션을 변경하세요.")

# 파일 형식에 맞춰 사용자가 조절 가능한 옵션
skip_rows = st.sidebar.number_input(
    "상단 제외 행 수 (기본값: 15)", 
    min_value=0, 
    value=15, 
    help="국토부 원본 파일은 보통 15줄의 설명이 있습니다. 가공된 파일은 0으로 설정하세요."
)

# [수정된 부분] 사용자에게는 친절하게 보여주고, 코드에는 정확한 값을 전달하도록 분리
encoding_label = st.sidebar.radio(
    "파일 인코딩 (글자 깨짐 해결)", 
    ["cp949 (Windows기본)", "utf-8"], 
    index=0,
    help="한글이 외계어처럼 보이면 utf-8을 선택하세요."
)

# 선택된 라벨을 실제 인코딩 코드로 변환
if "cp949" in encoding_label:
    encoding_opt = "cp949"
else:
    encoding_opt = "utf-8"

# 3. 데이터 로드 함수
@st.cache_data
def load_data(file, skip_n, enc):
    try:
        # 설정된 옵션으로 읽기 시도
        df = pd.read_csv(file, encoding=enc, skiprows=skip_n)
        # 컬럼명 앞뒤 공백 제거
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
    
    # [안전 수정] 리스트 컴프리헨션 대신 풀어서 작성
    missing_cols = []
    for col in required_cols:
        if col not in raw_df.columns:
            missing_cols.append(col)
    
    if missing_cols:
        st.error(f"🚨 데이터에서 다음 필수 항목을 찾을 수 없습니다: {missing_cols}")
        st.write("위의 미리보기 표를 확인하세요. 컬럼명이 첫 번째 줄에 제대로 와있나요?")
        st.warning("👉 만약 데이터가 첫 줄부터 시작된다면 좌측 **'상단 제외 행 수'를 0**으로 설정하세요.")
        st.stop()
    else:
        st.success("✅ 데이터 형식이 올바릅니다. 분석을 시작합니다.")

# 전처리 수행
try:
    df = raw_df.copy()
    df['거래금액'] = df['거래금액(만원)'].astype(str).str.replace(',', '').astype(int)
    
    # 구/군 정보 추출
    df['구'] = df['시군구'].apply(lambda x: x.split(' ')[1] if len(x.split(' ')) > 1 else '기타')
    df['동이름'] = df['시군구'].apply(lambda x: x.split(' ')[-1])
    
    # 날짜 변환
    df['계약일자'] = pd.to_datetime(df['계약년월'].astype(str) + df['계약일'].astype(str).str.zfill(2), format='%Y%m%d')
    
    # 평수 및 평당가 계산
    df['평수'] = df['전용면적(㎡)'] / 3.3058
    df['평당가'] = df['거래금액'] / df['평수']
    
except Exception as e:
    st.error(f"데이터 전처리 중 오류 발생: {e}")
    st.stop()

st.divider()

# --- [파트 1] 울산 전체 구별 트렌드 ---
st.header("📊 울산 구별 평당 가격 추이")
st.markdown("전용면적당 가격(평당가) 흐름을 통해 시장의 큰 흐름을 파악합니다.")

# 월별/구별 데이터 집계
df['년월'] = df['계약일자'].dt.to_period('M').astype(str)
trend_df = df.groupby(['년월', '구'])['평당가'].mean().reset_index()

overview_chart = alt.Chart(trend_df).mark_line(point=True).encode(
    x=alt.X('년월', title='기간', axis=alt.Axis(format='%Y-%m', labelAngle=-45)),
    y=alt.Y('평당가', title='평당 평균 거래가(만원)', scale=alt.Scale(zero=False)),
    color=alt.Color('구', title='구/군'),
    tooltip=['년월', '구', alt.Tooltip('평당가', format=',.0f')]
).properties(height=350).interactive()

st.altair_chart(overview_chart, use_container_width=True)

# --- [파트 2] 개별 아파트 상세 분석 ---
st.header("🏢 개별 아파트 상세 분석 & 예측")
st.markdown("관심 있는 아파트의 특정 평형을 선택하여 **미래 가격**을 예측합니다.")

# 필터링 UI
c1, c2, c3, c4 = st.columns(4)

with c1:
    gu_list = sorted(df['구'].unique())
    selected_gu = st.selectbox("1. 구/군", gu_list)

with c2:
    dong_list = sorted(df[df['구'] == selected_gu]['동이름'].unique())
    selected_dong = st.selectbox("2. 동네", dong_list)

with c3:
    apt_list = sorted(df[df['동이름'] == selected_dong]['단지명'].unique())
    selected_apt = st.selectbox("3. 아파트", apt_list)

with c4:
    # [안전 수정] 코드가 길어서 잘리지 않도록 변수로 분리하여 작성
    # 1. 해당 아파트 데이터만 먼저 필터링
    apt_data = df[
        (df['동이름'] == selected_dong) & 
        (df['단지명'] == selected_apt)
    ]
    
    # 2. 평수 목록 추출
    area_list = sorted(apt_data['전용면적(㎡)'].unique())
    
    def format_area(area):
        pyeong = area / 3.3058
        return f"{area}㎡ ({pyeong:.1f}평)"
        
    selected_area = st.selectbox("4. 평수", area_list, format_func=format_area)

# 최종 데이터 필터링
target_df = df[
    (df['동이름'] == selected_dong) & 
    (df['단지명'] == selected_apt) & 
    (df['전용면적(㎡)'] == selected_area)
].sort_values('계약일자')

# 결과 표시
pyeong_val = selected_area / 3.3058
st.subheader(f"📍 {selected_apt} {pyeong_val:.1f}평형 분석 결과")

if len(target_df) < 5:
    st.warning(f"⚠️ 거래 내역이 {len(target_df)}건 뿐입니다. 데이터가 너무 적어 AI 예측이 불가능합니다.")
    chart = alt.Chart(target_df).mark_circle(size=60).encode(
        x='계약일자', y=alt.Y('거래금액', scale=alt.Scale(zero=False)), tooltip=['계약일자', '거래금액']
    ).interactive()
    st.altair_chart(chart, use_container_width=True)
else:
    # 예측 버튼
    if st.button("🤖 미래 가격 예측하기 (클릭)", type="primary"):
        with st.spinner("AI가 분석 중입니다..."):
            # 학습
            target_df['date_ord'] = target_df['계약일자'].map(datetime.toordinal)
            X = target_df[['date_ord']]
            y = target_df['거래금액']
            
            model = LinearRegression()
            model.fit(X, y)
            
            # 예측 (6개월)
            last_date = target_df['계약일자'].max()
            future_dates = [last_date + pd.Timedelta(days=x) for x in range(15, 180, 15)]
            future_ord = np.array([d.toordinal() for d in future_dates]).reshape(-1, 1)
            predictions = model.predict(future_ord)
            
            future_df = pd.DataFrame({'계약일자': future_dates, '예측가격': predictions.astype(int)})
            
            # 차트 (과거+미래)
            base = alt.Chart(target_df).mark_circle(color='#1f77b4', size=60).encode(
                x='계약일자', y=alt.Y('거래금액', scale=alt.Scale(zero=False), title='가격(만원)'),
                tooltip=['계약일자', '거래금액']
            )
            pred = alt.Chart(future_df).mark_line(color='#ff7f0e', strokeDash=[5, 5]).encode(
                x='계약일자', y='예측가격', tooltip=['계약일자', '예측가격']
            )
            
            st.altair_chart(base + pred, use_container_width=True)
            
            # 코멘트
            diff = future_df.iloc[-1]['예측가격'] - target_df.iloc[-1]['거래금액']
            diff_text = f"{abs(diff)/10000:.2f}억원" if abs(diff) >= 10000 else f"{abs(diff)}만원"
            direction = "상승" if diff > 0 else "하락"
            st.success(f"📈 분석 결과: 현재 추세가 지속된다면 6개월 뒤 약 **{diff_text} {direction}** 할 가능성이 있습니다.")
    else:
        # 기본 차트
        chart = alt.Chart(target_df).mark_circle(size=60).encode(
            x='계약일자', y=alt.Y('거래금액', scale=alt.Scale(zero=False)), tooltip=['계약일자', '거래금액']
        ).interactive()
        st.altair_chart(chart, use_container_width=True)
        st.caption("위 버튼을 누르면 미래 예측선이 표시됩니다.")
