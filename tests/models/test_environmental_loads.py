import numpy as np
import pytest

from dp_capability.models.windloads import wind_loads_level1
from dp_capability.vessel import Hull

# Round numbers so the expected values can be checked by hand:
#   q = 0.5 * 1.226 * 10**2         = 61.3 Pa
#   q * A_F,wind * 0.7 = 61.3*200*0.7 = 8582 N
#   q * A_L,wind * 0.9 = 61.3*800*0.9 = 44136 N
WIND_SPEED = 10.0


@pytest.fixture
def hull():
    # Only af_wind, al_wind, xl_air and lpp are used by the wind loads.
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
