import sys
import json
import time
import urllib.request
import urllib.error
import webbrowser
from typing import List, Dict, Any, Optional

# UTF-8 출력 보장 (Windows 콘솔 한글 깨짐 방지)
if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except AttributeError:
        pass

GRAPHQL_URL = "https://m.booking.naver.com/graphql"
DEFAULT_HEADERS = {
    "Content-Type": "application/json",
    "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1",
    "Referer": "https://m.booking.naver.com/"
}

def get_campsite_items(business_id: str, keyword: str = "") -> List[Dict[str, Any]]:
    """
    네이버 예약 비즈니스에 등록된 모든 아이템 중 특정 키워드가 포함된 목록을 가져옵니다.
    """
    query = """
    query bizItems($input: BizItemsParams) {
      bizItems(input: $input) {
        id
        bizItemId
        name
        bizItemType
        desc
      }
    }
    """
    payload = {
        "query": query,
        "variables": {
            "input": {
                "businessId": business_id
            }
        }
    }
    req = urllib.request.Request(
        GRAPHQL_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers=DEFAULT_HEADERS
    )
    
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            all_items = data.get("data", {}).get("bizItems", [])
            if keyword:
                return [it for it in all_items if keyword in it.get("name", "")]
            return all_items
    except Exception as e:
        print(f"[오류] 상품 목록을 불러오는 중 문제가 발생했습니다: {e}")
        return []

def check_date_availability(
    business_id: str,
    biz_item_id: str,
    target_date: str,
    business_type_id: int = 5
) -> Optional[Dict[str, Any]]:
    """
    해당 객실의 특정 날짜 예약 가능 여부를 조회합니다.
    - stock: 전체 수량
    - bookingCount: 예약된 수량
    - isAvailable: 영업일 및 판매일이면서 잔여 수량(stock - bookingCount)이 1 이상인 경우 True
    """
    query = """
    query schedule($scheduleParams: ScheduleParams) {
      schedule(input: $scheduleParams) {
        bizItemSchedule {
          daily {
            summary {
              dateKey
              stock
              bookingCount
              isBusinessDay
              isSaleDay
            }
          }
        }
      }
    }
    """
    payload = {
        "query": query,
        "variables": {
            "scheduleParams": {
                "businessId": business_id,
                "bizItemId": biz_item_id,
                "businessTypeId": business_type_id,
                "startDateTime": f"{target_date}T00:00:00",
                "endDateTime": f"{target_date}T00:00:00"
            }
        }
    }
    req = urllib.request.Request(
        GRAPHQL_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            **DEFAULT_HEADERS,
            "Referer": f"https://m.booking.naver.com/booking/{business_type_id}/bizes/{business_id}/items/{biz_item_id}"
        }
    )
    
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            summary = data.get("data", {}).get("schedule", {}).get("bizItemSchedule", {}).get("daily", {}).get("summary", [])
            if summary:
                s = summary[0]
                stock = s.get("stock", 0)
                booked = s.get("bookingCount", 0)
                is_bus = s.get("isBusinessDay", False)
                is_sale = s.get("isSaleDay", False)
                remaining = max(0, stock - booked)
                is_available = is_bus and is_sale and (remaining > 0)
                return {
                    "dateKey": s.get("dateKey"),
                    "stock": stock,
                    "bookingCount": booked,
                    "remaining": remaining,
                    "isAvailable": is_available
                }
    except Exception as e:
        return {"error": str(e), "isAvailable": False}
    
    return None

def trigger_alerts(site_name: str, biz_item_id: str, business_id: str, target_date: str, cfg):
    """
    빈자리가 발견되었을 때 사운드, 브라우저 팝업, 텔레그램/디스코드 알림을 실행합니다.
    """
    booking_url = f"https://m.booking.naver.com/booking/{cfg.BUSINESS_TYPE_ID}/bizes/{business_id}/items/{biz_item_id}"
    message = f"🚨 [캠핑장 빈자리 발견!] 🚨\n사이트: {site_name}\n날짜: {target_date}\n예약 링크: {booking_url}"
    
    print("\n" + "!" * 60)
    print(f"🔥 빈자리 발견! [{site_name}]")
    print(f"🔗 예약 링크: {booking_url}")
    print("!" * 60 + "\n")
    
    # 1. 브라우저로 예약 페이지 즉시 열기
    if getattr(cfg, "AUTO_OPEN_BROWSER", True):
        try:
            webbrowser.open(booking_url)
        except Exception as e:
            print(f"[알림 오류] 브라우저 열기 실패: {e}")

    # 3. 텔레그램 알림 전송
    if getattr(cfg, "TELEGRAM_ENABLE", False) and cfg.TELEGRAM_BOT_TOKEN and cfg.TELEGRAM_CHAT_ID:
        try:
            tg_url = f"https://api.telegram.org/bot{cfg.TELEGRAM_BOT_TOKEN}/sendMessage"
            data = urllib.parse.urlencode({"chat_id": cfg.TELEGRAM_CHAT_ID, "text": message}).encode("utf-8")
            tg_req = urllib.request.Request(tg_url, data=data)
            urllib.request.urlopen(tg_req, timeout=5)
            print("📱 텔레그램 알림 발송 완료!")
        except Exception as e:
            print(f"[알림 오류] 텔레그램 전송 실패: {e}")

    # 4. 디스코드 웹훅 전송
    if getattr(cfg, "DISCORD_ENABLE", False) and cfg.DISCORD_WEBHOOK_URL:
        try:
            dc_payload = json.dumps({"content": message}).encode("utf-8")
            dc_req = urllib.request.Request(
                cfg.DISCORD_WEBHOOK_URL,
                data=dc_payload,
                headers={"Content-Type": "application/json", "User-Agent": "CampingBot"}
            )
            urllib.request.urlopen(dc_req, timeout=5)
            print("💬 디스코드 알림 발송 완료!")
        except Exception as e:
            print(f"[알림 오류] 디스코드 전송 실패: {e}")
