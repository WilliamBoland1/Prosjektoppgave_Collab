import numpy as np
import pytest

from dp_capability.models.rudders import max_rudder_angle_deg, rudder_coefficients, rudder_forces
from dp_capability.vessel import Rudder, Thruster


@pytest.fixture
def shaft():
    # A shaft line with D = 2 m and a NACA rudder of A_r = 4 m^2 = D^2, so
    # A_r / D^2 = 1; tests override the rudder fields they need.
    def make(kind="shaft_line", **rudder_overrides):
        rudder = dict(profile="naca", area=4.0, max_angle_deg=35.0)
        rudder.update(rudder_overrides)
        return Thruster(name="S", kind=kind, diameter=2.0, power_kw=1000.0, x=-40.0, y=5.0, z=2.0,
                        rudder=Rudder(**rudder))

    return make


def test_coefficients_naca(shaft):
    # C_Y = 0.0126 * k1 * k2 * A_r / D^2 = 0.0126 * 1.1 * 1.0 * 1 = 0.01386
    # C_x = 0.02 * C_Y = 0.0002772
    c_x, c_y = rudder_coefficients(shaft())
    assert c_y == pytest.approx(0.01386)
    assert c_x == pytest.approx(0.0002772)


def test_fixed_nozzle_raises_c_y_by_k2(shaft):
    # Table 3-6: k2 = 1.15 behind a fixed nozzle. C_Y = 0.0126 * 1.1 * 1.15 = 0.015939
    c_x, c_y = rudder_coefficients(shaft(behind_fixed_nozzle=True))
    assert c_y == pytest.approx(0.015939)
    assert c_x == pytest.approx(0.02 * 0.015939)


@pytest.mark.parametrize("profile, c_y", [
    # Table 3-5, C_Y = 0.0126 * k1 with A_r / D^2 = 1 and k2 = 1
    ("naca", 0.01386),  # 1.1
    ("hollow", 0.01701),  # 1.35
    ("flat_sided", 0.01386),  # 1.1
    ("fish_tail", 0.01764),  # 1.4
    ("flap", 0.02079),  # 1.65
    ("nozzle", 0.02394),  # 1.9
    ("mixed", 0.015246),  # 1.21
])
def test_coefficients_follow_table_3_5(shaft, profile, c_y):
    assert rudder_coefficients(shaft(profile=profile))[1] == pytest.approx(c_y)


def test_c_y_scales_with_area_over_diameter_squared(shaft):
    # A_r = 2 m^2 with D = 2 m: A_r / D^2 = 0.5, C_Y = 0.01386 / 2 = 0.00693
    assert rudder_coefficients(shaft(area=2.0))[1] == pytest.approx(0.00693)


def test_zero_rudder_angle_gives_the_plain_thrust(shaft):
    f_surge, f_sway = rudder_forces(shaft(), 1000.0, 0.0)
    assert f_surge == pytest.approx(1000.0)
    assert f_sway == pytest.approx(0.0)


def test_forces_at_30_deg(shaft):
    # T = 1000 N, alpha = 30 deg:
    #   F_Surge = 1000 * (1 - 0.0002772 * 900) = 1000 * 0.75052 = 750.52 N
    #   F_Sway  = 1000 * 0.01386 * 30          = 415.8 N
    # -30 deg mirrors the sway force (positive alpha is to port).
    f_surge, f_sway = rudder_forces(shaft(), 1000.0, [30.0, -30.0])
    assert f_surge == pytest.approx([750.52, 750.52])
    assert f_sway == pytest.approx([415.8, -415.8])


@pytest.mark.parametrize("max_angle", [35.0, 45.0])
def test_angles_above_30_deg_use_the_30_deg_values(shaft, max_angle):
    # [3.10.1]: for rudder angles above 30 deg the values for 30 deg are used.
    s = shaft(max_angle_deg=max_angle)
    assert max_rudder_angle_deg(s) == 30.0
    f_surge, f_sway = rudder_forces(s, 1000.0, max_angle)
    assert (f_surge, f_sway) == pytest.approx((750.52, 415.8))


def test_a_smaller_maximum_angle_limits_the_forces(shaft):
    # max 20 deg, asked for 30 deg: 20 deg is used.
    #   F_Surge = 1000 * (1 - 0.0002772 * 400) = 1000 * 0.88912 = 889.12 N
    #   F_Sway  = 1000 * 0.01386 * 20                           = 277.2 N
    s = shaft(max_angle_deg=20.0)
    assert max_rudder_angle_deg(s) == 20.0
    assert rudder_forces(s, 1000.0, 30.0) == pytest.approx((889.12, 277.2))


def test_forces_are_vectorised_over_the_angle(shaft):
    f_surge, f_sway = rudder_forces(shaft(), 1000.0, np.zeros((2, 3)))
    assert f_surge.shape == f_sway.shape == (2, 3)


def test_rejects_an_unknown_profile(shaft):
    with pytest.raises(ValueError, match="profile"):
        rudder_coefficients(shaft(profile="spade"))


def test_rejects_a_rudder_on_an_azimuth(shaft):
    with pytest.raises(ValueError, match="shaft line"):
        rudder_coefficients(shaft(kind="azimuth"))


def test_rejects_a_thruster_without_a_rudder():
    plain = Thruster(name="S", kind="shaft_line", diameter=2.0, power_kw=1000.0, x=0.0, y=0.0, z=2.0)
    with pytest.raises(ValueError, match="no rudder"):
        max_rudder_angle_deg(plain)
