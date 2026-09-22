import pytest

from dp_capability.models.thrust import _eta1, _eta2, _eta_m, effective_thrust, nominal_thrust
from dp_capability.vessel import Thruster


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
