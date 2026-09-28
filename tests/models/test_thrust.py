import math

import numpy as np
import pytest

from dp_capability.models.thrust import (
    _eta1,
    _eta2,
    _eta_m,
    _propeller_load_factor,
    _relative_motion_std,
    effective_thrust,
    nominal_thrust,
    thrust_loss_factor_level1,
    ventilation_loss_factor,
)
from dp_capability.vessel import Hull, Thruster


@pytest.fixture
def thruster():
    # Builds a thruster with round default data; tests override what they need.
    # Tunnels get a broken inlet by default, since they need one.
    def make(kind="azimuth", **overrides):
        fields = dict(name="T", kind=kind, diameter=2.0, power_kw=1000.0, x=0.0, y=0.0, z=2.0)
        if kind == "tunnel":
            fields["tunnel_inlet"] = "broken"
        fields.update(overrides)
        return Thruster(**fields)

    return make


@pytest.mark.parametrize(
    "kind, overrides, eta1",
    [
        ("azimuth", {}, 800.0),
        ("pod", {}, 800.0),
        ("shaft_line", {}, 800.0),
        ("cycloidal", {}, 900.0),
        ("tunnel", {}, 900.0),
        ("azimuth", {"contra_rotating": True}, 950.0),
        ("shaft_line", {"contra_rotating": True}, 950.0),
        ("azimuth", {"ducted": True}, 1200.0),
        ("pod", {"ducted": True}, 1200.0),
    ],
)
def test_eta1_table_3_1(thruster, kind, overrides, eta1):
    assert _eta1(thruster(kind, **overrides)) == eta1


def test_eta1_tunnel_ignores_duct_and_contra_rotation(thruster):
    assert _eta1(thruster("tunnel", ducted=True, contra_rotating=True)) == 900.0


@pytest.mark.parametrize("inlet, eta2", [("broken", 1.0), ("rounded", 1.07), ("other", 0.93)])
def test_eta2_tunnel_table_3_2_same_both_ways(thruster, inlet, eta2):
    tunnel = thruster("tunnel", tunnel_inlet=inlet)
    assert _eta2(tunnel) == eta2
    assert _eta2(tunnel, reverse=True) == eta2


@pytest.mark.parametrize(
    "pitch, ducted, eta2_reversed",
    [("FPP", False, 0.9), ("FPP", True, 0.7), ("CPP", False, 0.65), ("CPP", True, 0.5)],
)
def test_eta2_table_3_3(thruster, pitch, ducted, eta2_reversed):
    azimuth = thruster("azimuth", pitch=pitch, ducted=ducted)
    assert _eta2(azimuth) == 1.0
    assert _eta2(azimuth, reverse=True) == eta2_reversed


def test_eta2_cycloidal_is_not_reversed(thruster):
    cycloidal = thruster("cycloidal", pitch="CPP")
    assert _eta2(cycloidal) == 1.0
    assert _eta2(cycloidal, reverse=True) == 1.0


@pytest.mark.parametrize(
    "kind, permanent_magnet, eta_m",
    [
        ("cycloidal", False, 0.91),
        ("cycloidal", True, 0.97),
        ("tunnel", False, 0.93),
        ("azimuth", False, 0.93),
        # Other permanent magnet actuators are taken as rim-driven.
        ("tunnel", True, 0.995),
        ("azimuth", True, 0.995),
        ("shaft_line", False, 0.97),
        ("pod", False, 0.98),
    ],
)
def test_eta_m_table_3_4(thruster, kind, permanent_magnet, eta_m):
    assert _eta_m(thruster(kind, permanent_magnet=permanent_magnet)) == eta_m


@pytest.mark.parametrize(
    "kind, overrides, reverse, expected",
    [
        # P = 1000 * 0.93 = 930 kW, D*P = 2 * 930 = 1860, 1860^(2/3) = 151.243004
        # T = 900 * 1.07 * 151.243004 = 145647.0133 N
        ("tunnel", {"tunnel_inlet": "rounded"}, False, 145647.0133),
        # P = 2000 * 0.93 = 1860 kW, D*P = 3 * 1860 = 5580, 5580^(2/3) = 314.598127
        # T = 1200 * 1.0 * 314.598127 = 377517.7524 N forward,
        #     1200 * 0.7 * 314.598127 = 264262.4267 N reversed (FPP with duct)
        ("azimuth", {"diameter": 3.0, "power_kw": 2000.0, "ducted": True}, False, 377517.7524),
        ("azimuth", {"diameter": 3.0, "power_kw": 2000.0, "ducted": True}, True, 264262.4267),
        # P = 1000 * 0.98 = 980 kW, D*P = 2.5 * 980 = 2450, 2450^(2/3) = 181.737294
        # T = 800 * 0.65 * 181.737294 = 94503.3927 N (reversed CPP without duct)
        ("pod", {"diameter": 2.5, "pitch": "CPP"}, True, 94503.3927),
        # P = 1000 * 0.91 = 910 kW, D*P = 2 * 910 = 1820, 1820^(2/3) = 149.066799
        # T = 900 * 1.0 * 149.066799 = 134160.1190 N
        ("cycloidal", {}, False, 134160.1190),
        # P = 1000 * 0.97 = 970 kW, D*P = 2.5 * 970 = 2425, 2425^(2/3) = 180.498873
        # T = 950 * 1.0 * 180.498873 = 171473.9296 N
        ("shaft_line", {"diameter": 2.5, "contra_rotating": True}, False, 171473.9296),
    ],
)
def test_nominal_thrust(thruster, kind, overrides, reverse, expected):
    assert nominal_thrust(thruster(kind, **overrides), reverse) == pytest.approx(expected, rel=1e-9)


def test_nominal_thrust_scales_with_d_times_p_to_two_thirds(thruster):
    # 2 * D and 4 * P_B give 8 * D*P, and 8^(2/3) = 4.
    small = nominal_thrust(thruster("azimuth", diameter=2.0, power_kw=1000.0))
    large = nominal_thrust(thruster("azimuth", diameter=4.0, power_kw=4000.0))
    assert large == pytest.approx(4 * small)


@pytest.mark.parametrize("kind", ["tunnel", "cycloidal"])
def test_nominal_thrust_same_both_ways_for_tunnels_and_cycloidals(thruster, kind):
    unit = thruster(kind, pitch="CPP", ducted=True)
    assert nominal_thrust(unit, reverse=True) == nominal_thrust(unit)


def test_effective_thrust_applies_beta_misc(thruster):
    # beta_misc = 0.9 ([3.9.3]), in both directions.
    azimuth = thruster("azimuth", ducted=True)
    assert effective_thrust(azimuth) == pytest.approx(0.9 * nominal_thrust(azimuth))
    assert effective_thrust(azimuth, reverse=True) == pytest.approx(0.9 * nominal_thrust(azimuth, reverse=True))


def test_effective_thrust_takes_other_loss_factor(thruster):
    azimuth = thruster("azimuth")
    assert effective_thrust(azimuth, beta_t=0.5) == pytest.approx(0.5 * nominal_thrust(azimuth))


@pytest.mark.parametrize(
    "kind, overrides",
    [
        ("water_jet", {}),  # not covered by Tables 3-1 to 3-4, see [3.8.1]
        ("jet", {}),  # unknown kind
        ("tunnel", {"tunnel_inlet": None}),  # inlet shape must be given
        ("tunnel", {"tunnel_inlet": "square"}),
        ("azimuth", {"pitch": "VPP"}),
        ("azimuth", {"ducted": True, "contra_rotating": True}),  # no row in Table 3-1
    ],
)
def test_nominal_thrust_rejects_data_outside_the_tables(thruster, kind, overrides):
    with pytest.raises(ValueError):
        nominal_thrust(thruster(kind, **overrides))


@pytest.fixture
def hull():
    # Lpp = 100 m gives sqrt(Lpp) = 10, so T0 = 6.4 / Tz. Draft 6 m.
    return Hull(
        loa=108.0, lpp=100.0, draft=6.0, breadth=20.0, los=106.0, x_los=0.0,
        bow_angle=0.4, aw_laft=1000.0,
        af_wind=200.0, al_wind=800.0, xl_air=5.0,
        af_current=120.0, al_current=600.0, xl_current=0.0,
    )


def test_propeller_load_factor():
    # sqrt(1848.32 / 2^3) / 15.2 = sqrt(231.04) / 15.2 = 15.2 / 15.2 = 1
    assert _propeller_load_factor(1848.32, 2.0) == pytest.approx(1.0)
    # 4 times the thrust gives 2 times the factor.
    assert _propeller_load_factor(4 * 1848.32, 2.0) == pytest.approx(2.0)


@pytest.mark.parametrize(
    "direction_deg, b",
    [
        (0.0, 1.0),  # head-on
        (45.0, 1.095),  # 1 + 0.38 * 0.25
        (90.0, 1.19),  # 1 + 0.38 * 0.5, the same from both branches
        (135.0, 1.095),  # 1.38 - 0.38 * 0.75
        (180.0, 1.0),  # 1.38 - 0.38
        (270.0, 1.19),  # from port, as from starboard
    ],
)
def test_relative_motion_std_over_direction(hull, direction_deg, b):
    # x = 0 (C = 1), Tz = 3.2 (T0 = 6.4 / 3.2 = 2, min(T0, 1) = 1), no propeller
    # load term (factor <= 1): sigma = 0.25 * 0.85 * B * Hs = 0.85 * B with Hs = 4.
    sigma = _relative_motion_std(hull, 0.0, 4.0, 3.2, math.radians(direction_deg), 0.5)
    assert sigma == pytest.approx(0.85 * b)


def test_relative_motion_std_is_smaller_aft(hull):
    # x = -50 m: C = 1 + 0.4 * (-50 / 100) = 0.8, so sigma = 0.85 * 0.8 = 0.68.
    # Forward of midships C = 1.
    assert _relative_motion_std(hull, -50.0, 4.0, 3.2, 0.0, 0.5) == pytest.approx(0.68)
    assert _relative_motion_std(hull, 30.0, 4.0, 3.2, 0.0, 0.5) == pytest.approx(0.85)


def test_relative_motion_std_with_long_waves(hull):
    # Tz = 12.8: T0 = 6.4 / 12.8 = 0.5 < 1, so sigma = 0.85 * 0.5 = 0.425.
    assert _relative_motion_std(hull, 0.0, 4.0, 12.8, 0.0, 0.5) == pytest.approx(0.425)


def test_relative_motion_std_from_propeller_load_alone(hull):
    # Calm water (Tz = nan, as for BF 0): sigma = 0.25 * (3 - 1) = 0.5.
    assert _relative_motion_std(hull, 0.0, 0.0, np.nan, 0.0, 3.0) == pytest.approx(0.5)
    assert _relative_motion_std(hull, 0.0, 0.0, np.nan, 0.0, 0.5) == 0.0


@pytest.fixture
def light(thruster):
    # 1 kW on D = 2 m: T_Nominal = 800 * (2 * 0.93)^(2/3) = 1209.94 N, so the
    # propeller load factor is sqrt(1209.94 / 8) / 15.2 = 0.809 and adds nothing.
    def make(**overrides):
        return thruster("azimuth", power_kw=1.0, **overrides)

    return make


def test_ventilation_at_the_waterline_in_calm_water_is_one_half(hull, light):
    # xi = draft - z = 0 and sigma = 0: Phi(0) = 0.5.
    assert ventilation_loss_factor(light(z=6.0), hull, 0.0, np.nan, 0.0) == pytest.approx(0.5)


def test_ventilation_submerged_a_quarter_diameter(hull, light):
    # xi = 6 - 5.5 = 0.5 = D / 4, so k_V1 * 2 * xi / D = 2 * 2 * 0.5 / 2 = 1.
    unit = light(z=5.5)
    # Calm water: Phi(1) = 0.841345.
    assert ventilation_loss_factor(unit, hull, 0.0, np.nan, 0.0) == pytest.approx(0.841345, abs=1e-6)
    # Hs = 4, head-on, Tz = 3.2 (Tp = 3.2 * 1.4049): sigma = 0.85, as above.
    # Phi(1 - 1.5 * 0.85) = Phi(-0.275) = 0.391658.
    beta = ventilation_loss_factor(unit, hull, 4.0, 3.2 * 1.4049, 0.0)
    assert beta == pytest.approx(0.391658, abs=1e-6)


def test_ventilation_deep_and_above_the_surface(hull, light):
    # 26 m under water: Phi(52) = 1. Centre 1 m above the surface: Phi(-2) < 0.5.
    assert ventilation_loss_factor(light(z=-20.0), hull, 0.0, np.nan, 0.0) == pytest.approx(1.0)
    assert ventilation_loss_factor(light(z=7.0), hull, 0.0, np.nan, 0.0) == pytest.approx(0.022750, abs=1e-6)


def test_ventilation_is_vectorized_and_port_starboard_symmetric(hull, thruster):
    beta = ventilation_loss_factor(thruster("tunnel", x=30.0), hull, 4.0, 9.0, np.array([0.0, 90.0, 180.0, 270.0]))
    assert beta.shape == (4,)
    assert beta[1] == pytest.approx(beta[3])
    # Beam seas give more relative motion than head or following seas.
    assert beta[1] < beta[0] and beta[1] < beta[2]


def test_ventilation_uses_the_nominal_thrust_of_the_direction(hull, thruster):
    # Open FPP shaft line: reversed T_Nominal = 0.9 * forward (Table 3-3), a
    # lower propeller load and so less ventilation. At the waterline (xi = 0)
    # in calm water beta_vent = Phi(-1.5 * 0.25 * (PLF - 1)):
    #   forward T = 800 * (2 * 970)^(2/3) = 124439.4 N, PLF = sqrt(124439.4 / 8) / 15.2 = 8.2052
    #     beta = Phi(-0.375 * 7.2052) = Phi(-2.7020) = 0.00345
    #   reversed PLF = 8.2052 * sqrt(0.9) = 7.7842
    #     beta = Phi(-0.375 * 6.7842) = Phi(-2.5441) = 0.00548
    shaft = thruster("shaft_line", z=6.0)
    forward = ventilation_loss_factor(shaft, hull, 0.0, np.nan, 0.0)
    reverse = ventilation_loss_factor(shaft, hull, 0.0, np.nan, 0.0, reverse=True)
    assert forward == pytest.approx(0.00345, abs=1e-5)
    assert reverse == pytest.approx(0.00548, abs=1e-5)


def test_total_thrust_loss_factor_is_beta_misc_times_beta_vent(hull, thruster):
    # [3.9.5]: beta_T = 0.9 * beta_vent.
    unit = thruster("azimuth", x=-30.0, ducted=True)
    directions = np.array([0.0, 60.0, 120.0])
    assert thrust_loss_factor_level1(unit, hull, 5.7, 10.0, directions) == pytest.approx(
        0.9 * ventilation_loss_factor(unit, hull, 5.7, 10.0, directions)
    )
