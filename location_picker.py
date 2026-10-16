"""One-shot browser location component; coordinates stay in session memory."""
from math import isfinite
from pathlib import Path
import streamlit.components.v1 as components

device_location = components.declare_component(
    'device_location', path=str(Path(__file__).parent / 'components' / 'location'))


def valid_position(value):
    if not isinstance(value, dict) or value.get('status') != 'success':
        return False
    lat, lon = value.get('lat'), value.get('lon')
    return (type(lat) in (int, float) and type(lon) in (int, float)
            and isfinite(lat) and isfinite(lon) and -90 <= lat <= 90 and -180 <= lon <= 180)
