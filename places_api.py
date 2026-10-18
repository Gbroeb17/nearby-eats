"""Google Places adapter. Never include credentials in errors or stored results."""
import json
from math import isfinite, floor, ceil
from datetime import datetime, timezone, timedelta
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
from restaurant import Restaurant, distance_km

FIELDS = ','.join('places.' + field for field in (
    'displayName', 'location', 'primaryType', 'types', 'primaryTypeDisplayName',
    'rating', 'userRatingCount', 'currentOpeningHours', 'googleMapsUri',
    'formattedAddress', 'businessStatus', 'utcOffsetMinutes', 'attributions')) + ',routingSummaries'


def walking_route(summary):
    """Unavailable/invalid route data stays unknown; never infer from straight distance."""
    legs = summary.get('legs', []) if isinstance(summary, dict) else []
    if len(legs) != 1 or not isinstance(legs[0], dict):
        return None
    duration = legs[0].get('duration', '')
    meters = legs[0].get('distanceMeters')
    try:
        seconds = float(duration[:-1]) if isinstance(duration, str) and duration.endswith('s') else -1
    except ValueError:
        return None
    if not isfinite(seconds) or seconds < 0:
        return None
    if type(meters) not in (int, float) or not isfinite(meters) or meters < 0:
        return None
    return {'seconds': seconds, 'meters': meters}


def attach_walking_routes(payload):
    places = payload.get('places', [])
    summaries = payload.get('routingSummaries', [])
    for index, place in enumerate(places):
        place['_walking'] = walking_route(summaries[index]) if index < len(summaries) else None
    return places


def arrival_minutes(end, now, seconds):
    return floor(((end - now).total_seconds() - seconds) / 60) if end is not None else None


def fetch_nearby(key, lat, lon, radius):
    if not key or key == '請在這裡貼上你的金鑰':
        raise ValueError('尚未設定有效的 GOOGLE_PLACES_API_KEY。')
    body = dict(includedTypes=['restaurant'], maxResultCount=20,
                rankPreference='DISTANCE', languageCode='zh-TW',
                routingParameters={'origin': {'latitude': lat, 'longitude': lon}, 'travelMode': 'WALK'},
                locationRestriction={'circle': {'center': {'latitude': lat, 'longitude': lon},
                                                'radius': radius * 1000}})
    request = Request('https://places.googleapis.com/v1/places:searchNearby',
                      data=json.dumps(body).encode(), method='POST',
                      headers={'Content-Type': 'application/json', 'X-Goog-Api-Key': key,
                               'X-Goog-FieldMask': FIELDS})
    try:
        with urlopen(request, timeout=20) as response:
            return attach_walking_routes(json.load(response))
    except HTTPError as error:
        hints = {400: '請確認搜尋參數與 API 設定。', 403: '請確認帳單、Places API (New) 啟用狀態與金鑰限制。',
                 429: '配額已用完或請求太頻繁，請稍後再試。'}
        raise ValueError(f'Google 回應 {error.code}。{hints.get(error.code, "服務暫時無法使用。")}') from None
    except (URLError, TimeoutError, OSError):
        raise ValueError('無法連線 Google，請檢查網路或稍後再試。') from None
    except (ValueError, KeyError):
        raise ValueError('Google 回傳資料格式異常，請稍後再試。') from None


def category_of(place):
    mapping = {'japanese_restaurant': '日式料理', 'sushi_restaurant': '日式料理',
               'ramen_restaurant': '日式料理', 'italian_restaurant': '義式料理',
               'pizza_restaurant': '義式料理', 'chinese_restaurant': '中式料理',
               'taiwanese_restaurant': '台式料理', 'breakfast_restaurant': '早餐',
               'brunch_restaurant': '早餐', 'cafe': '咖啡甜點', 'coffee_shop': '咖啡甜點',
               'dessert_shop': '咖啡甜點', 'korean_restaurant': '韓式料理',
               'thai_restaurant': '泰式料理', 'vietnamese_restaurant': '越式料理',
               'vegetarian_restaurant': '蔬食料理', 'vegan_restaurant': '蔬食料理'}
    for kind in [place.get('primaryType')] + place.get('types', []):
        if kind in mapping:
            return mapping[kind]
    label = place.get('primaryTypeDisplayName', {}).get('text')
    return label if label and place.get('primaryType') != 'restaurant' else '其他餐廳'


def opening_status(place, now):
    """Return open flag, remaining minutes, localized closing timestamp."""
    if place.get('businessStatus') in ('CLOSED_TEMPORARILY', 'CLOSED_PERMANENTLY'):
        return False, None, None
    hours = place.get('currentOpeningHours', {})
    end = None
    if hours.get('nextCloseTime'):
        try:
            end = datetime.fromisoformat(hours['nextCloseTime'].replace('Z', '+00:00'))
        except ValueError:
            pass
    remaining = max(0, int((end - now).total_seconds() // 60)) if end else None
    opened = hours.get('openNow')
    if end and end <= now:
        opened = None  # Cached snapshot expired: don't infer a later reopening.
        remaining = None
    offset = place.get('utcOffsetMinutes')
    local_end = end.astimezone(timezone(timedelta(minutes=offset))) if end and offset is not None else end
    return opened, remaining, local_end


def next_opening(place, now):
    """Return wait minutes and next opening timestamp; never invent missing hours."""
    if place.get('businessStatus') in ('CLOSED_TEMPORARILY', 'CLOSED_PERMANENTLY'):
        return None, None
    hours = place.get('currentOpeningHours', {})
    if hours.get('openNow') is not False:
        return None, None
    try:
        opening = datetime.fromisoformat(hours['nextOpenTime'].replace('Z', '+00:00'))
        if opening.tzinfo is None:
            return None, None
        waiting = max(0, ceil((opening - now).total_seconds() / 60))
        offset = place.get('utcOffsetMinutes')
        local = opening.astimezone(timezone(timedelta(minutes=offset))) if offset is not None else opening
        return waiting, local
    except (KeyError, ValueError, TypeError, OverflowError):
        return None, None


def live_rows(places, lat, lon, radius, only_open, min_remaining, sort_by, now,
              max_walk=0):
    rows = []
    for raw in places:
        loc = raw.get('location', {})
        if 'latitude' not in loc or 'longitude' not in loc:
            continue
        place = Restaurant(raw.get('displayName', {}).get('text', '未命名餐廳'),
                           category_of(raw), loc['latitude'], loc['longitude'],
                           raw.get('rating'), raw.get('userRatingCount', 0), None)
        distance = distance_km(lat, lon, place)
        opened, remaining, end = opening_status(raw, now)
        if distance > radius or (only_open and opened is not True):
            continue
        if min_remaining and (opened is not True or remaining is None or remaining < min_remaining):
            continue
        walk = raw.get('_walking')
        if max_walk and (walk is None or walk['seconds'] > max_walk * 60):
            continue
        rows.append((place, distance, (opened, remaining, end, raw)))
    if sort_by == '步行最快':
        rows.sort(key=lambda r: (r[2][3].get('_walking') is None,
                                (r[2][3].get('_walking') or {}).get('seconds', float('inf')), r[1]))
    elif sort_by == '評分最高':
        rows.sort(key=lambda r: (-(r[0].rating if r[0].rating is not None else -1), -r[0].reviews, r[1]))
    else:
        rows.sort(key=lambda r: r[1])
    return rows
