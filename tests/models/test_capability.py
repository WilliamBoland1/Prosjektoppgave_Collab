import numpy as np
import pytest

from dp_capability.models.capability import capability_numbers_level1, limiting_wind_speed_level1
from dp_capability.models.environmental_loads import environmental_loads_level1
from dp_capability.models.thrust import effective_thrust
from dp_capability.models.thruster_allocation import allocate_thrust
from dp_capability.vessel import Hull, Thruster

HEADINGS = np.arange(0, 360, 10)


@pytest.fixture
def hull():
    # Same round hull as tests/models/test_environmental_loads.py.
    return Hull(
        loa=88.0, lpp=80.0, draft=6.0, breadth=18.0, los=86.0, x_los=-1.0,
        bow_angle=0.4, aw_laft=648.0,
        af_wind=200.0, al_wind=800.0, xl_air=5.0,
        af_current=100.0, al_current=490.0, xl_current=-1.5,
    )


@pytest.fixture
def thruster():
    # Builds a thruster with round default data at the origin; tests override
    # what they need. Tunnels get a broken inlet by default, since they need one.
    def make(kind="azimuth", **overrides):
        fields = dict(name="T", kind=kind, diameter=2.0, power_kw=1000.0, x=0.0, y=0.0, z=2.0)
        if kind == "tunnel":
            fields["tunnel_inlet"] = "broken"
        fields.update(overrides)
        return Thruster(**fields)

    return make


@pytest.fixture
def psv(thruster):
    # Same layout as config.THRUSTERS, built here so the tests don't depend on
    # it. power_scale multiplies every actuator's power.
    def make(power_scale=1.0):
        return [
            thruster("azimuth", diameter=3.0, power_kw=2000.0 * power_scale, x=-40.0, y=5.5, ducted=True),
            thruster("azimuth", diameter=3.0, power_kw=2000.0 * power_scale, x=-40.0, y=-5.5, ducted=True),
            thruster("tunnel", power_kw=900.0 * power_scale, x=31.0, pitch="CPP", tunnel_inlet="rounded"),
            thruster("tunnel", power_kw=900.0 * power_scale, x=28.0, pitch="CPP", tunnel_inlet="broken"),
            thruster("azimuth", diameter=1.8, power_kw=800.0 * power_scale, x=22.0),
        ]

    return make


def test_too_weak_for_bf1_gives_zero_everywhere(hull, psv):
    # T grows with P^(2/3), so 1e-6 of the power gives 1e-4 of the thrust:
    # all five together have 100.3 N. The smallest BF 1 load at any heading
    # is 603.0 N (head-on), and the thrusters can never give more than the
    # sum of their thrusts, so BF 1 fails everywhere.
    thrusters = psv(power_scale=1e-6)
    assert sum(effective_thrust(t) for t in thrusters) == pytest.approx(100.3, abs=0.1)
    assert np.all(capability_numbers_level1(hull, thrusters, HEADINGS) == 0)


def test_strong_enough_for_bf11_gives_eleven_everywhere(hull, psv):
    # 10 times the power gives 10^(2/3) = 4.64 times the thrust. The worst
    # heading at BF 11 then needs u = 0.58.
    assert np.all(capability_numbers_level1(hull, psv(power_scale=10.0), HEADINGS) == 11)


def test_head_on_surge_is_the_last_bf_within_the_thrust(hull, thruster):
    # Head-on the load is pure surge (fy = mz = 0). Two azimuths at y = +5 and
    # -5 share it equally, so it balances while |Fx| <= 2T.
    #   T = 108.895 kN (D = 2 m, 1000 kW, open), 2T = 217.79 kN
    #   |Fx| at BF 9 = 168.63 kN <= 217.79 kN
    #   |Fx| at BF 10 = 221.40 kN > 217.79 kN   ->  DP capability number 9
    azimuths = [thruster("azimuth", y=5.0), thruster("azimuth", y=-5.0)]
    assert 2 * effective_thrust(azimuths[0]) == pytest.approx(217.79e3, rel=1e-4)
    assert -environmental_loads_level1(hull, 9, 0.0)[0] == pytest.approx(168.63e3, rel=1e-4)
    assert -environmental_loads_level1(hull, 10, 0.0)[0] == pytest.approx(221.40e3, rel=1e-4)
    assert capability_numbers_level1(hull, azimuths, 0.0) == 9


def test_number_holds_in_all_lower_conditions_but_not_the_next(hull, psv):
    # [2.2.2], checked with allocate_thrust directly at every 30 deg.
    thrusters = psv()
    headings = np.arange(0, 360, 30)
    for heading, number in zip(headings, capability_numbers_level1(hull, thrusters, headings)):
        for bf in range(1, 12):
            load = environmental_loads_level1(hull, bf, heading)
            assert allocate_thrust(thrusters, load).feasible == (bf <= number), (heading, bf)


def test_port_starboard_symmetry(hull, psv):
    # The layout is mirror-symmetric about the centreline, and so are the loads.
    numbers = capability_numbers_level1(hull, psv(), HEADINGS)
    mirrored = capability_numbers_level1(hull, psv(), (360 - HEADINGS) % 360)
    np.testing.assert_array_equal(mirrored, numbers)


def test_returns_integers_in_the_shape_of_the_headings(hull, psv):
    numbers = capability_numbers_level1(hull, psv(), HEADINGS)
    assert numbers.shape == HEADINGS.shape
    assert np.issubdtype(numbers.dtype, np.integer)
    assert np.shape(capability_numbers_level1(hull, psv(), 90.0)) == ()


def test_limiting_wind_speed_is_the_table_2_1_wind_speed():
    np.testing.assert_array_equal(limiting_wind_speed_level1([0, 7, 11]), [0.0, 17.1, 32.6])


@pytest.mark.parametrize("number", [-1, 12])
def test_limiting_wind_speed_rejects_numbers_outside_table_2_1(number):
    with pytest.raises(ValueError):
        limiting_wind_speed_level1([number])
