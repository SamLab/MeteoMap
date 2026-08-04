import meteo


def test_mean_basic():
    assert meteo.mean([1.0, 2.0, 3.0]) == 2.0


def test_mean_skips_none():
    assert meteo.mean([1.0, None, 3.0]) == 2.0


def test_mean_all_none():
    assert meteo.mean([None, None]) is None


def test_median_even():
    assert meteo.median([4.0, 1.0, 7.0, 2.0]) == 3.0


def test_median_odd_skips_none():
    assert meteo.median([10.0, None, 1.0, 5.0, 3.0]) == 4.0


def test_median_all_none():
    assert meteo.median([None]) is None


def test_circular_mean_north():
    assert abs(meteo.circular_mean([350.0, 10.0]) - 0.0) < 1e-6


def test_circular_mean_skips_none():
    assert abs(meteo.circular_mean([90.0, None, 270.0]) - 0.0) < 1e-6


def test_circular_mean_empty():
    assert meteo.circular_mean([]) is None


def test_weather_code_unique_winner():
    assert meteo.weather_code_consensus([61, 61, 80, 0]) == 61


def test_weather_code_tiebreak_by_adversity():
    # 61 (rain) and 71 (snow) tie in count → snow (priority 5) wins
    assert meteo.weather_code_consensus([61, 71, 71, 61]) == 71


def test_weather_code_skips_none():
    assert meteo.weather_code_consensus([None, 0, 0]) == 0


def test_weather_code_family_majority_beats_most_common_code():
    # 3 overcast + 3 variable + 3 mostly-clear + 1 clear: clear-family 7 vs overcast 3
    # → "clear" family wins → most common clear code 2 (partly cloudy) by adversity
    assert meteo.weather_code_consensus([3, 2, 3, 1, 1, 1, 2, 2, 3, 0]) == 2


def test_weather_code_family_rain_beats_showers():
    # 4 rain + 2 showers → rain family wins, most common rain code 61
    assert meteo.weather_code_consensus([61, 63, 65, 80, 80, 61]) == 61


def test_weather_code_family_tie_prefers_more_adverse_family():
    # rain and snow families tie 2:2 → snow (more adverse) wins
    assert meteo.weather_code_consensus([61, 71, 71, 61]) == 71
