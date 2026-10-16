from collections import defaultdict
from datetime import datetime, timezone, time, timedelta
from places_api import fetch_nearby, live_rows
from restaurant import DEMO_PLACES, search
import streamlit as st

st.set_page_config(page_title='附近吃什麼？', page_icon='🍜', layout='wide')
st.title('🍜 附近吃什麼？')
st.write('依種類找餐廳，看看哪些店還來得及吃。')
mode = st.radio('資料來源', ['Google 真實搜尋', '模擬展示'], horizontal=True)
live = mode == 'Google 真實搜尋'
if live:
    st.info('按「搜尋附近餐廳」才會向 Google 發出一次請求（可能計費）。分類與排序不會新增請求。每次最多取得最近的 20 家餐廳，不包含範圍內所有店家。')
else:
    st.warning('展示模式：所有店名、評分、座標與每日營業時段都是虛構資料，不代表真實店家。')

with st.sidebar:
    st.header('搜尋條件')
    st.caption('預設示範中心：台大周邊。此版本使用手動座標，尚未取得裝置位置。')
    lat = st.number_input('緯度', min_value=-90.0, max_value=90.0, value=25.0173, format='%.4f')
    lon = st.number_input('經度', min_value=-180.0, max_value=180.0, value=121.5398, format='%.4f')
    radius = st.select_slider('直線搜尋半徑（公里）', options=[1, 3, 5], value=3)
    sort_by = st.selectbox('各種類內排序', ['距離最近', '評分最高'])
    only_open = st.checkbox('只看營業中', value=True)
    min_remaining = st.selectbox('至少多久後才打烊', [0, 30, 60, 90], format_func=lambda x: '不限' if x == 0 else f'{x} 分鐘')
    demo_time = time(19, 0)
    if not live:
        demo_time = st.time_input('模擬查詢時間（台灣時間）', value=demo_time)
        st.caption('展示時段假設每天相同。')
    if live and st.button('搜尋附近餐廳', type='primary'):
        try:
            with st.spinner('正在向 Google 搜尋…'):
                places = fetch_nearby(st.secrets.get('GOOGLE_PLACES_API_KEY', ''), lat, lon, radius)
            st.session_state.live_result = (places, lat, lon, radius, datetime.now(timezone.utc))
            st.session_state.selected_category = None
        except (ValueError, FileNotFoundError) as error:
            st.error(str(error))

minute = demo_time.hour * 60 + demo_time.minute
if live:
    snapshot = st.session_state.get('live_result')
    if snapshot is None:
        st.info('請在左側設定座標和半徑，再按「搜尋附近餐廳」。')
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
    rows = live_rows(places, lat, lon, radius, only_open, min_remaining, sort_by, datetime.now(timezone.utc))
else:
    rows = search(DEMO_PLACES, lat, lon, radius, minute, only_open=only_open,
                  min_remaining=min_remaining, sort_by=sort_by)
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
                st.write(f'{rating} · {distance:.2f} 公里')
                if live:
                    opened, left, end, raw = remaining
                    if opened is True:
                        st.write('🟢 營業中' + (f' · {end:%m/%d %H:%M} 打烊（剩 {left} 分鐘）' if end else ' · 打烊時間不明'))
                        if left is not None and left <= 60:
                            st.warning('即將打烊')
                    else:
                        st.write('🔴 休息中' if opened is False else '⚪ 營業狀態不明')
                    st.write(raw.get('formattedAddress', ''))
                    if raw.get('googleMapsUri', '').startswith('https://'):
                        st.link_button('在 Google Maps 開啟', raw['googleMapsUri'])
                    for attribution in raw.get('attributions', []):
                        st.caption('資料提供者：' + attribution.get('provider', 'Google Maps'))
                elif remaining is None:
                    st.write('⚪ 營業時間不明')
                elif remaining == 0:
                    st.write('🔴 休息中')
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
