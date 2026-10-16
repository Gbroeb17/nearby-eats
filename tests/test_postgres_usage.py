"""Integration checks against an explicitly supplied disposable PostgreSQL DB."""
import os
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import pytest
from unittest.mock import patch, Mock
import sys
from usage_limit import reserve_request, used_count, LimitReached, QuotaStorageError


def test_database_failures_hide_credentials():
    fake = Mock()
    fake.connect.side_effect = RuntimeError('postgres://user:SECRET@host')
    with patch.dict(sys.modules, {'psycopg': fake}):
        with pytest.raises(QuotaStorageError) as error:
            used_count('postgres://user:SECRET@host')
        assert 'SECRET' not in str(error.value)


@pytest.mark.skipif(not os.environ.get('TEST_DATABASE_URL'), reason='Requires disposable PostgreSQL database')
def test_postgres_atomic_limit():
    import psycopg
    url = os.environ['TEST_DATABASE_URL']
    # Use a dedicated test month to avoid changing current counters.
    now = datetime(2099, 1, 15, tzinfo=timezone.utc)
    with psycopg.connect(url, sslmode='require') as db:
        db.execute('CREATE SCHEMA IF NOT EXISTS nearby_eats')
        db.execute('CREATE TABLE IF NOT EXISTS nearby_eats.api_usage (month text PRIMARY KEY, requests integer NOT NULL)')
        db.execute('DELETE FROM nearby_eats.api_usage WHERE month=%s', ('2099-01',))
    def attempt(_):
        try:
            reserve_request(url, limit=3, external_used=1, now=now)
            return True
        except LimitReached:
            return False
    with ThreadPoolExecutor(max_workers=6) as pool:
        assert sum(pool.map(attempt, range(12))) == 2
    assert used_count(url, now) == 2
