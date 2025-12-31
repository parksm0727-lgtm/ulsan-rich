import streamlit as st
import pandas as pd
import requests
import xml.etree.ElementTree as ET
import altair as alt
import urllib3

# [설정] SSL 인증서 경고 무시
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# 1. 페이지 설정
st.set_page_config(page_title="전국 아파트 실시간 실거래가", page_icon="📡", layout="wide")

st.title("📡 전국 아파트 실시간 실거래가 조회")
st.markdown("국토교통부 API를 사용하여 **실시간 매매가**를 조회합니다.")

# -----------------------------------------------------------
# [기능 1] 지역 코드 데이터 (계속 추가 가능)
# -----------------------------------------------------------
korea_regions = {
    "울산광역시": {
        "남구": "31140", "중구": "31110", "북구": "31200", 
        "동구": "31170", "울주군": "31710"
    },
    "서울특별시": {
        "강남구": "11680", "서초구": "11650", "송파구": "11710", 
        "용산구": "11170", "성동구": "11200", "마포구": "11440",
        "종로구": "11110", "중구": "11140", "노원구": "11350"
    },
    "부산광역시": {
        "해운대구": "26350", "수영구": "26500", "남구": "26290", 
        "동래구": "26260", "연제구": "26470"
    },
    "대구광역시": {
        "수성구": "27260", "중구": "27110"
    },
    "경기도": {
        "성남시 분당구": "41135", "수원시 영통구": "41117", 
        "용인시 수지구": "41465", "고양시 일산동구": "41285",
        "화성시": "41590", "과천시": "41290"
    }
}

# -----------------------------------------------------------
# [기능 2] 사이드바 설정 (키 저장 & 3단계 선택)
# -----------------------------------------------------------
st.sidebar.header("🔑 설정 및 조회")

# (1) API 키 자동 저장 (Session State 활용)
if 'saved_api_key' not in st.session_state:
    st.session_state['saved_api_key'] = ''

api_key_input = st.sidebar.text_input(
    "공공데이터포털 인증키 (Decoding Key)", 
    type="password", 
    value=st.session_state['saved_api_key'],
    help="한번 입력하면 새로고침 해도 유지됩니다."
)
# 입력된 값이 있으면 저장
if api_key_input:
    st.session_state['saved_api_key'] = api_key_input

st.sidebar.markdown("---")

# (2) 3단계 지역 선택 구현
# 1단계: 시/도
si_do_list = list(korea_regions.keys())
selected_si_do = st.sidebar.selectbox("1. 시/도 선택", si_do_list)

# 2단계: 구/군 (시/도 선택에 따라 바뀜)
gu_gun_dict = korea_regions[selected_si_do]
gu_gun_list = list(gu_gun_dict.keys())
selected_gu_gun = st.sidebar.selectbox("2. 구/군 선택", gu_gun_list)

# 선택된 지역의 코드 가져오기
lawd_cd = gu_gun_dict[selected_gu_gun]

# 3단계: 날짜 선택
c1, c2 = st.sidebar.columns(2)
year = c1.selectbox("년도", ["2025", "2024", "2023"], index=1)
month = c2.selectbox("월", [f"{i:02d}" for i in range(1, 13)], index=11)
deal_ymd = year + month

# -----------------------------------------------------------
# [기능 3] 데이터 가져오기 함수 (기존과 동일)
# -----------------------------------------------------------
@st.cache_data
def fetch_data(api_key, lawd_cd, deal_ymd):
    url = "https://apis.data.go.kr/1613000/RTMSDataSvcAptTrade/getRTMSDataSvcAptTrade"
    
    params = {
        "serviceKey": api_key,
        "LAWD_CD": lawd_cd,
        "DEAL_YMD": deal_ymd,
        "numOfRows": "1000",
        "pageNo": "1"
    }
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }
    
    try:
        response = requests.get(url, params=params, headers=headers, verify=False, timeout=10)
        
        try:
            root = ET.fromstring(response.content)
        except ET.ParseError:
            return f"🚨 서버 응답 오류 (XML 아님): {response.text}"
        
        header_code = root.find('.//resultCode')
        if header_code is not None:
            code_val = header_code.text.strip()
            if code_val not in ['00', '000']:
                error_msg = root.find('.//resultMsg').text
                return f"API Error: {error_msg} (코드: {code_val})"

        items = root.findall('.//item')
        if not items:
            return None
        
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

# -----------------------------------------------------------
# [기능 4] 메인 로직 (조회 버튼 및 결과 처리)
# -----------------------------------------------------------
if st.sidebar.button("🚀 데이터 조회하기"):
    # 조회를 누르면 데이터를 세션에 저장해서 유지
    st.session_state['search_clicked'] = True
    st.session_state['search_params'] = (lawd_cd, deal_ymd, selected_si_do, selected_gu_gun)

# 이전에 조회한 기록이 있으면 화면 표시
if st.session_state.get('search_clicked'):
    # 저장된 파라미터 사용
    current_lawd, current_ymd, si_name, gu_name = st.session_state['search_params']
    
    if not st.session_state['saved_api_key']:
        st.error("⚠️ 사이드바에 인증키를 입력해주세요.")
    else:
        with st.spinner(f"{si_name} {gu_name}의 {current_ymd} 데이터를 불러오는 중..."):
            result = fetch_data(st.session_state['saved_api_key'], current_lawd, current_ymd)
            
            if isinstance(result, str):
                st.error("❌ 오류가 발생했습니다.")
                st.code(result)
            elif result is None or result.empty:
                st.info("해당 지역/기간에 신고된 거래 내역이 없습니다.")
            else:
                df = result.copy()
                
                # 컬럼 통역
                col_map = {
                    'aptNm': '아파트', '단지명': '아파트',
                    'dealAmount': '거래금액', 'amount': '거래금액',
                    'excluUseAr': '전용면적', 'area': '전용면적', 
                    'umdNm': '법정동', 'dong': '법정동',
                    'floor': '층', 'dealDay': '일', 'day': '일'
                }
                df = df.rename(columns=col_map)
                
                # 필수 컬럼 채우기
                for col in ['아파트', '거래금액', '전용면적', '법정동', '층', '일']:
                    if col not in df.columns:
                        df[col] = "-" if col != '거래금액' else "0"

                # 숫자 변환
                df['거래금액_숫자'] = df['거래금액'].astype(str).str.replace(',', '').astype(int)
                df['전용면적_숫자'] = pd.to_numeric(df['전용면적'], errors='coerce').fillna(0)
                df['계약일'] = current_ymd + df['일'].astype(str).str.zfill(2)
                df['평수'] = df['전용면적_숫자'] / 3.3058
                df['평당가'] = df['거래금액_숫자'] / df['평수']

                # -----------------------------------------------------------
                # [기능 5] 3단계: 동/면 선택 (데이터 로드 후 필터링)
                # -----------------------------------------------------------
                st.sidebar.markdown("---")
                st.sidebar.subheader("📍 상세 필터")
                
                # 데이터에 있는 법정동 목록 자동 추출
                dong_list = sorted(df['법정동'].unique())
                dong_list.insert(0, "전체 보기") # 맨 앞에 전체 옵션 추가
                
                selected_dong = st.sidebar.selectbox("3. 동/면 선택", dong_list)
                
                # 필터링 적용
                if selected_dong != "전체 보기":
                    df = df[df['법정동'] == selected_dong]
                    st.info(f"📍 '{selected_dong}' 데이터만 표시합니다. ({len(df)}건)")
                else:
                    st.success(f"✅ '{gu_name}' 전체 데이터 ({len(df)}건)")

                # -----------------------------------------------------------
                # [기능 6] 결과 시각화
                # -----------------------------------------------------------
                
                # 요약 정보
                if not df.empty:
                    c1, c2, c3 = st.columns(3)
                    avg_p = df['거래금액_숫자'].mean()
                    max_p = df['거래금액_숫자'].max()
                    c1.metric("평균 거래가", f"{avg_p/10000:.1f}억원")
                    c2.metric("최고 거래가", f"{max_p/10000:.1f}억원")
                    
                    # 가장 핫한 아파트
                    top_apt = df['아파트'].mode()[0] if not df['아파트'].mode().empty else "-"
                    c3.metric("최다 거래 아파트", top_apt)
                    
                    st.divider()
                    
                    # 차트
                    st.subheader("📊 매매가 추세")
                    chart = alt.Chart(df).mark_circle(size=80).encode(
                        x=alt.X('계약일', title='날짜'),
                        y=alt.Y('거래금액_숫자', title='거래금액(만원)', scale=alt.Scale(zero=False)),
                        color=alt.Color('법정동', title='법정동'),
                        tooltip=['계약일', '아파트', '전용면적', '거래금액', '층']
                    ).interactive()
                    st.altair_chart(chart, use_container_width=True)
                    
                    # 표
                    st.subheader("📋 상세 거래 내역")
                    cols = ['계약일', '법정동', '아파트', '전용면적', '거래금액', '층']
                    st.dataframe(
                        df[cols].sort_values('계약일', ascending=False), 
                        use_container_width=True
                    )
                else:
                    st.warning("조건에 맞는 데이터가 없습니다.")

else:
    st.info("👈 사이드바에서 [조회하기] 버튼을 눌러주세요.")
