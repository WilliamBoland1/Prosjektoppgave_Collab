import math

import numpy as np
import pytest

from dp_capability.models.thrust import effective_thrust
from dp_capability.models.thruster_allocation import TOLERANCE, allocate_thrust
from dp_capability.vessel import Thruster


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


def balance_residual(thrusters, allocation, load):
    # Thruster forces plus environmental load; zero when balanced ([2.4.4]).
    mz = sum(t.x * fy - t.y * fx for t, fx, fy in zip(thrusters, allocation.fx, allocation.fy))
    return np.array([allocation.fx.sum(), allocation.fy.sum(), mz]) + np.asarray(load)


def test_azimuth_pushes_forward_against_head_load(thruster):
    # Load pushes aft with 0.5 T, so the azimuth pushes forward with 0.5 T.
    # 0 deg is a polygon corner, so the full T is available there: u = 0.5.
    azimuth = thruster("azimuth")
    t = effective_thrust(azimuth)
    a = allocate_thrust([azimuth], (-0.5 * t, 0.0, 0.0))
    assert a.fx == pytest.approx([0.5 * t])
    assert a.fy == pytest.approx([0.0], abs=1e-6)
    assert a.utilisation == pytest.approx(0.5)
    assert a.feasible
    assert a.angle_deg == pytest.approx([0.0])


def test_azimuth_overloaded_still_balances(thruster):
    # 2 T needed from a thruster that has T: u = 2, not feasible, but the
    # forces still balance the load, so the overload can be read off.
    azimuth = thruster("azimuth")
    t = effective_thrust(azimuth)
    a = allocate_thrust([azimuth], (-2.0 * t, 0.0, 0.0))
    assert a.utilisation == pytest.approx(2.0)
    assert not a.feasible
    assert a.fx == pytest.approx([2.0 * t])


def test_exactly_full_thrust_is_feasible(thruster):
    azimuth = thruster("azimuth")
    t = effective_thrust(azimuth)
    a = allocate_thrust([azimuth], (-t, 0.0, 0.0))
    assert a.utilisation == pytest.approx(1.0)
    assert a.feasible


def test_azimuth_pushes_to_starboard_against_load_from_starboard(thruster):
    # Environment from starboard pushes to port (+y), so the azimuth pushes to
    # starboard: angle 270 deg ([3.8.2], counter-clockwise from forward).
    azimuth = thruster("azimuth")
    t = effective_thrust(azimuth)
    a = allocate_thrust([azimuth], (0.0, 0.5 * t, 0.0))
    assert a.fx == pytest.approx([0.0], abs=1e-6)
    assert a.fy == pytest.approx([-0.5 * t])
    assert a.utilisation == pytest.approx(0.5)
    assert a.angle_deg == pytest.approx([270.0])


@pytest.mark.parametrize(
    "n_sides, expected",
    [
        # 45 deg is the middle of the side between the corners at 40 and 50 deg,
        # at T * cos(5 deg) = 0.996195 T from the centre: u = 0.5 / 0.996195.
        (36, 0.5 / math.cos(math.radians(5))),
        # A square with corners at 0, 90, 180 and 270 deg: the side at 45 deg is
        # at T * cos(45 deg) from the centre, u = 0.5 * sqrt(2).
        (4, 0.5 * math.sqrt(2)),
    ],
)
def test_azimuth_polygon_is_conservative_between_corners(thruster, n_sides, expected):
    azimuth = thruster("azimuth")
    t = effective_thrust(azimuth)
    load = (-0.5 * t * math.cos(math.radians(45)), -0.5 * t * math.sin(math.radians(45)), 0.0)
    a = allocate_thrust([azimuth], load, n_sides=n_sides)
    assert a.utilisation == pytest.approx(expected)
    assert a.angle_deg == pytest.approx([45.0])


def test_two_tunnels_share_a_sway_load(thruster):
    # Tunnels at x = +10 and -10. Load 1.0 T to starboard; moment balance
    # 10 * fy1 - 10 * fy2 = 0 gives fy1 = fy2 = 0.5 T to port, u = 0.5.
    tunnels = [thruster("tunnel", x=10.0), thruster("tunnel", x=-10.0)]
    t = effective_thrust(tunnels[0])
    a = allocate_thrust(tunnels, (0.0, -t, 0.0))
    assert a.fx == pytest.approx([0.0, 0.0])
    assert a.fy == pytest.approx([0.5 * t, 0.5 * t])
    assert a.utilisation == pytest.approx(0.5)
    assert a.angle_deg == pytest.approx([90.0, 90.0])


def test_two_tunnels_balance_a_yaw_moment(thruster):
    # Load Mz = +10 T (counter-clockwise), so the tunnels give -10 T:
    #   fy1 + fy2 = 0,  10 * fy1 - 10 * fy2 = -10 T  ->  fy1 = -0.5 T, fy2 = +0.5 T
    # The bow tunnel pushes the bow to starboard, the stern tunnel the stern to port.
    tunnels = [thruster("tunnel", x=10.0), thruster("tunnel", x=-10.0)]
    t = effective_thrust(tunnels[0])
    a = allocate_thrust(tunnels, (0.0, 0.0, 10.0 * t))
    assert a.fy == pytest.approx([-0.5 * t, 0.5 * t])
    assert a.utilisation == pytest.approx(0.5)
    assert a.angle_deg == pytest.approx([270.0, 90.0])


def test_side_by_side_azimuths_balance_a_yaw_moment(thruster):
    # Azimuths at y = +5 (port) and -5 (starboard). Load Mz = +5 T, so
    #   fx1 + fx2 = 0,  -5 * fx1 + 5 * fx2 = -5 T  ->  fx1 = +0.5 T, fx2 = -0.5 T
    # Checks the -y * fx term: the port thruster pushing forward turns the bow
    # to starboard (clockwise).
    azimuths = [thruster("azimuth", y=5.0), thruster("azimuth", y=-5.0)]
    t = effective_thrust(azimuths[0])
    a = allocate_thrust(azimuths, (0.0, 0.0, 5.0 * t))
    assert a.fx == pytest.approx([0.5 * t, -0.5 * t])
    assert a.fy == pytest.approx([0.0, 0.0], abs=1e-6)
    assert a.utilisation == pytest.approx(0.5)
    assert a.angle_deg == pytest.approx([0.0, 180.0])


def test_shaft_line_uses_reversed_thrust_backwards(thruster):
    # Open FPP: reversed thrust is 0.9 T (Table 3-3). Load 0.45 T forward, so
    # the propeller pushes 0.45 T aft = 0.5 of its reversed thrust: u = 0.5.
    shaft = thruster("shaft_line")
    t = effective_thrust(shaft)
    a = allocate_thrust([shaft], (0.45 * t, 0.0, 0.0))
    assert a.fx == pytest.approx([-0.45 * t])
    assert a.fy == pytest.approx([0.0])
    assert a.utilisation == pytest.approx(0.5)
    assert a.angle_deg == pytest.approx([180.0])


def test_tunnels_cannot_balance_a_surge_load(thruster):
    tunnels = [thruster("tunnel", x=10.0), thruster("tunnel", x=-10.0)]
    a = allocate_thrust(tunnels, (-1000.0, 0.0, 0.0))
    assert a.utilisation == math.inf
    assert not a.feasible
    assert np.isnan(a.fx).all() and np.isnan(a.fy).all()


def test_zero_load_needs_no_thrust(thruster):
    thrusters = [thruster("azimuth", x=-10.0), thruster("tunnel", x=10.0)]
    a = allocate_thrust(thrusters, (0.0, 0.0, 0.0))
    assert a.utilisation == pytest.approx(0.0, abs=1e-9)
    assert a.feasible
    assert a.fx == pytest.approx([0.0, 0.0])
    assert a.fy == pytest.approx([0.0, 0.0])
    assert np.isnan(a.angle_deg).all()


def test_second_pass_keeps_idle_thrusters_idle(thruster):
    # Two tunnels at the same x could push against each other (fy1 = -fy2)
    # without disturbing the balance of a pure surge load. The second pass
    # minimises total thrust, so they stay at zero.
    thrusters = [thruster("azimuth"), thruster("tunnel", x=10.0), thruster("tunnel", x=10.0)]
    t = effective_thrust(thrusters[0])
    a = allocate_thrust(thrusters, (-0.5 * t, 0.0, 0.0))
    assert a.fx == pytest.approx([0.5 * t, 0.0, 0.0])
    assert a.fy == pytest.approx([0.0, 0.0, 0.0], abs=1e-6)
    assert np.isnan(a.angle_deg[1:]).all()


@pytest.fixture
def psv(thruster):
    # Same layout as config.THRUSTERS, built here so the tests don't depend on it.
    return [
        thruster("azimuth", diameter=3.0, power_kw=2000.0, x=-40.0, y=5.5, ducted=True),
        thruster("azimuth", diameter=3.0, power_kw=2000.0, x=-40.0, y=-5.5, ducted=True),
        thruster("tunnel", power_kw=900.0, x=31.0, pitch="CPP", tunnel_inlet="rounded"),
        thruster("tunnel", power_kw=900.0, x=28.0, pitch="CPP", tunnel_inlet="broken"),
        thruster("azimuth", diameter=1.8, power_kw=800.0, x=22.0),
    ]


@pytest.mark.parametrize(
    "load",
    [
        (-100e3, 0.0, 0.0),
        (60e3, -150e3, 2e6),
        (-5.5e3, 358e3, 509e3),  # the BF 6 beam load of the config vessel
        (-12.7e3, 664e3, 1367.5e3),  # BF 8 beam: more than the thrusters can give
    ],
)
def test_mixed_layout_balances_within_utilisation(psv, load):
    a = allocate_thrust(psv, load)
    assert balance_residual(psv, a, load) == pytest.approx([0.0, 0.0, 0.0], abs=1e-3)
    # No thruster needs more than u of its effective thrust (azimuths and tunnels
    # only, so the forward thrust is the limit in every direction). The second
    # pass may use TOLERANCE on top, and HiGHS its own 1e-7, hence the margin.
    for unit, fx, fy in zip(psv, a.fx, a.fy):
        assert math.hypot(fx, fy) / effective_thrust(unit) <= a.utilisation + 2 * TOLERANCE


def test_utilisation_scales_with_load(psv):
    load = np.array([60e3, -150e3, 2e6])
    assert allocate_thrust(psv, 2 * load).utilisation == pytest.approx(2 * allocate_thrust(psv, load).utilisation)


def test_rejects_water_jets(thruster):
    with pytest.raises(ValueError):
        allocate_thrust([thruster("water_jet")], (1.0, 0.0, 0.0))


def test_rejects_a_load_for_several_headings(thruster):
    loads = (np.zeros(36), np.zeros(36), np.zeros(36))
    with pytest.raises(ValueError):
        allocate_thrust([thruster("azimuth")], loads)
