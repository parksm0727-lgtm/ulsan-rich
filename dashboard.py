import streamlit as st
import pandas as pd
import requests
import xml.etree.ElementTree as ET
import altair as alt
import urllib3

# [설정] SSL 인증서 경고 무시 (verify=False 사용 시 경고 메시지 숨기기)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# 1. 페이지 설정
st.set_page_config(page_title="전국 아파트 실시간 실거래가", page_icon="📡", layout="wide")

st.title("📡 전국 아파트 실시간 실거래가 조회")
st.markdown("파일 업로드 없이 **국토교통부 API**를 통해 실시간 데이터를 조회합니다.")

# 2. 사이드바: 설정 및 입력
st.sidebar.header("🔑 설정 및 조회")

# (1) API 키 입력
api_key = st.sidebar.text_input("공공데이터포털 인증키 (Decoding Key)", type="password", help="발급받은 일반 인증키(Decoding)을 입력하세요.")

# (2) 지역 선택
region_codes = {
    "울산 남구": "31140",
    "울산 중구": "31110",
    "울산 북구": "31200",
    "울산 동구": "31170",
    "울산 울주군": "31710",
    "서울 강남구": "11680",
    "서울 서초구": "11650",
    "서울 송파구": "11710",
    "부산 해운대구": "26350",
    "대구 수성구": "27260"
}

region_name = st.sidebar.selectbox("지역 선택", list(region_codes.keys()))
lawd_cd = region_codes[region_name]

# (3) 날짜 선택
year = st.sidebar.selectbox("년도", ["2025", "2024", "2023"], index=1)
month = st.sidebar.selectbox("월", [f"{i:02d}" for i in range(1, 13)], index=11)
deal_ymd = year + month

# 3. 데이터 가져오기 함수
@st.cache_data
def fetch_data(api_key, lawd_cd, deal_ymd):
    # [핵심] HTTPS 주소 사용
    url = "https://apis.data.go.kr/1613000/RTMSDataSvcAptTrade/getRTMSDataSvcAptTrade"
    
    params = {
        "serviceKey": api_key,
        "LAWD_CD": lawd_cd,
        "DEAL_YMD": deal_ymd,
        "numOfRows": "1000",
        "pageNo": "1"
    }
    
    # [핵심] 헤더 설정
    headers = {
           "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }
    
    try:
        # [핵심] verify=False로 방화벽/SSL 우회
        response = requests.get(url, params=params, headers=headers, verify=False, timeout=10)
        
        try:
            root = ET.fromstring(response.content)
        except ET.ParseError:
            return f"🚨 서버 응답 오류 (XML 아님): {response.text}"
        
        # 에러 코드 확인
        header_code = root.find('.//resultCode')
        if header_code is not None:
            code_val = header_code.text.strip()
            if code_val not in ['00', '000']:
                error_msg = root.find('.//resultMsg').text
                return f"API Error: {error_msg} (코드: {code_val})"

        items = root.findall('.//item')
        if not items:
            return None
        
        # 데이터 수집
        data = []
        for item in items:
            row = {}
            for child in item:
                if child.text:
                    row[child.tag] = child.text.strip()
            data.append(row)
            
        return pd.DataFrame(data)
        
    except Exception as e:
        return f"통신 오류 발생: {e}"

# 4. 조회 버튼 및 결과 화면
if st.sidebar.button("🚀 실시간 조회하기"):
    if not api_key:
        st.error("⚠️ 인증키를 먼저 입력해주세요.")
    else:
        with st.spinner(f"{region_name}의 {year}년 {month}월 데이터를 조회 중..."):
            result = fetch_data(api_key, lawd_cd, deal_ymd)
            
            if isinstance(result, str):
                st.error("❌ 오류가 발생했습니다.")
                st.code(result) 
            elif result is None or result.empty:
                st.info("해당 기간에 신고된 거래 내역이 없습니다.")
            else:
                df = result
                
                # 컬럼 통역 (영어 -> 한글)
                col_map = {
                    'aptNm': '아파트', '단지명': '아파트',
                    'dealAmount': '거래금액', 'amount': '거래금액',
                    'excluUseAr': '전용면적', 'area': '전용면적', 
                    'umdNm': '법정동', 'dong': '법정동',
                    'floor': '층',
                    'dealDay': '일', 'day': '일'
                }
                df = df.rename(columns=col_map)
                
                # 필수 컬럼 채우기
                required_cols = ['아파트', '거래금액', '전용면적', '법정동', '층', '일']
                for col in required_cols:
                    if col not in df.columns:
                        df[col] = "-" if col != '거래금액' else "0"

                # 전처리 (숫자 변환)
                df['거래금액_숫자'] = df['거래금액'].astype(str).str.replace(',', '').astype(int)
                df['전용면적_숫자'] = pd.to_numeric(df['전용면적'], errors='coerce').fillna(0)
                df['일자'] = df['일'].astype(str).str.zfill(2)
                df['계약일'] = deal_ymd + df['일자']
                df['평수'] = df['전용면적_숫자'] / 3.3058
                df['평당가'] = df['거래금액_숫자'] / df['평수']
                
                st.success(f"✅ 총 {len(df)}건의 데이터를 가져왔습니다!")
                
                # 요약 지표
                avg_price = df['거래금액_숫자'].mean()
                max_price = df['거래금액_숫자'].max()
                
                c1, c2, c3 = st.columns(3)
                c1.metric("평균 거래가", f"{avg_price/10000:.1f}억원")
                c2.metric("최고 거래가", f"{max_price/10000:.1f}억원")
                top_dong = df['법정동'].mode()[0] if not df['법정동'].mode().empty else "-"
                c3.metric("최다 거래 지역", top_dong)
                
                st.divider()
                
                # 차트
                st.subheader("📅 거래 흐름")
                chart = alt.Chart(df).mark_circle(size=60).encode(
                    x=alt.X('계약일', title='날짜'),
                    y=alt.Y('거래금액_숫자', title='거래금액(만원)', scale=alt.Scale(zero=False)),
                    color=alt.Color('법정동', title='법정동'),
                    tooltip=['계약일', '아파트', '거래금액', '전용면적', '층']
                ).interactive()
                st.altair_chart(chart, use_container_width=True)
                
                # 표
                st.subheader("📋 상세 내역")
                display_cols = ['계약일', '법정동', '아파트', '전용면적', '거래금액', '층']
                st.dataframe(
                    df[display_cols].sort_values('계약일', ascending=False),
                    use_container_width=True
                )

else:
    st.info("👈 사이드바에 인증키(Decoding)를 입력하고 [조회하기] 버튼을 눌러주세요.")
