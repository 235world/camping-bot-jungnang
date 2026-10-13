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

import hashlib
import random
import time
import urllib.parse
from datetime import datetime, timedelta, timezone
from concurrent.futures import ThreadPoolExecutor
from threading import Lock
import streamlit as st
import streamlit.components.v1 as components
import config
from campsite_checker import get_campsite_items, check_date_availability

# 한국 표준시(KST) 기준 오늘 날짜 정의
KST = timezone(timedelta(hours=9))
TODAY_KST = datetime.now(KST).date()
TODAY_KST_STR = TODAY_KST.strftime("%Y-%m-%d")

# 1. 페이지 기본 설정 (모바일 친화적)
st.set_page_config(
    page_title="중랑캠핑숲 조회",
    layout="centered",
    initial_sidebar_state="collapsed"
)

# 2. 모바일 최적화 커스텀 CSS 주입
st.markdown("""
<style>
    /* 상단 기본 메뉴, 배포 버튼, 푸터 숨김 */
    #MainMenu {visibility: hidden; display: none !important;}
    footer {visibility: hidden; display: none !important;}
    header {visibility: hidden; display: none !important;}
    .stAppDeployButton {display: none !important;}
    [data-testid="stDecoration"] {display: none !important;}
    [data-testid="stStatusWidget"] {display: none !important;}
    [data-testid="stToolbar"] {display: none !important;}
    div[class*="viewerBadge"] {display: none !important;}
    div[class*="ProfileBadge"] {display: none !important;}
    .viewerBadge_container__1QSob, .viewerBadge_link__1S137 {display: none !important;}
    [data-testid="manage-app-button"] {display: none !important;}
    
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

# PIN 번호가 URL이나 스토리지에 평문 노출되지 않도록 고유 해시 토큰 생성
AUTH_SALT = "camping_jungnang_auth_salt"
AUTH_TOKEN = hashlib.sha256(f"{AUTH_SALT}:{CORRECT_PIN}".encode()).hexdigest()[:16]

# 3. URL 파라미터 감지 및 정리
# 3-1. 기존 URL에 남아있을 수 있는 ?pin= 파라미터 감지 시 세션 인증 후 즉시 URL에서 삭제
if "pin" in st.query_params:
    legacy_pin = st.query_params.get("pin")
    if legacy_pin == CORRECT_PIN:
        st.session_state["authenticated"] = True
    del st.query_params["pin"]
    st.rerun()

# 3-2. 로컬스토리지 자동 로그인용 1회성 auth 토큰 처리 (검증 즉시 URL에서 삭제)
if "auth" in st.query_params:
    received_token = st.query_params.get("auth")
    if received_token == AUTH_TOKEN:
        st.session_state["authenticated"] = True
    del st.query_params["auth"]
    st.rerun()

is_authenticated = st.session_state.get("authenticated", False)

# 3-3. 로컬스토리지 브릿지 JavaScript (인증 토큰 및 날짜 복원)
components.html(f"""
<script>
    (function() {{
        const authToken = "{AUTH_TOKEN}";
        const todayStr = "{TODAY_KST_STR}";
        const url = new URL(window.parent.location.href);
        const storedToken = localStorage.getItem('camping_auth_token');
        const legacyPin = localStorage.getItem('camping_auth_pin');
        let storedDate = localStorage.getItem('camping_target_date');
        let shouldReload = false;

        // 과거 로컬스토리지에 저장된 평문 PIN이 있다면 해시 토큰으로 마이그레이션 후 삭제
        if (legacyPin) {{
            if (legacyPin === "{CORRECT_PIN}") {{
                localStorage.setItem('camping_auth_token', authToken);
            }}
            localStorage.removeItem('camping_auth_pin');
        }}

        // 과거 날짜이거나 이전 설정값인 경우 오늘 날짜로 갱신
        if (storedDate && storedDate < todayStr) {{
            storedDate = todayStr;
            localStorage.setItem('camping_target_date', todayStr);
            if (url.searchParams.get('date')) {{
                url.searchParams.set('date', todayStr);
                shouldReload = true;
            }}
        }}

        // 비인증 상태일 때 로컬스토리지 토큰이 유효하면 1회성 토큰 전달하여 자동 로그인
        const isSessionAuth = {"true" if is_authenticated else "false"};
        if (!isSessionAuth && storedToken === authToken && !url.searchParams.get('auth')) {{
            url.searchParams.delete('pin');
            url.searchParams.set('auth', authToken);
            shouldReload = true;
        }}

        // 날짜 복원
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

# 4. PIN 인증 확인 (인증되지 않은 경우에만 폼 표시)
if not is_authenticated:
    st.markdown("### 🔒 보안 인증")
    st.caption("비인가 접근을 방지하기 위해 PIN 번호를 입력해주세요.")
    
    pin_input = st.text_input("PIN 번호", type="password", max_chars=8, placeholder="비밀번호 입력")
    
    if st.button("확인", type="primary"):
        if pin_input == CORRECT_PIN:
            st.session_state["authenticated"] = True
            # ※ URL GET 파라미터에는 PIN 번호를 절대 넣지 않습니다!
            
            # 브라우저 localStorage에 안전한 암호화 해시 토큰 저장 (다음 방문 시 자동 패스)
            components.html(f"""
            <script>
                localStorage.setItem('camping_auth_token', '{AUTH_TOKEN}');
                localStorage.removeItem('camping_auth_pin');
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
st.markdown("## 중랑캠핑숲 조회")

# 5. 날짜 선택 로직 (오늘 날짜 KST 기준 기본값)
saved_date_str = st.query_params.get("date")
if not saved_date_str:
    default_date = TODAY_KST
else:
    try:
        parsed_date = datetime.strptime(saved_date_str, "%Y-%m-%d").date()
        # 과거 날짜인 경우 오늘 날짜로 자동 보정
        default_date = max(parsed_date, TODAY_KST)
    except Exception:
        default_date = TODAY_KST

# 달력 날짜 선택기 (min_value=TODAY_KST: 과거 날짜 선택 방지, default_date >= TODAY_KST 로 StreamlitValueBelowMinError 방지)
selected_date = st.date_input("날짜 선택", value=default_date, min_value=TODAY_KST)
selected_date_str = selected_date.strftime("%Y-%m-%d")

# 날짜 변경 시 URL 파라미터 및 localStorage 동기화
if st.query_params.get("date") != selected_date_str:
    st.query_params["date"] = selected_date_str
    components.html(f"""
    <script>
        localStorage.setItem('camping_target_date', '{selected_date_str}');
    </script>
    """, height=0)

st.write(f"**선택한 날짜:** `{selected_date_str}`")

# ====================================================================
# 공유 캐시 및 데이터 조회 모듈 (8~20명 동시 접속 시 네이버 IP 차단 완벽 방지)
# ====================================================================
_CACHE_LOCK = Lock()
_FETCH_LOCK = Lock()
_SHARED_CACHE = {}  # {date_str: {"timestamp": float, "results": list}}
CACHE_TTL = 20.0    # 20초 동안 최신 결과 공유

def fetch_campsite_status_shared(date_str: str):
    """
    공유 캐시 기능:
    - 최근 20초 이내에 누군가 조회한 결과가 있으면 해당 결과를 즉시 공유 (외부 요청 0회)
    - 캐시 만료 시 단 1개의 스레드만 네이버 조회를 수행하고, 동시 요청자는 그 결과를 공유
    - 반환값: (results, is_shared_cache, timestamp_str)
    """
    now = time.time()
    
    # 1. 기존 캐시 확인
    with _CACHE_LOCK:
        if date_str in _SHARED_CACHE:
            cached = _SHARED_CACHE[date_str]
            if now - cached["timestamp"] < CACHE_TTL:
                ts_str = time.strftime("%H:%M:%S", time.localtime(cached["timestamp"]))
                return cached["results"], True, ts_str

    # 2. 캐시 만료 시 조회 (FETCH_LOCK으로 단 1개의 스레드만 실제 조회 수행)
    with _FETCH_LOCK:
        # 더블 체크 락킹
        now = time.time()
        with _CACHE_LOCK:
            if date_str in _SHARED_CACHE:
                cached = _SHARED_CACHE[date_str]
                if now - cached["timestamp"] < CACHE_TTL:
                    ts_str = time.strftime("%H:%M:%S", time.localtime(cached["timestamp"]))
                    return cached["results"], True, ts_str
        
        # 실제 네이버 조회 수행
        sites = get_campsite_items(config.BUSINESS_ID, config.FILTER_KEYWORD)
        if not sites:
            return [], False, time.strftime("%H:%M:%S", time.localtime(now))
        
        def check_one(s):
            res = check_date_availability(
                config.BUSINESS_ID,
                s["bizItemId"],
                date_str,
                config.BUSINESS_TYPE_ID
            )
            if res and res.get("dateKey"):
                stock = res.get("stock", 0)
                booked = res.get("bookingCount", 0)
                remain = res.get("remaining", 0)
                avail = res.get("isAvailable", False)
            else:
                stock, booked, remain, avail = 0, 0, 0, False
            return {
                "id": s["bizItemId"],
                "name": s["name"],
                "stock": stock,
                "booked": booked,
                "remain": remain,
                "available": avail
            }

        with ThreadPoolExecutor(max_workers=6) as executor:
            results = list(executor.map(check_one, sites))
        
        finish_time = time.time()
        ts_str = time.strftime("%H:%M:%S", time.localtime(finish_time))
        
        with _CACHE_LOCK:
            _SHARED_CACHE[date_str] = {
                "timestamp": finish_time,
                "results": results
            }
            
        return results, False, ts_str

def render_results(results, target_date_str):
    available_sites = [r for r in results if r["available"]]
    
    if available_sites:
        st.success(f"🎉 **{target_date_str}**에 예약 가능한 사이트가 **{len(available_sites)}개** 발견되었습니다!")
        
        for site in available_sites:
            web_url = f"https://m.booking.naver.com/booking/{config.BUSINESS_TYPE_ID}/bizes/{config.BUSINESS_ID}/items/{site['id']}"
            app_deep_link = f"naversearchapp://inappbrowser?url={urllib.parse.quote(web_url, safe='')}&target=new&version=6"
            
            st.markdown(f"""
            <div class="site-card">
                <div class="site-title">{site['name']}</div>
                <div class="site-badge">잔여: {site['remain']}자리 (전체 {site['stock']} / 예약 {site['booked']})</div>
                <a href="{app_deep_link}" class="app-link-btn">🚀 네이버 앱으로 바로 예약하기</a>
                <a href="{web_url}" target="_blank" class="web-link-btn">🌐 웹 브라우저로 열기</a>
            </div>
            """, unsafe_allow_html=True)
    else:
        st.warning(f"🔒 **{target_date_str}** 전 사이트 매진 상태입니다.")

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

# 세션 상태 초기화
if "auto_monitor" not in st.session_state:
    st.session_state["auto_monitor"] = False
if "monitor_start_time" not in st.session_state:
    st.session_state["monitor_start_time"] = 0
if "monitor_logs" not in st.session_state:
    st.session_state["monitor_logs"] = []
if "last_results" not in st.session_state:
    st.session_state["last_results"] = None

is_monitoring = st.session_state["auto_monitor"]

# 6. 조회 및 자동감시 버튼 영역
col_btn1, col_btn2 = st.columns(2)

with col_btn1:
    btn_single = st.button("즉시 조회", use_container_width=True, disabled=is_monitoring)

with col_btn2:
    if not is_monitoring:
        btn_start_monitor = st.button("1시간 자동감시 시작", type="primary", use_container_width=True)
        btn_stop_monitor = False
    else:
        btn_stop_monitor = st.button("자동감시 중지", type="secondary", use_container_width=True)
        btn_start_monitor = False

# 화면을 나가면 꺼진다는 안내 문구 (요청사항: 문구에 이모지 사용안함)
st.markdown("<div style='font-size:0.83rem; color:#64748b; margin-top:2px; margin-bottom:14px; text-align:center;'>화면을 나가면 자동감시가 중단됩니다. (최대 1시간 동작)</div>", unsafe_allow_html=True)

# 버튼 이벤트 처리
if btn_start_monitor:
    st.session_state["auto_monitor"] = True
    st.session_state["monitor_start_time"] = time.time()
    st.session_state["monitor_logs"] = []
    st.rerun()

if btn_stop_monitor:
    st.session_state["auto_monitor"] = False
    st.rerun()

if btn_single:
    with st.spinner("네이버 예약 실시간 재고 확인 중..."):
        results, is_shared, ts_str = fetch_campsite_status_shared(selected_date_str)
        st.session_state["last_results"] = (results, selected_date_str)
        st.rerun()

# 7. 실행 및 결과 렌더링
if is_monitoring:
    now_time = time.time()
    start_time = st.session_state.get("monitor_start_time", now_time)
    elapsed = now_time - start_time
    
    # 최대 1시간(3600초) 초과 시 자동 종료
    if elapsed >= 3600:
        st.session_state["auto_monitor"] = False
        st.info("최대 감시 시간(1시간)이 경과하여 자동감시가 종료되었습니다.")
        st.rerun()
    
    elapsed_m = int(elapsed // 60)
    elapsed_s = int(elapsed % 60)
    st.info(f"자동감시 진행 중 (경과: {elapsed_m:02d}분 {elapsed_s:02d}초 / 최대 60분)")
    
    # 1. 요청 결과를 다 가져온다 (공유 캐시 활용)
    results, is_shared, ts_str = fetch_campsite_status_shared(selected_date_str)
    st.session_state["last_results"] = (results, selected_date_str)
    available_sites = [r for r in results if r["available"]]
    
    # 간단 호출 로그 기록
    cache_badge = "공유 캐시" if is_shared else "신규 조회"
    log_text = f"[{ts_str}] 잔여 {len(available_sites)}개 ({cache_badge})"
    st.session_state["monitor_logs"].insert(0, log_text)
    st.session_state["monitor_logs"] = st.session_state["monitor_logs"][:15]
    
    # 화면 렌더링
    render_results(results, selected_date_str)
    
    # 하단 호출 로그 표시
    if st.session_state["monitor_logs"]:
        st.markdown("##### 자동감시 호출 기록")
        st.code("\n".join(st.session_state["monitor_logs"]), language="text")
        
    # 잔여 객실 발견 시 자동감시 종료 (소리 기능 미사용)
    if available_sites:
        st.session_state["auto_monitor"] = False
        st.stop()
    else:
        # 결과를 모두 가져온 뒤 30초~70초 사이 랜덤 대기 후 다음 자동 실행
        wait_seconds = random.randint(30, 70)
        countdown_box = st.empty()
        for remaining in range(wait_seconds, 0, -1):
            countdown_box.markdown(
                f"<div style='font-size:0.88rem; color:#475569; background:#f1f5f9; border:1px solid #cbd5e1; padding:8px 12px; border-radius:10px; text-align:center; margin-top:12px;'>"
                f"다음 자동 조회까지 약 <b>{remaining}초</b> 대기 중</div>",
                unsafe_allow_html=True
            )
            time.sleep(1.0)
        countdown_box.empty()
        st.rerun()

elif st.session_state.get("last_results"):
    results, r_date = st.session_state["last_results"]
    render_results(results, r_date)
    
    if st.session_state.get("monitor_logs"):
        st.markdown("##### 자동감시 호출 기록")
        st.code("\n".join(st.session_state["monitor_logs"]), language="text")

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
            localStorage.removeItem('camping_auth_token');
            localStorage.removeItem('camping_auth_pin');
            localStorage.removeItem('camping_target_date');
            window.parent.location.replace(window.parent.location.origin + window.parent.location.pathname);
        </script>
        """, height=0)
        st.rerun()
