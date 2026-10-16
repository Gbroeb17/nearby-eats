from datetime import datetime, timezone
from unittest.mock import patch
from urllib.error import HTTPError
import pytest
from places_api import category_of, opening_status, live_rows, fetch_nearby


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
