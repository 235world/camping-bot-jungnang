"""
====================================================================
🏕️ 중랑캠핑숲 오토캠핑장 실시간 취소표 조회 앱 (Streamlit Cloud 최적화)
====================================================================
기능:
1. PIN 보안 인증 (기본 1919) - 로컬스토리지 & URL 파라미터 연동으로 다음 방문 시 자동 패스
2. 모바일 반응형 UI/UX (터치 친화적 디자인, 여백 최적화)
3. 쉬운 날짜 선택 (10월 9일 한글날, 주말 퀵 버튼 + 달력 선택)
4. 선택한 날짜 기억 (로컬스토리지 영구 보관)
5. 실시간 잔여석 조회 & 네이버 앱 다이렉트 딥링크(naversearchapp://) 지원
====================================================================
"""

import urllib.parse
from datetime import datetime, timedelta
import streamlit as st
import streamlit.components.v1 as components
import config
from campsite_checker import get_campsite_items, check_date_availability

# 1. 페이지 기본 설정 (모바일 친화적)
st.set_page_config(
    page_title="중랑캠핑숲 예약 조회기",
    page_icon="🏕️",
    layout="centered",
    initial_sidebar_state="collapsed"
)

# 2. 모바일 최적화 커스텀 CSS 주입
st.markdown("""
<style>
    /* 상단 기본 메뉴 및 푸터 숨김 (앱 같은 느낌 연출) */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    
    /* 모바일 여백 최적화 */
    .block-container {
        padding-top: 1.2rem !important;
        padding-bottom: 2rem !important;
        padding-left: 0.8rem !important;
        padding-right: 0.8rem !important;
        max-width: 520px !important;
    }

    /* 버튼 터치 최적화 */
    .stButton > button {
        width: 100% !important;
        height: 52px !important;
        border-radius: 14px !important;
        font-size: 1.05rem !important;
        font-weight: 700 !important;
        transition: transform 0.1s ease;
    }
    .stButton > button:active {
        transform: scale(0.98);
    }

    /* 카드 스타일 */
    .site-card {
        background-color: #ffffff;
        border: 2px solid #10b981;
        border-radius: 16px;
        padding: 16px;
        margin-bottom: 14px;
        box-shadow: 0 4px 14px rgba(16, 185, 129, 0.15);
    }
    .site-title {
        font-size: 1.1rem;
        font-weight: 800;
        color: #0f172a;
        margin-bottom: 6px;
    }
    .site-badge {
        display: inline-block;
        background-color: #10b981;
        color: white;
        font-size: 0.85rem;
        font-weight: 700;
        padding: 3px 10px;
        border-radius: 8px;
        margin-bottom: 12px;
    }
    .app-link-btn {
        display: block;
        width: 100%;
        text-align: center;
        background: linear-gradient(135deg, #03c75a 0%, #00b04e 100%);
        color: white !important;
        text-decoration: none !important;
        padding: 13px;
        border-radius: 12px;
        font-weight: 800;
        font-size: 1rem;
        box-shadow: 0 4px 10px rgba(3, 199, 90, 0.3);
        margin-bottom: 8px;
    }
    .web-link-btn {
        display: block;
        width: 100%;
        text-align: center;
        background: #f1f5f9;
        color: #475569 !important;
        text-decoration: none !important;
        padding: 9px;
        border-radius: 10px;
        font-weight: 600;
        font-size: 0.85rem;
    }
</style>
""", unsafe_allow_html=True)

# Streamlit Cloud의 Secrets(비밀 금고)에 PIN이 등록되어 있으면 해당 값을 사용하고,
# 등록되어 있지 않으면 기본값 "1919"를 사용합니다.
try:
    CORRECT_PIN = str(st.secrets.get("PIN", "1919"))
except Exception:
    CORRECT_PIN = "1919"

# 3. 로컬스토리지 브릿지 JavaScript (PIN 번호 및 날짜 저장/복원)
# URL 파라미터가 비어있을 때 브라우저 localStorage를 확인하여 자동 로그인 및 날짜 복원
components.html(f"""
<script>
    (function() {{
        const correctPin = "{CORRECT_PIN}";
        const url = new URL(window.parent.location.href);
        const storedPin = localStorage.getItem('camping_auth_pin');
        const storedDate = localStorage.getItem('camping_target_date');
        let shouldReload = false;

        // 1. PIN 복원
        if (storedPin === correctPin && url.searchParams.get('pin') !== correctPin) {{
            url.searchParams.set('pin', storedPin);
            shouldReload = true;
        }}

        // 2. 날짜 복원
        if (storedDate && !url.searchParams.get('date')) {{
            url.searchParams.set('date', storedDate);
            shouldReload = true;
        }}

        if (shouldReload) {{
            window.parent.location.replace(url.href);
        }}
    }})();
</script>
""", height=0)

# 4. PIN 인증 확인
url_pin = st.query_params.get("pin")
is_authenticated = (url_pin == CORRECT_PIN) or st.session_state.get("authenticated", False)

if not is_authenticated:
    st.markdown("### 🔒 보안 인증")
    st.caption("비인가 접근을 방지하기 위해 PIN 번호를 입력해주세요.")
    
    pin_input = st.text_input("PIN 번호", type="password", max_chars=8, placeholder="비밀번호 입력")
    
    if st.button("확인", type="primary"):
        if pin_input == CORRECT_PIN:
            st.session_state["authenticated"] = True
            st.query_params["pin"] = CORRECT_PIN
            
            # 브라우저 localStorage에 PIN 저장 (다음 방문 시 자동 패스)
            components.html(f"""
            <script>
                localStorage.setItem('camping_auth_pin', '{CORRECT_PIN}');
            </script>
            """, height=0)
            
            st.rerun()
        else:
            st.error("PIN 번호가 일치하지 않습니다.")
    
    st.stop()

# -------------------------------------------------------------
# 인증 완료 후 메인 화면
# -------------------------------------------------------------

# 헤더
st.markdown("## 🏕️ 중랑캠핑숲 실시간 조회")
st.caption("오토캠핑사이트 잔여석 탐색 & 네이버 앱 원클릭 예약")

# 5. 날짜 선택 로직 (로컬스토리지 / URL 기억 연동)
saved_date_str = st.query_params.get("date", config.TARGET_DATE)
try:
    default_date = datetime.strptime(saved_date_str, "%Y-%m-%d").date()
except Exception:
    default_date = datetime.now().date()

today = datetime.now().date()

# 퀵 날짜 계산
this_saturday = today + timedelta(days=(5 - today.weekday()) % 7)
next_saturday = this_saturday + timedelta(days=7)

st.markdown("##### 📅 빠른 날짜 선택")
c1, c2, c3 = st.columns(3)
quick_chosen = None

if c1.button("🎉 10월 9일\n(한글날)", use_container_width=True):
    quick_chosen = datetime(today.year, 10, 9).date()

if c2.button(f"이번주 토\n({this_saturday.strftime('%m/%d')})", use_container_width=True):
    quick_chosen = this_saturday

if c3.button(f"다음주 토\n({next_saturday.strftime('%m/%d')})", use_container_width=True):
    quick_chosen = next_saturday

if quick_chosen:
    default_date = quick_chosen
    st.query_params["date"] = quick_chosen.strftime("%Y-%m-%d")

# 달력 날짜 선택기
selected_date = st.date_input("직접 날짜 선택", value=default_date, min_value=today)
selected_date_str = selected_date.strftime("%Y-%m-%d")

# 날짜 변경 시 URL 파라미터 및 localStorage 동기화
if st.query_params.get("date") != selected_date_str:
    st.query_params["date"] = selected_date_str
    components.html(f"""
    <script>
        localStorage.setItem('camping_target_date', '{selected_date_str}');
    </script>
    """, height=0)

st.write(f"👉 **선택된 날짜:** `{selected_date_str}`")

# 6. 현황 조회 버튼
if st.button("🔍 실시간 예약 현황 조회하기", type="primary", use_container_width=True):
    with st.spinner("네이버 예약 실시간 재고 확인 중..."):
        sites = get_campsite_items(config.BUSINESS_ID, config.FILTER_KEYWORD)
        
        if not sites:
            st.error("사이트 목록을 가져오지 못했습니다.")
        else:
            results = []
            progress_bar = st.progress(0)
            
            for idx, s in enumerate(sites):
                res = check_date_availability(
                    config.BUSINESS_ID,
                    s["bizItemId"],
                    selected_date_str,
                    config.BUSINESS_TYPE_ID
                )
                
                if res and res.get("dateKey"):
                    stock = res.get("stock", 0)
                    booked = res.get("bookingCount", 0)
                    remain = res.get("remaining", 0)
                    avail = res.get("isAvailable", False)
                else:
                    stock, booked, remain, avail = 0, 0, 0, False

                results.append({
                    "id": s["bizItemId"],
                    "name": s["name"],
                    "stock": stock,
                    "booked": booked,
                    "remain": remain,
                    "available": avail
                })
                progress_bar.progress((idx + 1) / len(sites))
                
            progress_bar.empty()
            
            available_sites = [r for r in results if r["available"]]
            
            if available_sites:
                st.balloons()
                st.success(f"🎉 **{selected_date_str}**에 예약 가능한 사이트가 **{len(available_sites)}개** 발견되었습니다!")
                
                for site in available_sites:
                    # 네이버 모바일 웹 URL
                    web_url = f"https://m.booking.naver.com/booking/{config.BUSINESS_TYPE_ID}/bizes/{config.BUSINESS_ID}/items/{site['id']}"
                    
                    # 네이버 앱 전용 딥링크 스킴 (네이버 앱이 즉시 실행되어 인앱 브라우저로 열림)
                    app_deep_link = f"naversearchapp://inappbrowser?url={urllib.parse.quote(web_url, safe='')}&target=new&version=6"
                    
                    # 카드 UI 렌더링
                    st.markdown(f"""
                    <div class="site-card">
                        <div class="site-title">{site['name']}</div>
                        <div class="site-badge">잔여: {site['remain']}자리 (전체 {site['stock']} / 예약 {site['booked']})</div>
                        <a href="{app_deep_link}" class="app-link-btn">🚀 네이버 앱으로 바로 예약하기</a>
                        <a href="{web_url}" target="_blank" class="web-link-btn">🌐 웹 브라우저로 열기</a>
                    </div>
                    """, unsafe_allow_html=True)
            else:
                st.warning(f"🔒 **{selected_date_str}** 전 사이트 매진 상태입니다.")

            # 전체 사이트 테이블 (접기/펼치기)
            with st.expander(f"📋 전체 {len(results)}개 사이트 상세 현황 보기"):
                table_data = []
                for r in results:
                    status = f"🔥 가능 ({r['remain']})" if r["available"] else "🔒 마감"
                    table_data.append({
                        "사이트명": r["name"],
                        "수량(예약/전체)": f"{r['booked']}/{r['stock']}",
                        "상태": status
                    })
                st.table(table_data)

st.markdown("---")
col_footer_left, col_footer_right = st.columns([2, 1])
with col_footer_left:
    st.caption("🔒 본 서비스는 개인 전용으로 인증된 기기에서만 동작합니다.")
with col_footer_right:
    if st.button("로그아웃", use_container_width=True):
        st.query_params.clear()
        st.session_state["authenticated"] = False
        components.html("""
        <script>
            localStorage.removeItem('camping_auth_pin');
            localStorage.removeItem('camping_target_date');
            window.parent.location.replace(window.parent.location.origin + window.parent.location.pathname);
        </script>
        """, height=0)
        st.rerun()
