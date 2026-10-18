"""Pure search logic for fictional restaurant demonstrations."""
from dataclasses import dataclass, replace
from math import asin, cos, radians, sin, sqrt


@dataclass(frozen=True)
class Restaurant:
    name: str
    category: str
    lat: float
    lon: float
    rating: float | None
    reviews: int
    # Daily demo schedule. Closing <= opening means closing the following day.
    hours: tuple[tuple[int, int], ...] | None


def distance_km(lat: float, lon: float, place: Restaurant) -> float:
    a = sin(radians(place.lat - lat) / 2) ** 2
    a += cos(radians(lat)) * cos(radians(place.lat)) * sin(radians(place.lon - lon) / 2) ** 2
    return 6371.0088 * 2 * asin(sqrt(min(1, max(0, a))))


def minutes_until_close(hours, minute: int) -> int | None:
    """Return remaining minutes in the active interval, including overnight hours."""
    if hours is None:
        return None
    for opening, closing in hours:
        end = closing if closing > opening else closing + 1440
        for current in (minute, minute + 1440):
            if opening <= current < end:
                return end - current
    return 0


def minutes_until_open(hours, minute: int) -> int | None:
    """Daily fictional schedule only; live data uses Google's nextOpenTime."""
    if not hours or minutes_until_close(hours, minute):
        return None
    return min((opening - minute) % 1440 for opening, _ in hours)


def search(places, lat, lon, radius, minute, category='全部', only_open=False,
           min_remaining=0, sort_by='距離最近', opening_within=0):
    result = []
    for place in places:
        distance = distance_km(lat, lon, place)
        remaining = minutes_until_close(place.hours, minute)
        if opening_within:
            waiting = minutes_until_open(place.hours, minute)
            if waiting is None or not 0 < waiting <= opening_within:
                continue
        if distance > radius or (category != '全部' and place.category != category):
            continue
        if not opening_within and (only_open or min_remaining > 0) and (remaining is None or remaining <= 0):
            continue
        if not opening_within and min_remaining and remaining < min_remaining:
            continue
        result.append((place, distance, remaining))
    if sort_by == '評分最高':
        result.sort(key=lambda row: (-(row[0].rating if row[0].rating is not None else -1),
                                     -row[0].reviews, row[1], row[0].name))
    else:
        result.sort(key=lambda row: (row[1], row[0].name))
    return result


DEMO_PLACES = [
    Restaurant('範例・櫻花食堂', '日式料理', 25.018, 121.534, 4.5, 320, ((660, 870), (1020, 1290))),
    Restaurant('範例・深夜拉麵', '日式料理', 25.022, 121.535, 4.7, 180, ((1080, 120),)),
    Restaurant('範例・小巷壽司', '日式料理', 25.030, 121.540, 4.7, 25, None),
    Restaurant('範例・番茄義麵', '義式料理', 25.020, 121.531, 4.4, 210, ((660, 1260),)),
    Restaurant('範例・窯烤披薩', '義式料理', 25.036, 121.548, 4.8, 410, ((690, 1320),)),
    Restaurant('範例・晨光早餐', '早餐', 25.016, 121.532, 4.3, 85, ((360, 780),)),
    Restaurant('範例・早午餐屋', '早餐', 25.025, 121.528, 4.6, 150, ((480, 960),)),
    Restaurant('範例・轉角咖啡', '咖啡甜點', 25.019, 121.538, 4.6, 290, ((540, 1320),)),
    Restaurant('範例・午後甜點', '咖啡甜點', 25.041, 121.535, None, 0, ((720, 1140),)),
    Restaurant('範例・家常小館', '中式料理', 25.012, 121.525, 4.2, 500, ((660, 840), (1020, 1230))),
    Restaurant('範例・全天豆漿', '中式料理', 25.008, 121.540, 4.1, 670, ((0, 1440),)),
    Restaurant('範例・遠方蒸餃', '中式料理', 25.061, 121.554, 4.5, 140, ()),
]

# Keep fictional examples around the same default center as the application.
DEMO_PLACES = [replace(p, lat=p.lat + (24.9683 - 25.0173),
                       lon=p.lon + (121.1929 - 121.5398)) for p in DEMO_PLACES]
