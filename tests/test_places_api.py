from datetime import datetime, timezone
from unittest.mock import patch
from urllib.error import HTTPError
from io import BytesIO
import json
import pytest
from places_api import category_of, opening_status, live_rows, fetch_nearby
from places_api import attach_walking_routes, walking_route, arrival_minutes
from places_api import next_opening


def test_closing_sort_uses_exact_time_and_puts_closed_unknown_last():
    from datetime import timedelta
    now = datetime(2026, 10, 28, 15, 50, tzinfo=timezone.utc)
    base = {'location': {'latitude': 25, 'longitude': 121}}
    places = [dict(base, displayName={'text': 'later'}, currentOpeningHours={
        'openNow': True, 'nextCloseTime': (now + timedelta(minutes=40)).isoformat()}),
        dict(base, displayName={'text': 'soon'}, currentOpeningHours={
        'openNow': True, 'nextCloseTime': (now + timedelta(seconds=30)).isoformat()}),
        dict(base, displayName={'text': 'unknown'}, currentOpeningHours={'openNow': True}),
        dict(base, displayName={'text': 'closed'}, currentOpeningHours={'openNow': False})]
    rows = live_rows(places, 25, 121, 1, False, 0, '打烊剩餘時間：少到多', now)
    assert [r[0].name for r in rows[:2]] == ['soon', 'later']
    assert {r[0].name for r in rows[2:]} == {'unknown', 'closed'}


def test_next_opening_countdown_and_cross_day():
    now = datetime(2026, 10, 18, 15, 50, tzinfo=timezone.utc)
    place = {'utcOffsetMinutes': 480, 'currentOpeningHours': {
        'openNow': False, 'nextOpenTime': '2026-10-18T16:10:30Z'}}
    waiting, opening = next_opening(place, now)
    assert waiting == 21
    assert opening.day == 19 and opening.hour == 0 and opening.minute == 10
    assert next_opening(place, datetime(2026, 10, 18, 17, tzinfo=timezone.utc))[0] == 0


def test_next_opening_unknown_and_closed_business():
    now = datetime.now(timezone.utc)
    assert next_opening({}, now) == (None, None)
    for stamp in ('invalid', '2026-10-19T12:00:00'):
        assert next_opening({'currentOpeningHours': {'openNow': False, 'nextOpenTime': stamp}}, now) == (None, None)
    place = {'businessStatus': 'CLOSED_PERMANENTLY', 'currentOpeningHours': {
        'openNow': False, 'nextOpenTime': '2026-10-19T12:00:00Z'}}
    assert next_opening(place, now) == (None, None)


def test_opening_within_thirty_minutes_boundaries():
    from datetime import timedelta
    now = datetime(2026, 10, 18, 15, 50, tzinfo=timezone.utc)
    base = {'location': {'latitude': 25, 'longitude': 121}}
    places = []
    for seconds in (0, 1, 1800, 1801):
        places.append(dict(base, displayName={'text': str(seconds)},
                           currentOpeningHours={'openNow': False,
                             'nextOpenTime': (now + timedelta(seconds=seconds)).isoformat()}))
    places += [dict(base, currentOpeningHours={'openNow': True}),
               dict(base, currentOpeningHours={'openNow': False}),
               dict(places[1], businessStatus='CLOSED_TEMPORARILY')]
    rows = live_rows(places, 25, 121, 3, True, 60, '距離最近', now, opening_within=30)
    assert {r[0].name for r in rows} == {'1', '1800'}


def test_walking_summary_request_and_alignment():
    payload = {'places': [{'displayName': {'text': 'A'}}, {'displayName': {'text': 'B'}}],
               'routingSummaries': [{}, {'legs': [{'duration': '600.5s', 'distanceMeters': 850}]}]}
    with patch('places_api.urlopen', return_value=BytesIO(json.dumps(payload).encode())) as network:
        places = fetch_nearby('test-key', 24.9683, 121.1929, 3)
        body = json.loads(network.call_args.args[0].data)
        assert body['routingParameters']['travelMode'] == 'WALK'
        assert body['routingParameters']['origin']['longitude'] == 121.1929
        assert 'routingSummaries' in network.call_args.args[0].get_header('X-goog-fieldmask')
        assert network.call_count == 1
    assert places[0]['_walking'] is None
    assert places[1]['_walking']['seconds'] == 600.5
    assert attach_walking_routes({'places': [{}]})[0]['_walking'] is None


@pytest.mark.parametrize('duration', ['bad', '-1s', 'NaNs', 'infs', None, 600])
def test_invalid_walking_durations_are_unknown(duration):
    assert walking_route({'legs': [{'duration': duration, 'distanceMeters': 100}]}) is None


def test_arrival_time_cross_midnight_and_closed_before_arrival():
    now = datetime(2026, 10, 18, 23, 50, tzinfo=timezone.utc)
    end = datetime(2026, 10, 19, 0, 30, tzinfo=timezone.utc)
    assert arrival_minutes(end, now, 12 * 60) == 28
    assert arrival_minutes(end, now, 40 * 60) == 0
    assert arrival_minutes(end, now, 41 * 60) == -1
    assert arrival_minutes(None, now, 0) is None


def test_walk_filter_and_sort_unknown_last():
    base = {'location': {'latitude': 25, 'longitude': 121}}
    places = [dict(base, displayName={'text': 'unknown'}, _walking=None),
              dict(base, displayName={'text': 'slow'}, _walking={'seconds': 901, 'meters': 1000}),
              dict(base, displayName={'text': 'fast'}, _walking={'seconds': 600, 'meters': 800})]
    now = datetime.now(timezone.utc)
    rows = live_rows(places, 25, 121, 1, False, 0, '步行最快', now)
    assert [r[0].name for r in rows] == ['fast', 'slow', 'unknown']
    rows = live_rows(places, 25, 121, 1, False, 0, '步行最快', now, max_walk=15)
    assert [r[0].name for r in rows] == ['fast']


def test_category_uses_primary_before_secondary():
    assert category_of({'primaryType': 'japanese_restaurant', 'types': ['cafe']}) == '日式料理'
    assert category_of({}) == '其他餐廳'


def test_opening_timestamp_and_unknown_closing():
    now = datetime(2026, 10, 16, 17, tzinfo=timezone.utc)
    place = {'utcOffsetMinutes': 480, 'currentOpeningHours': {
        'openNow': True, 'nextCloseTime': '2026-10-16T18:00:00Z'}}
    opened, remaining, end = opening_status(place, now)
    assert opened is True and remaining == 60
    assert end.day == 17 and end.hour == 2
    assert opening_status({'currentOpeningHours': {'openNow': True}}, now) == (True, None, None)
    assert opening_status({}, now) == (None, None, None)
    assert opening_status(place, datetime(2026, 10, 16, 19, tzinfo=timezone.utc))[0] is None


def test_unknown_closing_does_not_pass_remaining_filter():
    place = {'location': {'latitude': 25, 'longitude': 121},
             'currentOpeningHours': {'openNow': True}}
    now = datetime.now(timezone.utc)
    assert len(live_rows([place], 25, 121, 1, True, 0, '距離最近', now)) == 1
    assert not live_rows([place], 25, 121, 1, True, 30, '距離最近', now)


def test_http_errors_do_not_expose_credentials():
    with patch('places_api.urlopen', side_effect=HTTPError('url', 403, 'secret', {}, None)):
        with pytest.raises(ValueError, match='403') as error:
            fetch_nearby('private-key', 25, 121, 1)
        assert 'private-key' not in str(error.value)
