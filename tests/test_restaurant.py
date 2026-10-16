from restaurant import Restaurant, distance_km, minutes_until_close, search


def test_overnight_and_exact_closing():
    hours = ((1080, 120),)
    assert minutes_until_close(hours, 23 * 60) == 180
    assert minutes_until_close(hours, 60) == 60
    assert minutes_until_close(hours, 120) == 0
    assert minutes_until_close(hours, 1080) == 480


def test_split_hours_unknown_and_closed():
    assert minutes_until_close(((660, 840), (1020, 1260)), 900) == 0
    assert minutes_until_close(None, 900) is None
    assert minutes_until_close((), 900) == 0


def test_distance_and_radius_filter():
    near = Restaurant('near', 'A', 25, 121, 4, 10, ((0, 1440),))
    far = Restaurant('far', 'A', 26, 121, 5, 100, None)
    assert distance_km(25, 121, near) == 0
    assert 110 < distance_km(25, 121, far) < 112
    assert [r[0].name for r in search([near, far], 25, 121, 3, 600)] == ['near']


def test_ranking_and_unknown_hours_filter():
    places = [Restaurant('few', 'A', 25, 121, 4.5, 2, None),
              Restaurant('many', 'A', 25, 121, 4.5, 200, ((600, 720),)),
              Restaurant('unrated', 'B', 25, 121, None, 0, ())]
    ranked = search(places, 25, 121, 1, 660, sort_by='評分最高')
    assert [r[0].name for r in ranked] == ['many', 'few', 'unrated']
    assert len(search(places, 25, 121, 1, 660, min_remaining=60)) == 1
    assert not search(places, 25, 121, 1, 661, min_remaining=60)
    assert not search(places, 25, 121, 1, 660, category='B', only_open=True)
