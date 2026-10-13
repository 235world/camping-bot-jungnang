# ==========================================
# 캠핑장 예약 모니터링 봇 설정 파일 (config.py)
# ==========================================

# 1. 대상 캠핑장 정보
BUSINESS_ID = "387475"          # 중랑캠핑숲 네이버 예약 비즈니스 ID
BUSINESS_TYPE_ID = 5            # 네이버 예약 카테고리 타입
from datetime import datetime, timezone, timedelta

# 2. 예약 목표 날짜 (YYYY-MM-DD 형식)
# 기본값은 항상 오늘 날짜(한국 시간 KST 기준)로 설정됩니다.
KST = timezone(timedelta(hours=9))
TARGET_DATE = datetime.now(KST).strftime("%Y-%m-%d")

# 3. 객실 필터링 키워드
# 이름에 이 키워드가 포함된 객실만 감시합니다.
FILTER_KEYWORD = "오토캠핑"

# 4. 모니터링 주기 (초 단위)
# 너무 빠르면 네이버에서 일시적 IP 차단을 할 수 있으므로 3초~5초 권장
INTERVAL_SECONDS = 3.0

# 5. 동작 설정
AUTO_OPEN_BROWSER = True        # 빈자리 발견 시 즉시 브라우저로 예약 페이지 열기

# 6. 텔레그램 알림 설정 (선택 사항)
# 텔레그램 BotFather에서 봇을 만들고 토큰과 chat_id를 넣으면 스마트폰으로 즉시 알림 전송
TELEGRAM_ENABLE = False
TELEGRAM_BOT_TOKEN = ""         # 예: "123456789:ABCdefGhIJKlmNoPQRsTUVwxyZ"
TELEGRAM_CHAT_ID = ""           # 예: "123456789"

# 7. 디스코드 웹훅 알림 설정 (선택 사항)
DISCORD_ENABLE = False
DISCORD_WEBHOOK_URL = ""        # 디스코드 채널 웹훅 URL
