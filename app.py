from collections import defaultdict
from datetime import datetime, timezone, time, timedelta
from places_api import fetch_nearby, live_rows, arrival_minutes, next_opening
from math import ceil
from restaurant import DEMO_PLACES, search, minutes_until_open
import streamlit as st
import sqlite3
from usage_limit import DEFAULT_LIMIT, DEFAULT_DB, month_key, used_count, limited_search
from location_picker import device_location, valid_position

st.set_page_config(page_title='附近吃什麼？', page_icon='🍜', layout='wide')
st.title('🍜 附近吃什麼？')
st.write('依種類找餐廳，看看哪些店還來得及吃。')
mode = st.radio('資料來源', ['Google 真實搜尋', '模擬展示'], horizontal=True)
live = mode == 'Google 真實搜尋'
if live:
    st.info('按「搜尋附近餐廳」才會向 Google 發出一次請求，同時取得餐廳與步行預估（可能計費）。分類與排序不會新增請求。每次最多取得直線距離最近的 20 家餐廳，不包含範圍內所有店家。')
    st.caption('步行時間以搜尋中心為起點。Google 步行路線可能缺少人行道或步道資訊，請依現場情況通行；預估未包含候餐、點餐與最後收客時間。')
else:
    st.warning('展示模式：所有店名、評分、座標與每日營業時段都是虛構資料，不代表真實店家。')

with st.sidebar:
    st.header('搜尋條件')
    st.session_state.setdefault('search_lat', 24.9683)
    st.session_state.setdefault('search_lon', 121.1929)
    st.session_state.setdefault('location_label', '中央大學周邊（預設）')
    position = device_location(key='device_position', default=None)
    if valid_position(position) and position.get('event_id') != st.session_state.get('location_event'):
        st.session_state.search_lat = float(position['lat'])
        st.session_state.search_lon = float(position['lon'])
        st.session_state.location_event = position.get('event_id')
        st.session_state.location_label = '裝置目前位置'
        accuracy = position.get('accuracy')
        st.session_state.location_accuracy = accuracy if type(accuracy) in (int, float) else None
    if st.button('使用中央大學周邊'):
        st.session_state.search_lat = 24.9683
        st.session_state.search_lon = 121.1929
        st.session_state.location_label = '中央大學周邊'
        st.session_state.location_accuracy = None
    st.caption('搜尋中心：' + st.session_state.location_label)
    accuracy = st.session_state.get('location_accuracy')
    if accuracy is not None:
        st.caption(f'定位誤差約 {accuracy:.0f} 公尺；電腦定位可能較不精確。')
    with st.expander('手動調整位置（選用）'):
        def mark_manual():
            st.session_state.location_label = '手動指定位置'
            st.session_state.location_accuracy = None
        lat = st.number_input('緯度', min_value=-90.0, max_value=90.0,
                              key='search_lat', format='%.6f', on_change=mark_manual)
        lon = st.number_input('經度', min_value=-180.0, max_value=180.0,
                              key='search_lon', format='%.6f', on_change=mark_manual)
    radius = st.select_slider('直線搜尋半徑（公里）', options=[1, 3, 5], value=3)
    sort_by = st.selectbox('各種類內排序', ['距離最近', '評分最高', '步行最快'] if live else ['距離最近', '評分最高'])
    max_walk = 0
    if live:
        max_walk = st.selectbox('最多步行多久', [0, 5, 10, 15, 20, 30],
                               format_func=lambda x: '不限' if x == 0 else f'{x} 分鐘')
    st.session_state.setdefault('only_open_filter', True)
    st.session_state.setdefault('opening_soon_filter', False)
    def choose_open_now():
        if st.session_state.only_open_filter:
            st.session_state.opening_soon_filter = False
    def choose_opening_soon():
        if st.session_state.opening_soon_filter:
            st.session_state.only_open_filter = False
            st.session_state.min_remaining_filter = 0
    only_open = st.checkbox('只看營業中', key='only_open_filter', on_change=choose_open_now)
    opening_soon = st.checkbox('30 分鐘內會開門', key='opening_soon_filter', on_change=choose_opening_soon)
    if opening_soon:
        st.caption('只顯示目前休息中、未來 30 分鐘內預計開門的店家。')
    if only_open:
        st.caption('取消「只看營業中」可查看休息中餐廳的開門倒數。')
    min_remaining = st.selectbox('至少多久後才打烊', [0, 30, 60, 90],
                                key='min_remaining_filter', disabled=opening_soon,
                                format_func=lambda x: '不限' if x == 0 else f'{x} 分鐘')
    demo_time = time(19, 0)
    if not live:
        demo_time = st.time_input('模擬查詢時間（台灣時間）', value=demo_time)
        st.caption('展示時段假設每天相同。')
    blocked = False
    limit = DEFAULT_LIMIT
    external_used = 0
    quota_path = None
    usage_slot = st.empty()
    if live:
        try:
            backend = st.secrets.get('QUOTA_BACKEND', 'postgres')
            if backend == 'sqlite':
                quota_path = DEFAULT_DB
            elif backend == 'postgres':
                quota_path = st.secrets.get('QUOTA_DATABASE_URL', '')
                if not quota_path.startswith(('postgres://', 'postgresql://')):
                    raise ValueError('尚未設定雲端用量資料庫。')
            else:
                raise ValueError('未知用量儲存方式。')
            limit = st.secrets.get('MONTHLY_REQUEST_LIMIT', DEFAULT_LIMIT)
            external_used = st.secrets.get('EXTERNAL_USAGE_BY_MONTH', {}).get(month_key(), 0)
            if type(limit) is not int or type(external_used) is not int or not 0 <= limit <= DEFAULT_LIMIT or external_used < 0:
                raise ValueError('額度設定無效，請管理者檢查本機設定。')
            used = used_count(path=quota_path)
            usage_slot.caption(f'本月網站計數：{used} 次；外部用量補計：{external_used} 次；安全上限：{limit} 次。')
            blocked = used + external_used >= limit
        except (sqlite3.Error, OSError, ValueError):
            blocked = True
            st.error('無法確認查詢額度，暫停查詢，請聯絡管理者。')
        if blocked:
            st.error('本月查詢額度已達上限或無法確認，暫不開放查詢。')
        st.caption('此為網站共用計數，不是 Google 官方帳單用量。模擬展示仍可使用。')
    if live and st.button('搜尋附近餐廳', type='primary', disabled=blocked):
        try:
            with st.spinner('正在向 Google 搜尋…'):
                places = limited_search(fetch_nearby, st.secrets.get('GOOGLE_PLACES_API_KEY', ''),
                                        lat, lon, radius, path=quota_path, limit=limit, external_used=external_used)
            st.session_state.live_result = (places, lat, lon, radius, datetime.now(timezone.utc))
            st.session_state.selected_category = None
        except (ValueError, FileNotFoundError) as error:
            st.error(str(error))
        except (sqlite3.Error, OSError):
            st.error('無法確認查詢額度，已停止查詢。')
        finally:
            try:
                used = used_count(path=quota_path)
                usage_slot.caption(f'本月網站計數：{used} 次；外部用量補計：{external_used} 次；安全上限：{limit} 次。')
                if used + external_used >= limit:
                    st.error('本月查詢額度已達網站上限，暫不開放新的查詢。')
                    st.rerun()
            except (sqlite3.Error, OSError, ValueError):
                pass

minute = demo_time.hour * 60 + demo_time.minute
if live:
    snapshot = st.session_state.get('live_result')
    if snapshot is None:
        st.info('請在左側使用裝置位置或中央大學位置，選擇半徑後按「搜尋附近餐廳」。')
        st.stop()
    places, search_lat, search_lon, search_radius, fetched_at = snapshot
    if (lat, lon, radius) != (search_lat, search_lon, search_radius):
        st.warning('搜尋位置或半徑已變更，請重新搜尋以取得對應結果。')
        st.stop()
    age = (datetime.now(timezone.utc) - fetched_at).total_seconds()
    if age >= 300:
        st.warning('結果已超過五分鐘，營業狀態可能改變，請重新搜尋。')
        st.stop()
    st.caption(f'資料來源：Google Maps · 查詢於 {fetched_at.astimezone(timezone(timedelta(hours=8))):%H:%M:%S}（台灣時間）。營業資訊以查詢時資料為準。')
    now = datetime.now(timezone.utc)
    rows = live_rows(places, lat, lon, radius, only_open, min_remaining, sort_by, now,
                     max_walk=max_walk, opening_within=30 if opening_soon else 0)
    if places and not any(p.get('_walking') for p in places):
        st.warning('這批結果沒有步行資料。若是更新前取得的結果，請重新搜尋；找不到路線的店家會保留為未知。')
else:
    rows = search(DEMO_PLACES, lat, lon, radius, minute, only_open=only_open,
                  min_remaining=min_remaining, sort_by=sort_by, opening_within=30 if opening_soon else 0)
groups = defaultdict(list)
for row in rows:
    groups[row[0].category].append(row)
if st.session_state.get('selected_category') not in groups:
    st.session_state.selected_category = None


def select_category(category):
    st.session_state.selected_category = category


st.subheader(f'找到 {len(rows)} 家{"" if live else "範例"}餐廳')
st.caption(f'中心 {lat:.4f}, {lon:.4f} · 半徑 {radius} 公里 · 距離為直線距離')
if not rows:
    st.info('沒有符合條件的餐廳，試著放寬營業條件或重新搜尋。')
else:
    selected = st.session_state.selected_category
    if selected is None:
        st.subheader('今天想吃什麼？')
        st.caption('點選食物類別，查看餐廳與排名。列表只顯示符合目前搜尋條件的類別。')
        icons = {'日式料理': '🍣', '義式料理': '🍝', '早餐': '🥪', '咖啡甜點': '☕', '中式料理': '🥟'}
        for group, entries in sorted(groups.items()):
            st.button(f'{icons.get(group, "🍽️")} {group}　·　{len(entries)} 家　→',
                      key=f'category_{group}', use_container_width=True,
                      on_click=select_category, args=(group,))
    else:
        st.button('← 返回食物類別', on_click=select_category, args=(None,))
        st.subheader(f'{selected} · {len(groups[selected])} 家')
    for group, entries in ([(selected, groups[selected])] if selected else []):
        for rank, (place, distance, remaining) in enumerate(entries, 1):
            with st.container(border=True):
                st.markdown(f'**{rank}. {place.name}**')
                rating = f'★ {place.rating:.1f}（{place.reviews} 則）' if place.rating is not None else '尚無評分'
                st.write(f'{rating} · 直線距離 {distance:.2f} 公里')
                if live:
                    opened, left, end, raw = remaining
                    walk = raw.get('_walking')
                    if walk is None:
                        st.write('🚶 無法取得步行路線時間')
                    else:
                        st.write(f'🚶 步行約 {ceil(walk["seconds"] / 60)} 分鐘 · 路線距離 {walk["meters"] / 1000:.2f} 公里')
                        if opened is True and end is not None:
                            after_arrival = arrival_minutes(end, now, walk['seconds'])
                            if after_arrival <= 0:
                                st.warning('依目前預估，抵達時可能已打烊或正好打烊。')
                            else:
                                st.write(f'抵達後距離打烊約剩 {after_arrival} 分鐘')
                        elif opened is True:
                            st.caption('打烊時間未知，無法估算抵達後剩餘時間。')
                        st.link_button('開啟步行導航',
                                       f'https://www.google.com/maps/dir/?api=1&origin={lat},{lon}&destination={place.lat},{place.lon}&travelmode=walking')
                    if opened is True:
                        st.write('🟢 營業中' + (f' · {end:%m/%d %H:%M} 打烊（剩 {left} 分鐘）' if end else ' · 打烊時間不明'))
                        if left is not None and left <= 60:
                            st.warning('即將打烊')
                    else:
                        if opened is False:
                            waiting, opening = next_opening(raw, now)
                            if raw.get('businessStatus') == 'CLOSED_PERMANENTLY':
                                st.write('🔴 已永久停業')
                            elif raw.get('businessStatus') == 'CLOSED_TEMPORARILY':
                                st.write('🔴 暫停營業 · 恢復時間不明')
                            elif waiting is None:
                                st.write('🔴 休息中 · 下次開門時間不明')
                            elif waiting == 0:
                                st.warning('預定開門時間已到，請重新搜尋確認目前營業狀態。')
                            else:
                                hours, mins = divmod(waiting, 60)
                                wait_text = f'{hours} 小時 {mins} 分鐘' if hours else f'{mins} 分鐘'
                                st.write(f'🕒 再過 {wait_text} 開門')
                                st.caption(f'下次開門：{opening:%m/%d %H:%M}（店家當地時間）' if raw.get('utcOffsetMinutes') is not None
                                           else f'下次開門：{opening:%m/%d %H:%M}（UTC）')
                        else:
                            st.write('⚪ 營業狀態不明')
                    st.write(raw.get('formattedAddress', ''))
                    if raw.get('googleMapsUri', '').startswith('https://'):
                        st.link_button('在 Google Maps 開啟', raw['googleMapsUri'])
                    for attribution in raw.get('attributions', []):
                        st.caption('資料提供者：' + attribution.get('provider', 'Google Maps'))
                elif remaining is None:
                    st.write('⚪ 營業時間不明')
                elif remaining == 0:
                    waiting = minutes_until_open(place.hours, minute)
                    if waiting is None:
                        st.write('🔴 休息中 · 下次開門時間不明')
                    else:
                        opening = minute + waiting
                        prefix = '明日' if opening >= 1440 else '今日'
                        st.write(f'🕒 再過 {waiting} 分鐘開門 · {prefix} {(opening // 60) % 24:02d}:{opening % 60:02d}')
                else:
                    closing = minute + remaining
                    prefix = '明日' if closing >= 1440 else '今日'
                    text = f'{prefix} {(closing // 60) % 24:02d}:{closing % 60:02d} 打烊（剩 {remaining} 分鐘）'
                    if remaining <= 60:
                        st.warning(f'🟡 即將打烊 · {text}')
                    else:
                        st.write(f'🟢 營業中 · {text}')
                if not live:
                    st.link_button('查看範例座標', f'https://www.google.com/maps/search/?api=1&query={place.lat},{place.lon}')
st.caption('排名只涵蓋本次符合條件的資料。評分相同時，先比較評論數，再比較距離。')
