from location_picker import valid_position


def test_browser_location_validation():
    assert valid_position({'status': 'success', 'lat': 24.9683, 'lon': 121.1929})
    for value in [None, {}, {'status': 'error'},
                  {'status': 'success', 'lat': 91, 'lon': 121},
                  {'status': 'success', 'lat': 25, 'lon': float('nan')},
                  {'status': 'success', 'lat': '25', 'lon': 121}]:
        assert not valid_position(value)
