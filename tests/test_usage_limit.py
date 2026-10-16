from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from unittest.mock import Mock
import pytest
from usage_limit import LimitReached, month_key, used_count, reserve_request, limited_search


def test_limit_persists_and_prevents_network_call(tmp_path):
    path = tmp_path / 'usage.db'
    fetch = Mock(return_value=[])
    for _ in range(2):
        limited_search(fetch, 'test-key', 25, 121, 1, path=path, limit=2)
    with pytest.raises(LimitReached):
        limited_search(fetch, 'test-key', 25, 121, 1, path=path, limit=2)
    assert fetch.call_count == 2
    assert used_count(path) == 2


def test_failed_requests_stay_counted(tmp_path):
    path = tmp_path / 'usage.db'
    with pytest.raises(ValueError):
        limited_search(Mock(side_effect=ValueError('network failed')), 'key', 25, 121, 1,
                       path=path, limit=1)
    assert used_count(path) == 1


def test_concurrent_sessions_cannot_overrun(tmp_path):
    path = tmp_path / 'usage.db'
    used_count(path)
    def attempt(_):
        try:
            reserve_request(path, limit=3)
            return True
        except LimitReached:
            return False
    with ThreadPoolExecutor(max_workers=8) as pool:
        assert sum(pool.map(attempt, range(16))) == 3
    assert used_count(path) == 3


def test_month_boundary_and_external_usage(tmp_path):
    path = tmp_path / 'usage.db'
    before = datetime(2026, 11, 1, 6, 59, tzinfo=timezone.utc)
    after = datetime(2026, 11, 1, 7, 1, tzinfo=timezone.utc)
    assert month_key(before) == '2026-10'
    assert month_key(after) == '2026-11'
    reserve_request(path, limit=2, external_used=1, now=before)
    with pytest.raises(LimitReached):
        reserve_request(path, limit=2, external_used=1, now=before)
    assert used_count(path, after) == 0
    reserve_request(path, limit=2, now=after)
