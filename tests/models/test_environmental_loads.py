import numpy as np
import pytest

from dp_capability.models.currentloads import current_loads_level1
from dp_capability.models.environmental_loads import environmental_loads_level1
from dp_capability.models.waveloads import _period_factor, wave_loads_level1
from dp_capability.models.windloads import wind_loads_level1
from dp_capability.vessel import Hull

# Round numbers so the expected values can be checked by hand:
#   q = 0.5 * 1.226 * 10**2         = 61.3 Pa
#   q * A_F,wind * 0.7 = 61.3*200*0.7 = 8582 N
#   q * A_L,wind * 0.9 = 61.3*800*0.9 = 44136 N
WIND_SPEED = 10.0

#   q = 0.5 * 1026 * 1**2                  = 513 Pa
#   q * B * draft * 0.07 = 513*18*6*0.07   = 3878.28 N
#   q * A_L,current * 0.6 = 513*490*0.6    = 150822 N
CURRENT_SPEED = 1.0

# Tz = 3.5 / 1.4049 = 2.4913 s, so T'surge = 0.652 and T'sway = 0.783 are both
# below 1 and f(T') = 1:
#   0.5 * 1026 * 9.81 * 2**2 * B * 0.09   = 32610.7944 N
#   0.5 * 1026 * 9.81 * 2**2 * Los * 0.09 = 155807.1288 N
#   h1A = 0.8 * 0.4**0.45 = 0.52968416,  h1B = 0.7 * 0.90**2 = 0.567
HS, TP = 2.0, 3.5
# Tz = 7.118 s, so T'surge = 1.862 and T'sway = 2.237 are above 1:
#   f(T'surge) = 0.360409,  f(T'sway) = 0.222088
HS_LONG, TP_LONG = 4.0, 10.0


@pytest.fixture
def hull():
    # Wind uses af_wind, al_wind, xl_air and lpp. Current uses breadth, draft,
    # al_current, xl_current and lpp. Waves use breadth, lpp, los, x_los,
    # bow_angle and aw_laft (C_WLaft = 648 / (40 * 18) = 0.90).
    return Hull(
        loa=88.0, lpp=80.0, draft=6.0, breadth=18.0, los=86.0, x_los=-1.0,
        bow_angle=0.4, aw_laft=648.0,
        af_wind=200.0, al_wind=800.0, xl_air=5.0,
        af_current=100.0, al_current=490.0, xl_current=-1.5,
    )


def test_wind_level1_head_wind(hull):
    fx, fy, mz = wind_loads_level1(hull, WIND_SPEED, 0)
    assert fx == pytest.approx(-8582.0)
    assert fy == pytest.approx(0.0, abs=1e-6)
    assert mz == pytest.approx(0.0, abs=1e-6)


def test_wind_level1_beam_wind_from_starboard(hull):
    # Lever arm: 5 + 0.3 * (1 - 2 * (pi/2) / pi) * 80 = 5 m
    fx, fy, mz = wind_loads_level1(hull, WIND_SPEED, 90)
    assert fx == pytest.approx(0.0, abs=1e-6)
    assert fy == pytest.approx(44136.0)
    assert mz == pytest.approx(220680.0)


def test_wind_level1_stern_wind(hull):
    fx, fy, mz = wind_loads_level1(hull, WIND_SPEED, 180)
    assert fx == pytest.approx(8582.0)
    assert fy == pytest.approx(0.0, abs=1e-6)
    assert mz == pytest.approx(0.0, abs=1e-6)


def test_wind_level1_beam_wind_from_port(hull):
    fx, fy, mz = wind_loads_level1(hull, WIND_SPEED, 270)
    assert fx == pytest.approx(0.0, abs=1e-6)
    assert fy == pytest.approx(-44136.0)
    assert mz == pytest.approx(-220680.0)


def test_wind_level1_bow_quarter(hull):
    # Lever arm: 5 + 0.3 * (1 - 2 * (pi/4) / pi) * 80 = 17 m
    fx, fy, mz = wind_loads_level1(hull, WIND_SPEED, 45)
    assert fx == pytest.approx(-6068.4, rel=1e-5)
    assert fy == pytest.approx(31208.9, rel=1e-5)
    assert mz == pytest.approx(530551.0, rel=1e-5)


def test_wind_level1_port_starboard_symmetry(hull):
    directions = np.arange(0, 360, 10)
    fx_stbd, fy_stbd, mz_stbd = wind_loads_level1(hull, WIND_SPEED, directions)
    fx_port, fy_port, mz_port = wind_loads_level1(hull, WIND_SPEED, 360 - directions)

    np.testing.assert_allclose(fx_port, fx_stbd, atol=1e-6)
    np.testing.assert_allclose(fy_port, -fy_stbd, atol=1e-6)
    np.testing.assert_allclose(mz_port, -mz_stbd, atol=1e-6)


def test_wind_level1_sign_convention(hull):
    # Wind from starboard pushes the vessel to port (+y), from port to starboard.
    _, fy_stbd, _ = wind_loads_level1(hull, WIND_SPEED, np.arange(10, 180, 10))
    _, fy_port, _ = wind_loads_level1(hull, WIND_SPEED, np.arange(190, 360, 10))
    assert np.all(fy_stbd > 0)
    assert np.all(fy_port < 0)

    # Wind on the starboard bow turns the bow to port (+yaw),
    # wind on the starboard quarter turns it to starboard (-yaw).
    assert wind_loads_level1(hull, WIND_SPEED, 30)[2] > 0
    assert wind_loads_level1(hull, WIND_SPEED, 150)[2] < 0


def test_wind_level1_scales_with_wind_speed_squared(hull):
    directions = np.arange(0, 360, 10)
    slow = wind_loads_level1(hull, WIND_SPEED, directions)
    fast = wind_loads_level1(hull, 2 * WIND_SPEED, directions)
    for load_slow, load_fast in zip(slow, fast):
        np.testing.assert_allclose(load_fast, 4 * load_slow, atol=1e-6)


def test_wind_level1_array_input_keeps_shape(hull):
    directions = np.arange(0, 360, 10)
    for load in wind_loads_level1(hull, WIND_SPEED, directions):
        assert np.shape(load) == directions.shape


@pytest.mark.parametrize(
    "direction, fx, fy, mz",
    [
        (0, -3878.28, 0.0, 0.0),
        # Lever: -1.5 + min(0.4 * (1 - 1/3), 0.25) * 80 = 18.5 m (upper clip)
        (30, -3358.689, 75411.0, 1395103.5),
        # Lever: -1.5 + 0.2 * 80 = 14.5 m (not clipped)
        (45, -2742.358, 106647.259, 1546385.255),
        # Lever: -1.5 + 0 * 80 = x_L,current
        (90, 0.0, 150822.0, -226233.0),
        # Lever: -1.5 + max(0.4 * (1 - 5/3), -0.2) * 80 = -17.5 m (lower clip)
        (150, 3358.689, 75411.0, -1319692.5),
        (180, 3878.28, 0.0, 0.0),
    ],
)
def test_current_level1_values(hull, direction, fx, fy, mz):
    loads = current_loads_level1(hull, CURRENT_SPEED, direction)
    assert loads == pytest.approx((fx, fy, mz), rel=1e-6, abs=1e-6)


def test_current_level1_lever_is_clipped(hull):
    # The lever factor 0.4 * (1 - 2*dir/pi) is clipped to 0.25 below 33.75 deg
    # and to -0.2 above 135 deg, so the lever arm MZ/FY is constant there.
    _, fy, mz = current_loads_level1(hull, CURRENT_SPEED, np.array([10, 20, 30, 33]))
    np.testing.assert_allclose(mz / fy, 18.5)
    _, fy, mz = current_loads_level1(hull, CURRENT_SPEED, np.array([140, 160, 170]))
    np.testing.assert_allclose(mz / fy, -17.5)


def test_current_level1_port_starboard_symmetry(hull):
    directions = np.arange(0, 360, 10)
    fx_stbd, fy_stbd, mz_stbd = current_loads_level1(hull, CURRENT_SPEED, directions)
    fx_port, fy_port, mz_port = current_loads_level1(hull, CURRENT_SPEED, 360 - directions)

    np.testing.assert_allclose(fx_port, fx_stbd, atol=1e-6)
    np.testing.assert_allclose(fy_port, -fy_stbd, atol=1e-6)
    np.testing.assert_allclose(mz_port, -mz_stbd, atol=1e-6)


def test_current_level1_sign_convention(hull):
    # Current from ahead pushes the vessel aft, from astern forward.
    assert current_loads_level1(hull, CURRENT_SPEED, 0)[0] < 0
    assert current_loads_level1(hull, CURRENT_SPEED, 180)[0] > 0

    # Current from starboard pushes the vessel to port (+y), from port to starboard.
    _, fy_stbd, _ = current_loads_level1(hull, CURRENT_SPEED, np.arange(10, 180, 10))
    _, fy_port, _ = current_loads_level1(hull, CURRENT_SPEED, np.arange(190, 360, 10))
    assert np.all(fy_stbd > 0)
    assert np.all(fy_port < 0)

    # Current on the starboard bow turns the bow to port (+yaw),
    # current on the starboard quarter turns it to starboard (-yaw).
    assert current_loads_level1(hull, CURRENT_SPEED, 30)[2] > 0
    assert current_loads_level1(hull, CURRENT_SPEED, 150)[2] < 0


def test_current_level1_scales_with_current_speed_squared(hull):
    directions = np.arange(0, 360, 10)
    slow = current_loads_level1(hull, CURRENT_SPEED, directions)
    fast = current_loads_level1(hull, 2 * CURRENT_SPEED, directions)
    for load_slow, load_fast in zip(slow, fast):
        np.testing.assert_allclose(load_fast, 4 * load_slow, atol=1e-6)


def test_current_level1_array_input_keeps_shape(hull):
    directions = np.arange(0, 360, 10)
    for load in current_loads_level1(hull, CURRENT_SPEED, directions):
        assert np.shape(load) == directions.shape


@pytest.mark.parametrize(
    "direction, fx, fy, mz",
    [
        # h1 = h1A = 0.52968416, h2 = -1.08562647, lever = -1 + 0.05 * 86 = 3.3 m
        (0, -18752.4833, 0.0, 0.0),
        # h1 = 0.54834208, h2 = -0.19151201, lever = -1 + (0.05 - 0.07) * 86 = -2.72 m
        (90, -3424.5931, 155807.1288, -423795.3903),
        # h1 = 0.55767104, h2 = 0.73502681, lever = -1 + (0.05 - 0.105) * 86 = -5.73 m
        (135, 13367.2678, 110172.2773, -631287.1491),
        # h1 = h1B = 0.567, h2 = 1.10515111, lever = -1 + (0.05 - 0.14) * 86 = -8.74 m
        (180, 20434.5981, 0.0, 0.0),
        (270, -3424.5931, -155807.1288, 423795.3903),
    ],
)
def test_wave_level1_values(hull, direction, fx, fy, mz):
    loads = wave_loads_level1(hull, HS, TP, direction)
    assert loads == pytest.approx((fx, fy, mz), rel=1e-6, abs=1e-6)


@pytest.mark.parametrize(
    "direction, fx, fy, mz",
    [
        # 4x the Hs = 2 m values above, times f(T'surge) on FX and f(T'sway) on FY.
        (0, -27034.2779, 0.0, 0.0),
        (90, -4937.0209, 138411.5230, -376479.3425),
        (180, 29459.2772, 0.0, 0.0),
    ],
)
def test_wave_level1_values_long_period(hull, direction, fx, fy, mz):
    loads = wave_loads_level1(hull, HS_LONG, TP_LONG, direction)
    assert loads == pytest.approx((fx, fy, mz), rel=1e-6, abs=1e-6)


def test_wave_period_factor_is_continuous_at_one():
    assert _period_factor(0.5) == 1.0
    assert _period_factor(np.nextafter(1.0, 0.0)) == 1.0
    assert _period_factor(1.0) == 1.0
    assert _period_factor(1.0 + 1e-9) == pytest.approx(1.0)
    assert _period_factor(2.0) == pytest.approx(2.0**-3 * np.exp(1 - 2.0**-3))


def test_wave_level1_surge_changes_sign_abaft_beam(hull):
    # h2 changes sign at dir = 1.75 + tan(-0.05/0.95) / 1.45 = 98.19 deg: seas
    # from forward of that push the vessel aft, seas from abaft it forward.
    directions = np.arange(0, 360)
    folded = np.minimum(directions, 360 - directions)
    fx, _, _ = wave_loads_level1(hull, HS, TP, directions)
    assert np.all(fx[folded <= 98] < 0)
    assert np.all(fx[folded >= 99] > 0)


@pytest.mark.filterwarnings("error")
def test_wave_level1_calm_sea_is_zero_despite_nan_period(hull):
    # BF 0 in Table 2-1 gives hs = 0 and tp = nan, and 0 * nan = nan.
    for load in wave_loads_level1(hull, 0.0, np.nan, np.arange(0, 360, 10)):
        assert np.all(load == 0.0)


def test_wave_level1_port_starboard_symmetry(hull):
    directions = np.arange(0, 360, 10)
    fx_stbd, fy_stbd, mz_stbd = wave_loads_level1(hull, HS, TP, directions)
    fx_port, fy_port, mz_port = wave_loads_level1(hull, HS, TP, 360 - directions)

    np.testing.assert_allclose(fx_port, fx_stbd, atol=1e-6)
    np.testing.assert_allclose(fy_port, -fy_stbd, atol=1e-6)
    np.testing.assert_allclose(mz_port, -mz_stbd, atol=1e-6)


def test_wave_level1_sign_convention(hull):
    # Waves from starboard push the vessel to port (+y), from port to starboard.
    _, fy_stbd, _ = wave_loads_level1(hull, HS, TP, np.arange(10, 180, 10))
    _, fy_port, _ = wave_loads_level1(hull, HS, TP, np.arange(190, 360, 10))
    assert np.all(fy_stbd > 0)
    assert np.all(fy_port < 0)

    # Waves on the starboard bow turn the bow to port (+yaw),
    # waves on the starboard quarter turn it to starboard (-yaw).
    assert wave_loads_level1(hull, HS, TP, 30)[2] > 0
    assert wave_loads_level1(hull, HS, TP, 150)[2] < 0


def test_wave_level1_scales_with_wave_height_squared(hull):
    directions = np.arange(0, 360, 10)
    low = wave_loads_level1(hull, HS, TP, directions)
    high = wave_loads_level1(hull, 2 * HS, TP, directions)
    for load_low, load_high in zip(low, high):
        np.testing.assert_allclose(load_high, 4 * load_low, atol=1e-6)


def test_wave_level1_array_input_keeps_shape(hull):
    directions = np.arange(0, 360, 10)
    for load in wave_loads_level1(hull, HS, TP, directions):
        assert np.shape(load) == directions.shape


def test_environmental_level1_is_factored_sum_of_components(hull):
    # BF 6 in Table 2-1: 13.8 m/s wind, 0.75 m/s current, Hs 3.1 m, Tp 8.5 s.
    directions = np.arange(0, 360, 10)
    components = (
        wind_loads_level1(hull, 13.8, directions),
        current_loads_level1(hull, 0.75, directions),
        wave_loads_level1(hull, 3.1, 8.5, directions),
    )
    total = environmental_loads_level1(hull, 6, directions)
    for i, load in enumerate(total):
        np.testing.assert_allclose(load, 1.25 * sum(c[i] for c in components), atol=1e-6)


def test_environmental_level1_dynamic_factor_can_be_overridden(hull):
    directions = np.arange(0, 360, 10)
    factored = environmental_loads_level1(hull, 6, directions)
    raw = environmental_loads_level1(hull, 6, directions, dynamic_factor=1.0)
    for load_factored, load_raw in zip(factored, raw):
        np.testing.assert_allclose(load_factored, 1.25 * load_raw, atol=1e-6)


@pytest.mark.filterwarnings("error")
def test_environmental_level1_calm_is_exactly_zero(hull):
    for load in environmental_loads_level1(hull, 0, np.arange(0, 360, 10)):
        assert np.all(load == 0.0)


@pytest.mark.parametrize("bf", range(12))
def test_environmental_level1_port_starboard_symmetry(hull, bf):
    directions = np.arange(0, 360, 10)
    fx_stbd, fy_stbd, mz_stbd = environmental_loads_level1(hull, bf, directions)
    fx_port, fy_port, mz_port = environmental_loads_level1(hull, bf, 360 - directions)

    np.testing.assert_allclose(fx_port, fx_stbd, atol=1e-6)
    np.testing.assert_allclose(fy_port, -fy_stbd, atol=1e-6)
    np.testing.assert_allclose(mz_port, -mz_stbd, atol=1e-6)


def test_environmental_level1_array_input_keeps_shape(hull):
    directions = np.arange(0, 360, 10)
    for load in environmental_loads_level1(hull, 6, directions):
        assert np.shape(load) == directions.shape
