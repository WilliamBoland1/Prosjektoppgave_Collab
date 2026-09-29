import dataclasses

import numpy as np
import pytest

from dp_capability.models.capability import (
    _loss_factors,
    capability_notation,
    capability_numbers_level1,
    failure_numbers_level1,
    information_elements_level1,
    limiting_wind_speed_level1,
    worst_case_numbers,
)
from dp_capability.models.environmental_loads import environmental_loads_level1
from dp_capability.models.thrust import effective_thrust
from dp_capability.models.thruster_allocation import allocate_thrust
from dp_capability.standard import environment
from dp_capability.vessel import Hull, PowerSource, RedundancyGroup, Rudder, Thruster

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
        ]

    return make


def test_too_weak_for_bf1_gives_zero_everywhere(hull, psv):
    # T grows with P^(2/3), so 1e-6 of the power gives 1e-4 of the thrust:
    # all four together have 91.6 N. The smallest BF 1 load at any heading
    # is 603.0 N (head-on), and the thrusters can never give more than the
    # sum of their thrusts, so BF 1 fails everywhere.
    thrusters = psv(power_scale=1e-6)
    assert sum(effective_thrust(t) for t in thrusters) == pytest.approx(91.6, abs=0.1)
    assert np.all(capability_numbers_level1(hull, thrusters, HEADINGS) == 0)


def test_strong_enough_for_bf11_gives_eleven_everywhere(hull, psv):
    # 10 times the power gives 10^(2/3) = 4.64 times the thrust. The worst
    # heading at BF 11 then needs u = 0.73. Without ventilation: the propeller
    # load factor grows as P^(1/3), and at 10 times the power the aft azimuths
    # would ventilate almost completely (beta_vent ~ 0.001 at BF 11).
    numbers = capability_numbers_level1(hull, psv(power_scale=10.0), HEADINGS, ventilation=False)
    assert np.all(numbers == 11)


def test_head_on_surge_is_the_last_bf_within_the_thrust(hull, thruster):
    # Head-on the load is pure surge (fy = mz = 0). Two azimuths at y = +5 and
    # -5 share it equally, so it balances while |Fx| <= 2T.
    #   T = 108.895 kN (D = 2 m, 1000 kW, open, beta_misc), 2T = 217.79 kN
    #   |Fx| at BF 9 = 168.63 kN <= 217.79 kN
    #   |Fx| at BF 10 = 221.40 kN > 217.79 kN   ->  DP capability number 9
    # Ventilation hardly matters here: xi / D = 4 / 2 gives beta_vent = 0.9998
    # at BF 9 and 0.9994 at BF 10, so 2T becomes 217.75 and 217.65 kN.
    azimuths = [thruster("azimuth", y=5.0), thruster("azimuth", y=-5.0)]
    assert 2 * effective_thrust(azimuths[0]) == pytest.approx(217.79e3, rel=1e-4)
    assert -environmental_loads_level1(hull, 9, 0.0)[0] == pytest.approx(168.63e3, rel=1e-4)
    assert -environmental_loads_level1(hull, 10, 0.0)[0] == pytest.approx(221.40e3, rel=1e-4)
    assert capability_numbers_level1(hull, azimuths, 0.0) == 9


def test_number_holds_in_all_lower_conditions_but_not_the_next(hull, psv):
    # [2.2.2], checked with allocate_thrust directly at every 30 deg, with the
    # same thrust loss factors (ventilation included).
    thrusters = psv()
    headings = np.arange(0, 360, 30)
    for heading, number in zip(headings, capability_numbers_level1(hull, thrusters, headings)):
        for bf in range(1, 12):
            load = environmental_loads_level1(hull, bf, heading)
            beta_t = _loss_factors(hull, thrusters, environment(bf), heading)
            assert allocate_thrust(thrusters, load, beta_t=beta_t).feasible == (bf <= number), (heading, bf)


def test_ventilation_never_raises_a_number(hull, psv):
    # beta_vent <= 1, so no thruster gets stronger. At 150 deg BF 10 balances
    # with beta_misc alone but not once ventilation is included.
    with_ventilation = capability_numbers_level1(hull, psv(), HEADINGS)
    without = capability_numbers_level1(hull, psv(), HEADINGS, ventilation=False)
    assert np.all(with_ventilation <= without)
    assert (without[15], with_ventilation[15]) == (10, 9)


def test_forbidden_zones_never_raise_a_number(hull, psv):
    # Zones only take directions away. For this layout the aft azimuths push
    # in opposite surge directions for yaw and stay clear of their zones
    # (90 +- 20.4 and 270 +- 20.4 deg), so the numbers are the same.
    with_zones = capability_numbers_level1(hull, psv(), HEADINGS)
    without = capability_numbers_level1(hull, psv(), HEADINGS, forbidden_zones=False)
    assert np.all(with_zones <= without)
    np.testing.assert_array_equal(with_zones, without)


def test_skeg_loss_never_raises_a_number(hull, psv):
    # With a skeg ending at (-36, 0), 4 m forward of the aft azimuths, the
    # starboard azimuth loses thrust around 180-249 deg (and the port one
    # around 111-180 deg), which it uses for loads from the beam quarters.
    # The hull fixture has no skeg, so one is added here.
    skegged = dataclasses.replace(hull, skegs=((-36.0, 0.0),))
    with_skeg = capability_numbers_level1(skegged, psv(), HEADINGS)
    without = capability_numbers_level1(skegged, psv(), HEADINGS, skeg_loss=False)
    assert np.all(with_skeg <= without)
    np.testing.assert_array_equal(HEADINGS[with_skeg < without], [100, 160, 200, 260])


def test_rudders_never_lower_a_number(hull, thruster):
    # Twin screw with the psv tunnels. Without rudders only the bow tunnels
    # give sway, and their yaw moment (lever ~30 m) must be cancelled by
    # opposite surge from shaft lines only 10 m apart: about 3 times the
    # tunnel force, which the weaker reversed thrust limits to BF 2 at beam.
    # With rudders ([3.10.1]) the stern pushes sideways too: BF 5 at beam.
    def twin_screw(rudder):
        return [
            thruster("shaft_line", diameter=3.0, power_kw=2000.0, x=-38.0, y=5.0, rudder=rudder),
            thruster("shaft_line", diameter=3.0, power_kw=2000.0, x=-38.0, y=-5.0, rudder=rudder),
            thruster("tunnel", power_kw=900.0, x=31.0, pitch="CPP", tunnel_inlet="rounded"),
            thruster("tunnel", power_kw=900.0, x=28.0, pitch="CPP", tunnel_inlet="broken"),
        ]

    with_rudders = capability_numbers_level1(hull, twin_screw(Rudder("naca", 9.0, 35.0)), HEADINGS)
    without = capability_numbers_level1(hull, twin_screw(None), HEADINGS)
    assert np.all(with_rudders >= without)
    assert (without[9], with_rudders[9]) == (2, 5)
    np.testing.assert_array_equal(with_rudders[1:18], with_rudders[35:18:-1])  # port/starboard symmetric


def test_power_limits_only_where_the_plant_is_too_small(hull, psv):
    # Two switchboards, SWBD 1 = port azimuth + first tunnel, SWBD 2 the others:
    # 2000 + 900 = 2900 kW of thrusters on each.
    # - 3600 kW each: 3240 kW usable > 2900 kW, so power never limits.
    # - 3000 kW each: 2700 kW usable < 2900 kW. Only 100 and 260 deg drop
    #   (BF 7 -> 6); there BF 7 needs every thruster near full thrust.
    thrusters = [dataclasses.replace(t, power_supply=((bus, 1.0),))
                 for t, bus in zip(psv(), ["SWBD 1", "SWBD 2", "SWBD 1", "SWBD 2"])]

    def plant(kw):
        return (PowerSource("SWBD 1", kw), PowerSource("SWBD 2", kw))

    without = capability_numbers_level1(hull, thrusters, HEADINGS)
    np.testing.assert_array_equal(capability_numbers_level1(hull, thrusters, HEADINGS, power_sources=plant(3600.0)), without)
    small = capability_numbers_level1(hull, thrusters, HEADINGS, power_sources=plant(3000.0))
    assert np.all(small <= without)
    np.testing.assert_array_equal(HEADINGS[small < without], [100, 260])


def test_loss_factors_without_ventilation_are_beta_misc(hull, psv):
    beta_t = _loss_factors(hull, psv(), environment(6), HEADINGS, ventilation=False)
    assert beta_t.shape == (4, 2, 36)
    assert np.all(beta_t == 0.9)


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


def test_losing_one_of_two_azimuths_head_on(hull, thruster):
    # Two azimuths on the centreline, 40 m apart (more than 15D = 30 m, so no
    # flushing sector). Head-on the load is pure surge along the centreline.
    #   Intact: 2T = 217.79 kN, BF 9 needs 168.63 kN, BF 10 221.40 kN  ->  9
    #   One lost: T = 108.89 kN, BF 7 needs 82.34 kN, BF 8 117.31 kN   ->  7
    # (beta_vent head-on is 0.99998 at BF 7 and 0.99995 at BF 8.)
    azimuths = [thruster("azimuth", name="F", x=20.0), thruster("azimuth", name="A", x=-20.0)]
    assert -environmental_loads_level1(hull, 7, 0.0)[0] == pytest.approx(82.34e3, rel=1e-4)
    assert -environmental_loads_level1(hull, 8, 0.0)[0] == pytest.approx(117.31e3, rel=1e-4)
    assert capability_numbers_level1(hull, azimuths, 0.0) == 9
    groups = [RedundancyGroup("F", thrusters=("F",)), RedundancyGroup("A", thrusters=("A",))]
    assert failure_numbers_level1(hull, azimuths, 0.0, groups) == {"F": 7, "A": 7}


def test_failure_numbers_are_runs_on_what_is_left(hull, psv):
    # Two switchboards as in config.py; losing one loses its two thrusters.
    thrusters = [dataclasses.replace(t, name=name, power_supply=((bus, 1.0),))
                 for t, name, bus in zip(psv(), ["AZ1", "AZ2", "BT1", "BT2"], ["S1", "S2", "S1", "S2"])]
    sources = [PowerSource("S1", 3600.0), PowerSource("S2", 3600.0)]
    groups = [RedundancyGroup("S1", thrusters=("AZ1", "BT1"), power_sources=("S1",)),
              RedundancyGroup("S2", thrusters=("AZ2", "BT2"), power_sources=("S2",))]
    headings = np.arange(0, 360, 30)
    failures = failure_numbers_level1(hull, thrusters, headings, groups, power_sources=sources)
    assert list(failures) == ["S1", "S2"]
    np.testing.assert_array_equal(failures["S1"], capability_numbers_level1(
        hull, [thrusters[1], thrusters[3]], headings, power_sources=sources[1:], dead_thrusters=[thrusters[0], thrusters[2]]))
    np.testing.assert_array_equal(failures["S2"], capability_numbers_level1(
        hull, [thrusters[0], thrusters[2]], headings, power_sources=sources[:1], dead_thrusters=[thrusters[1], thrusters[3]]))
    # The surviving azimuth flushes the dead one (11 m < 4 D = 12 m) at 270
    # or 90 deg +- 5.45 deg, but the tunnel limits there: no number changes.
    without = failure_numbers_level1(hull, thrusters, headings, groups, power_sources=sources, dead_flushing=False)
    for name in failures:
        np.testing.assert_array_equal(failures[name], without[name])


def test_flushing_a_dead_thruster_head_on(hull, thruster):
    # Two open azimuths on the centreline, 6 m apart, head-on (pure surge).
    # Loss of the aft one: the forward one pushes forward and its race hits
    # the dead one, s = 6 m < 8 D = 16 m. s/D = 3:
    #   beta = 1 - 1 / (0.02 * 9 + 0.25 * 3 + 1.2) = 1 - 1/2.13 = 0.53052
    #   capacity = 0.53052 * 108.89 kN = 57.77 kN
    #   BF 6 needs 53.14 kN, BF 7 82.34 kN                  ->  6
    #   without the dead flushing loss: T = 108.89 kN       ->  7
    # Loss of the forward one: the aft one's race goes away from it  ->  7
    azimuths = [thruster("azimuth", name="F", x=3.0), thruster("azimuth", name="A", x=-3.0)]
    assert -environmental_loads_level1(hull, 6, 0.0)[0] == pytest.approx(53.14e3, rel=1e-4)
    groups = [RedundancyGroup("A", thrusters=("A",)), RedundancyGroup("F", thrusters=("F",))]
    assert failure_numbers_level1(hull, azimuths, 0.0, groups) == {"A": 6, "F": 7}
    assert failure_numbers_level1(hull, azimuths, 0.0, groups, dead_flushing=False) == {"A": 7, "F": 7}


def test_worst_case_is_the_lowest_per_heading_table_a_1():
    # DNV-ST-0111 Table A-1 (p. 69, checked with William on the crop,
    # 2026-09-29), headings 0, 10, 20, 30 deg. [2.4.7]: the combined plot is
    # the lowest of the two redundancy groups at each heading.
    loss_of_swbd_1 = [9, 8, 6, 5]
    loss_of_swbd_2 = [11, 11, 10, 8]
    np.testing.assert_array_equal(worst_case_numbers([loss_of_swbd_1, loss_of_swbd_2]), [9, 8, 6, 5])
    # Figure A-2 of the same example says L1(9, 7, 5, 2): A = 9 and C = 5 are
    # the values at 30 deg, so the +-30 deg sector includes its edges.
    a, _, c, _ = information_elements_level1([0, 10, 20, 30], [11, 11, 11, 9], [9, 8, 6, 5])
    assert (a, c) == (9, 5)


def test_information_elements_take_the_bow_sector_with_its_edges():
    # [2.5.1]: A and C within +-30 deg of the bow (330-30 deg, edges
    # included), B and D over all headings.
    headings = np.arange(0, 360, 10)
    intact = np.full(36, 11)
    intact[3], intact[33], intact[4], intact[18] = 8, 9, 6, 7  # 30, 330, 40, 180 deg
    worst = np.full(36, 10)
    worst[33], worst[9] = 5, 3  # 330, 90 deg
    assert information_elements_level1(headings, intact, worst) == (8, 6, 5, 3)


def test_information_elements_without_redundancy_are_na():
    # [2.5.2]: C and D do not apply to a non-redundant DP system.
    assert information_elements_level1([0, 90, 180, 270], [9, 6, 11, 6]) == (9, 6, None, None)


def test_information_elements_need_a_heading_near_the_bow():
    with pytest.raises(ValueError):
        information_elements_level1([90, 180, 270], [6, 11, 6])


def test_capability_notation():
    assert capability_notation(8, 6, 5, 3) == "DP capability-L1(8, 6, 5, 3)"
    assert capability_notation(8, 6) == "DP capability-L1(8, 6, NA, NA)"


def test_limiting_wind_speed_is_the_table_2_1_wind_speed():
    np.testing.assert_array_equal(limiting_wind_speed_level1([0, 7, 11]), [0.0, 17.1, 32.6])


@pytest.mark.parametrize("number", [-1, 12])
def test_limiting_wind_speed_rejects_numbers_outside_table_2_1(number):
    with pytest.raises(ValueError):
        limiting_wind_speed_level1([number])
