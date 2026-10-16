"""One manual smoke request; print only counts, never credentials or raw payloads."""
import tomllib
from pathlib import Path
from datetime import datetime, timezone
from places_api import fetch_nearby, live_rows
from usage_limit import limited_search, month_key, DEFAULT_LIMIT

if __name__ == '__main__':
    config = tomllib.loads(Path('.streamlit/secrets.toml').read_text(encoding='utf-8'))
    try:
        places = limited_search(fetch_nearby, config.get('GOOGLE_PLACES_API_KEY', ''),
                                24.9683, 121.1929, 3,
                                limit=min(config.get('MONTHLY_REQUEST_LIMIT', DEFAULT_LIMIT), DEFAULT_LIMIT),
                                external_used=config.get('EXTERNAL_USAGE_BY_MONTH', {}).get(month_key(), 0))
        rows = live_rows(places, 24.9683, 121.1929, 3, False, 0, '距離最近', datetime.now(timezone.utc))
        print(f'Live API check passed: {len(places)} places, {len(rows)} displayable restaurants.')
    except ValueError as error:
        print(str(error))
        raise SystemExit(1)
