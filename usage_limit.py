"""Persistent, atomic quota shared by all sessions using one database."""
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
import sqlite3
from zoneinfo import ZoneInfo

DEFAULT_LIMIT = 950
DEFAULT_DB = Path(__file__).parent / 'data' / 'api_usage.sqlite3'


class LimitReached(ValueError):
    pass


class QuotaStorageError(ValueError):
    pass


@contextmanager
def postgres_connection(url):
    try:
        import psycopg
        with psycopg.connect(url, connect_timeout=10, sslmode='require') as db:
            yield db
    except LimitReached:
        raise
    except Exception:
        # Database exceptions may contain passwords/hosts. Never expose them in UI.
        raise QuotaStorageError('雲端用量資料庫無法使用，已暫停查詢。請管理者確認連線與資料表設定。') from None


def is_postgres(path):
    return isinstance(path, str) and path.startswith(('postgres://', 'postgresql://'))


def month_key(now=None):
    return (now or datetime.now(timezone.utc)).astimezone(ZoneInfo('America/Los_Angeles')).strftime('%Y-%m')


@contextmanager
def connection(path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(path, timeout=10, isolation_level=None)
    try:
        db.execute('CREATE TABLE IF NOT EXISTS usage (month TEXT PRIMARY KEY, requests INTEGER NOT NULL)')
        yield db
    finally:
        db.close()


def used_count(path=DEFAULT_DB, now=None):
    if is_postgres(path):
        with postgres_connection(path) as db:
            row = db.execute('SELECT requests FROM nearby_eats.api_usage WHERE month=%s', (month_key(now),)).fetchone()
            return row[0] if row else 0
    with connection(path) as db:
        row = db.execute('SELECT requests FROM usage WHERE month=?', (month_key(now),)).fetchone()
        return row[0] if row else 0


def reserve_request(path=DEFAULT_DB, limit=DEFAULT_LIMIT, external_used=0, now=None):
    """Reserve BEFORE calling Google; failed/uncertain requests remain counted."""
    if type(limit) is not int or type(external_used) is not int or limit < 0 or external_used < 0:
        raise ValueError('查詢額度設定必須是非負整數。')
    month = month_key(now)
    if is_postgres(path):
        with postgres_connection(path) as db:
            db.execute('INSERT INTO nearby_eats.api_usage(month, requests) VALUES (%s, 0) ON CONFLICT(month) DO NOTHING', (month,))
            used = db.execute('SELECT requests FROM nearby_eats.api_usage WHERE month=%s FOR UPDATE', (month,)).fetchone()[0]
            if used + external_used >= limit:
                raise LimitReached('本月查詢額度已達網站設定上限，暫不開放查詢，請下個月再試。')
            db.execute('UPDATE nearby_eats.api_usage SET requests=requests+1 WHERE month=%s', (month,))
            return used + 1
    with connection(path) as db:
        db.execute('BEGIN IMMEDIATE')
        try:
            row = db.execute('SELECT requests FROM usage WHERE month=?', (month,)).fetchone()
            used = row[0] if row else 0
            if used + external_used >= limit:
                raise LimitReached('本月查詢額度已達網站設定上限，暫不開放查詢，請下個月再試。')
            db.execute('INSERT INTO usage(month, requests) VALUES (?, 1) '
                       'ON CONFLICT(month) DO UPDATE SET requests=requests+1', (month,))
            db.execute('COMMIT')
            return used + 1
        except Exception:
            db.execute('ROLLBACK')
            raise


def limited_search(fetch, key, lat, lon, radius, *, path=DEFAULT_DB,
                   limit=DEFAULT_LIMIT, external_used=0):
    if not key or key == '請在這裡貼上你的金鑰':
        raise ValueError('尚未設定有效的 GOOGLE_PLACES_API_KEY。')
    reserve_request(path, limit, external_used)
    return fetch(key, lat, lon, radius)
