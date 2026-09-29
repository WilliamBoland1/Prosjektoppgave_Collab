import dataclasses
import math

import numpy as np
import pytest

from dp_capability.models.forbidden_zones import forbidden_zones_level1
from dp_capability.models.skeg_loss import skeg_loss_factor
from dp_capability.models.thrust import effective_thrust
from dp_capability.models.thruster_allocation import TOLERANCE, allocate_thrust
from dp_capability.vessel import PowerSource, Rudder, Thruster


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


def test_half_the_loss_factor_doubles_the_utilisation(thruster):
    # T is the effective thrust with beta_misc = 0.9. With beta_T = 0.45 the
    # azimuth has T / 2, so a 0.5 T load needs all of it: u = 1.
    azimuth = thruster("azimuth")
    t = effective_thrust(azimuth)
    assert allocate_thrust([azimuth], (-0.5 * t, 0.0, 0.0)).utilisation == pytest.approx(0.5)
    a = allocate_thrust([azimuth], (-0.5 * t, 0.0, 0.0), beta_t=[(0.45, 0.45)])
    assert a.utilisation == pytest.approx(1.0)


def test_weaker_tunnel_sets_the_utilisation(thruster):
    # As in test_two_tunnels_share_a_sway_load, the moment balance makes both
    # tunnels give 0.5 T. The second has beta_T = 0.45, i.e. only T / 2, so
    # it is at u = 0.5 T / (T / 2) = 1.
    tunnels = [thruster("tunnel", x=10.0), thruster("tunnel", x=-10.0)]
    t = effective_thrust(tunnels[0])
    a = allocate_thrust(tunnels, (0.0, -t, 0.0), beta_t=[(0.9, 0.9), (0.45, 0.45)])
    assert a.fy == pytest.approx([0.5 * t, 0.5 * t])
    assert a.utilisation == pytest.approx(1.0)


def test_shaft_line_uses_the_reverse_loss_factor_backwards(thruster):
    # Same as test_shaft_line_uses_reversed_thrust_backwards, with the reverse
    # loss factor halved: 0.45 T aft is now all of the reversed thrust.
    shaft = thruster("shaft_line")
    t = effective_thrust(shaft)
    a = allocate_thrust([shaft], (0.45 * t, 0.0, 0.0), beta_t=[(0.9, 0.45)])
    assert a.utilisation == pytest.approx(1.0)


def test_azimuth_cannot_push_into_its_forbidden_zone(thruster):
    # The load needs 0.5 T at exactly 90 deg (to port), inside the user zone
    # 80-100 deg, and a single azimuth has nothing to combine it with.
    azimuth = thruster("azimuth", forbidden_zones=((80.0, 100.0),))
    t = effective_thrust(azimuth)
    assert allocate_thrust([azimuth], (0.0, -0.5 * t, 0.0)).utilisation == math.inf
    assert allocate_thrust([azimuth], (0.0, -0.5 * t, 0.0), forbidden_zones=False).utilisation == pytest.approx(0.5)


def test_flushing_sector_moves_the_sway_force_to_one_azimuth(thruster):
    # Azimuths at y = +5 and -5, D = 2: s = 10 < 15D = 30, so the port one may
    # not push within 16.7 deg of 90 deg and the starboard one not near 270.
    # Load T to starboard, balanced by T to port. The moment balance
    #   -5 * fx1 + 5 * fx2 = 0  and  fx1 + fx2 = 0  ->  fx1 = fx2 = 0
    # leaves the port azimuth only 90 deg, which it may not use. So the
    # starboard one gives all of it: u = 1 (0.5 each without the zones).
    azimuths = [thruster("azimuth", y=5.0), thruster("azimuth", y=-5.0)]
    t = effective_thrust(azimuths[0])
    a = allocate_thrust(azimuths, (0.0, -t, 0.0))
    assert a.utilisation == pytest.approx(1.0)
    assert a.fx == pytest.approx([0.0, 0.0], abs=1e-6)
    assert a.fy == pytest.approx([0.0, t])
    assert allocate_thrust(azimuths, (0.0, -t, 0.0), forbidden_zones=False).utilisation == pytest.approx(0.5)


def test_tunnel_direction_inside_a_zone_is_not_available(thruster):
    # A zone around 90 deg takes away the push to port, not to starboard.
    tunnel = thruster("tunnel", forbidden_zones=((80.0, 100.0),))
    t = effective_thrust(tunnel)
    assert allocate_thrust([tunnel], (0.0, -0.5 * t, 0.0)).utilisation == math.inf
    assert allocate_thrust([tunnel], (0.0, 0.5 * t, 0.0)).utilisation == pytest.approx(0.5)


def test_fully_forbidden_azimuth_gives_nothing(thruster):
    # Every direction forbidden: the other azimuth takes the whole load. They
    # are 40 m apart (> 15D = 30 m), so no flushing sector gets in the way.
    blocked = thruster("azimuth", x=-20.0, forbidden_zones=((0.0, 360.0),))
    free = thruster("azimuth", x=20.0)
    t = effective_thrust(free)
    a = allocate_thrust([blocked, free], (-0.5 * t, 0.0, 0.0))
    assert a.fx == pytest.approx([0.0, 0.5 * t])
    assert a.utilisation == pytest.approx(0.5)


@pytest.mark.parametrize(
    "load",
    [(-100e3, 0.0, 0.0), (60e3, -150e3, 2e6), (-5.5e3, 358e3, 509e3), (0.0, -300e3, 0.0), (0.0, 0.0, -1e7)],
)
def test_forces_stay_out_of_the_forbidden_zones(psv, load):
    # The aft azimuths are 11 m apart (< 15D = 45 m): zones 90 +- 20.44 deg
    # (port) and 270 +- 20.44 deg (starboard).
    a = allocate_thrust(psv, load)
    for angle, zones in zip(a.angle_deg, forbidden_zones_level1(psv)):
        for start, end in zones:
            assert not 1e-6 < (angle - start) % 360.0 < end - start - 1e-6, (angle, start, end)


def single_thruster_load(unit, force):
    # The load a single thruster balances by giving `force` at its position.
    fx, fy = force
    return (-fx, -fy, -(unit.x * fy - unit.y * fx))


def test_skeg_loss_halves_the_thrust_at_45_deg(thruster):
    # Open, D = 10, at (-30, 6) with the skeg end at (-36, 0): the skeg loss
    # factor is 0.5 at 45 deg and 0 at 90 deg (tests/models/test_skeg_loss.py).
    # 0.25 T at 45 deg is then half of what is left: u = 0.5. The polygon has
    # corners every 1 deg there, so it is within 1e-3 of the true curve.
    azimuth = thruster("azimuth", diameter=10.0, x=-30.0, y=6.0)
    t = effective_thrust(azimuth)
    c = math.cos(math.radians(45))
    load = single_thruster_load(azimuth, (0.25 * t * c, 0.25 * t * c))
    a = allocate_thrust([azimuth], load, skegs=[(-36.0, 0.0)])
    assert a.utilisation == pytest.approx(0.5, rel=1e-3)
    assert a.utilisation >= 0.5  # conservative
    assert a.angle_deg == pytest.approx([45.0])
    # Without the skeg, 45 deg is halfway between the 36-gon corners at 40
    # and 50 deg: u = 0.25 / cos(5 deg).
    assert allocate_thrust([azimuth], load).utilisation == pytest.approx(0.25 / math.cos(math.radians(5)))


def test_no_thrust_straight_into_the_skeg(thruster):
    # At 90 deg the skeg loss factor is 0, so a single azimuth can't push that way.
    azimuth = thruster("azimuth", diameter=10.0, x=-30.0, y=6.0)
    load = single_thruster_load(azimuth, (0.0, 1000.0))
    assert allocate_thrust([azimuth], load, skegs=[(-36.0, 0.0)]).utilisation == math.inf


@pytest.mark.parametrize("load", [(-100e3, 0.0, 0.0), (-5.5e3, 358e3, 509e3), (0.0, -300e3, 0.0), (0.0, 0.0, -1e7)])
def test_forces_stay_inside_the_skeg_reduced_capacity(psv, load):
    # The aft azimuths are 4 m aft and 5.5 m outboard of the skeg end (-36, 0):
    # no force may exceed u * T * beta_skeg(angle), nor point into a zone.
    skegs = [(-36.0, 0.0)]
    a = allocate_thrust(psv, load, skegs=skegs)
    for unit, fx, fy, angle, zones in zip(psv, a.fx, a.fy, a.angle_deg, forbidden_zones_level1(psv)):
        if np.isnan(angle):
            continue
        capacity = effective_thrust(unit) * skeg_loss_factor(unit, skegs, angle)
        assert math.hypot(fx, fy) <= (a.utilisation + 2 * TOLERANCE) * capacity + 1e-6
        for start, end in zones:
            assert not 1e-6 < (angle - start) % 360.0 < end - start - 1e-6
    assert a.utilisation >= allocate_thrust(psv, load).utilisation - 1e-9


def test_flushing_a_dead_thruster_straight_on(thruster):
    # Open, D = 2, with a dead azimuth 10 m aft: forward thrust sends the race
    # onto it. s/D = 5 gives beta = 0.66102 at 0 deg
    # (tests/models/test_dead_flushing.py), so 0.5 T forward needs
    # u = 0.5 / 0.66102 = 0.75641. Without the dead thruster u = 0.5.
    azimuth = thruster("azimuth")
    dead = thruster("azimuth", name="DEAD", x=-10.0)
    t = effective_thrust(azimuth)
    load = single_thruster_load(azimuth, (0.5 * t, 0.0))
    assert allocate_thrust([azimuth], load, dead_thrusters=[dead]).utilisation == pytest.approx(0.75641, abs=1e-5)
    assert allocate_thrust([azimuth], load).utilisation == pytest.approx(0.5)


def test_dead_flushing_capacity_is_the_straight_line_of_figure_3_6(thruster):
    # The midpoint of the line from beta * T at 0 deg to T at the sector edge
    # is T * (0.82695, 0.05957) (tests/models/test_dead_flushing.py). It lies
    # on the capacity boundary, so it needs exactly u = 1: the polygon
    # corners every 1 deg in the sector lie on that line.
    azimuth = thruster("azimuth")
    dead = thruster("azimuth", name="DEAD", x=-10.0)
    t = effective_thrust(azimuth)
    load = single_thruster_load(azimuth, (0.82695 * t, 0.05957 * t))
    assert allocate_thrust([azimuth], load, dead_thrusters=[dead]).utilisation == pytest.approx(1.0, abs=1e-4)


def test_a_tunnel_flushing_a_dead_thruster(thruster):
    # Dead azimuth 5 m to starboard: pushing to port sends the tunnel's race
    # onto it. Open, s/D = 2.5: beta = 1 - 1 / (0.125 + 0.625 + 1.2) = 0.48718.
    # 0.25 T to port then needs u = 0.25 / 0.48718 = 0.51316; to starboard
    # the race goes the other way, so u = 0.25.
    tunnel = thruster("tunnel")
    dead = thruster("azimuth", name="DEAD", y=-5.0)
    t = effective_thrust(tunnel)
    to_port = allocate_thrust([tunnel], single_thruster_load(tunnel, (0.0, 0.25 * t)), dead_thrusters=[dead])
    to_starboard = allocate_thrust([tunnel], single_thruster_load(tunnel, (0.0, -0.25 * t)), dead_thrusters=[dead])
    assert to_port.utilisation == pytest.approx(0.51316, abs=1e-5)
    assert to_starboard.utilisation == pytest.approx(0.25)


@pytest.fixture
def rudder():
    # NACA rudder with A_r = D^2 for the default D = 2 m: C_Y = 0.01386 and
    # C_x = 0.0002772 (tests/models/test_rudders.py). At 30 deg the propeller
    # and rudder give (1 - 0.0002772 * 900, 0.01386 * 30) T = (0.75052, 0.4158) T.
    return Rudder(profile="naca", area=4.0, max_angle_deg=35.0)


# Direction of the force at 30 deg rudder: atan2(0.4158, 0.75052) = 28.99 deg.
RUDDER_EDGE_DEG = math.degrees(math.atan2(0.4158, 0.75052))


def test_rudder_turns_forward_thrust_sideways(thruster, rudder):
    # Half of the 30 deg force: a corner of the rudder fan, so u = 0.5.
    shaft = thruster("shaft_line", rudder=rudder)
    t = effective_thrust(shaft)
    a = allocate_thrust([shaft], (-0.5 * 0.75052 * t, -0.5 * 0.4158 * t, 0.0))
    assert a.utilisation == pytest.approx(0.5)
    assert a.fx == pytest.approx([0.5 * 0.75052 * t])
    assert a.fy == pytest.approx([0.5 * 0.4158 * t])
    assert a.angle_deg == pytest.approx([RUDDER_EDGE_DEG])
    assert RUDDER_EDGE_DEG == pytest.approx(28.99, abs=0.01)


def test_rudder_side_force_is_limited_to_the_fan(thruster, rudder):
    # Pure sway (90 deg) or any direction beyond 28.99 deg is outside the fan,
    # however much thrust: a single shaft line cannot balance it.
    shaft = thruster("shaft_line", rudder=rudder)
    t = effective_thrust(shaft)
    assert allocate_thrust([shaft], (0.0, -0.1 * t, 0.0)).utilisation == math.inf
    c, s = math.cos(math.radians(35.0)), math.sin(math.radians(35.0))
    assert allocate_thrust([shaft], (-0.1 * t * c, -0.1 * t * s, 0.0)).utilisation == math.inf


def test_rudder_gives_no_side_force_when_backing(thruster, rudder):
    # [3.10.2]: with negative thrust the rudder is neglected. Backing with a
    # side force cannot be balanced; pure backing is as without a rudder:
    # 0.45 T of the 0.9 T reversed thrust (open FPP), u = 0.5.
    shaft = thruster("shaft_line", rudder=rudder)
    t = effective_thrust(shaft)
    assert allocate_thrust([shaft], (0.45 * t, 0.1 * t, 0.0)).utilisation == math.inf
    a = allocate_thrust([shaft], (0.45 * t, 0.0, 0.0))
    assert a.utilisation == pytest.approx(0.5)
    assert a.fy == pytest.approx([0.0], abs=1e-6)


def test_rudder_is_not_used_by_a_shaft_line_without_one(thruster):
    # The plain shaft line has no side force at all.
    shaft = thruster("shaft_line")
    t = effective_thrust(shaft)
    assert allocate_thrust([shaft], (-0.5 * 0.75052 * t, -0.5 * 0.4158 * t, 0.0)).utilisation == math.inf


def test_zones_act_on_the_shaft_direction_not_the_rudder_force(thruster, rudder):
    # [3.11.3] takes the thrust direction through the propeller shaft. A zone
    # around 0 deg removes all forward thrust, rudder fan included, but not
    # the reversed thrust; a zone at 20-40 deg, around the deflected force
    # but not the shaft, removes nothing.
    load = (-0.5 * 0.75052, -0.5 * 0.4158, 0.0)
    blocked = thruster("shaft_line", rudder=rudder, forbidden_zones=((-10.0, 10.0),))
    t = effective_thrust(blocked)
    assert allocate_thrust([blocked], np.multiply(load, t)).utilisation == math.inf
    assert allocate_thrust([blocked], (0.45 * t, 0.0, 0.0)).utilisation == pytest.approx(0.5)
    aside = thruster("shaft_line", rudder=rudder, forbidden_zones=((20.0, 40.0),))
    assert allocate_thrust([aside], np.multiply(load, t)).utilisation == pytest.approx(0.5)


@pytest.fixture
def twin_screw(thruster):
    # Two shaft lines aft with NACA rudders (A_r = D^2 = 9 m^2) and the two bow
    # tunnels of the psv fixture. with_rudders=False gives plain shaft lines.
    def make(with_rudders=True):
        r = Rudder(profile="naca", area=9.0, max_angle_deg=35.0) if with_rudders else None
        return [
            thruster("shaft_line", diameter=3.0, power_kw=2000.0, x=-38.0, y=5.0, rudder=r),
            thruster("shaft_line", diameter=3.0, power_kw=2000.0, x=-38.0, y=-5.0, rudder=r),
            thruster("tunnel", power_kw=900.0, x=31.0, pitch="CPP", tunnel_inlet="rounded"),
            thruster("tunnel", power_kw=900.0, x=28.0, pitch="CPP", tunnel_inlet="broken"),
        ]

    return make


@pytest.mark.parametrize(
    "load",
    [(-100e3, 0.0, 0.0), (60e3, -150e3, 2e6), (0.0, -300e3, 0.0), (0.0, 200e3, 0.0), (0.0, 0.0, -1e7)],
)
def test_rudder_forces_stay_inside_their_pieces(twin_screw, load):
    # Forward: inside u times the fan, i.e. fx <= u T and |fy| within the
    # 28.99 deg edges. Backing: along -x only, up to u times the reversed thrust.
    thrusters = twin_screw()
    a = allocate_thrust(thrusters, load)
    assert balance_residual(thrusters, a, load) == pytest.approx([0.0, 0.0, 0.0], abs=1e-3)
    slope = 0.4158 / 0.75052
    for unit, fx, fy in zip(thrusters[:2], a.fx[:2], a.fy[:2]):
        u = a.utilisation + 2 * TOLERANCE
        if fx < 0:
            assert fy == pytest.approx(0.0, abs=1e-6)
            assert -fx <= u * effective_thrust(unit, reverse=True) + 1e-6
        else:
            assert fx <= u * effective_thrust(unit) + 1e-6
            assert abs(fy) <= slope * fx + 1e-6
    # The rudders only add capacity.
    assert a.utilisation <= allocate_thrust(twin_screw(False), load).utilisation + 1e-9


def test_rudders_share_a_sway_load_with_the_tunnels(twin_screw):
    # Without rudders only the bow tunnels give sway, and the shaft lines have
    # to balance their yaw moment with opposite surge. With rudders the stern
    # pushes sideways too, so the same load needs less.
    load = (0.0, -300e3, 0.0)
    with_rudders = allocate_thrust(twin_screw(), load)
    without = allocate_thrust(twin_screw(False), load)
    assert with_rudders.utilisation < without.utilisation
    assert np.any(np.abs(with_rudders.fy[:2]) > 1e3)
    assert without.fy[:2] == pytest.approx([0.0, 0.0], abs=1e-6)


def test_power_within_the_bus_leaves_the_utilisation_to_the_thrust(thruster):
    # P_B = 1000 kW on a 1000 kW switchboard: 900 kW usable ([3.12.3]).
    # 0.5 T needs r = 0.5 and 0.5^1.5 * 1000 = 353.55 kW, which is 0.393 of
    # 900 kW, below r: U = 0.5 as without power.
    azimuth = thruster("azimuth", power_supply=(("SWBD", 1.0),))
    t = effective_thrust(azimuth)
    a = allocate_thrust([azimuth], (-0.5 * t, 0.0, 0.0), power_sources=(PowerSource("SWBD", 1000.0),))
    assert a.utilisation == pytest.approx(0.5)
    assert a.thrust_fraction == pytest.approx([0.5])
    assert a.power_kw == pytest.approx([353.553], abs=1e-3)
    assert a.source_power_kw == pytest.approx([353.553], abs=1e-3)


def test_power_limits_a_load_the_thrust_could_balance(thruster):
    # 0.95 T needs 0.95^1.5 * 1000 = 925.95 kW > 900 kW usable:
    # U = 925.95 / 900 = 1.0288 (0.95 is a chord point, so no chord error).
    azimuth = thruster("azimuth", power_supply=(("SWBD", 1.0),))
    t = effective_thrust(azimuth)
    load = (-0.95 * t, 0.0, 0.0)
    a = allocate_thrust([azimuth], load, power_sources=(PowerSource("SWBD", 1000.0),))
    assert a.utilisation == pytest.approx(0.95 ** 1.5 * 1000 / 900)
    assert not a.feasible
    assert allocate_thrust([azimuth], load).utilisation == pytest.approx(0.95)


def test_a_weak_bus_moves_load_to_the_other_thruster(thruster):
    # Two azimuths 40 m apart (> 15D, no flushing) share a surge load T:
    # 0.5 T each without power. Azimuth A's bus has 250 kW (225 kW usable),
    # but 0.5 T would need 353.55 kW, so B takes more of the load.
    a_unit = thruster("azimuth", x=-20.0, power_supply=(("A", 1.0),))
    b_unit = thruster("azimuth", x=20.0, power_supply=(("B", 1.0),))
    sources = (PowerSource("A", 250.0), PowerSource("B", 2000.0))
    t = effective_thrust(a_unit)
    load = (-t, 0.0, 0.0)
    a = allocate_thrust([a_unit, b_unit], load, power_sources=sources)
    assert allocate_thrust([a_unit, b_unit], load).utilisation == pytest.approx(0.5)
    assert 0.5 < a.utilisation < 1.0
    assert a.fx[0] < a.fx[1]
    assert balance_residual([a_unit, b_unit], a, load) == pytest.approx([0.0, 0.0, 0.0], abs=1e-3)
    # The chords lie above r^1.5, so the true power is within U * usable.
    assert np.all(a.source_power_kw <= (a.utilisation + 2 * TOLERANCE) * np.array([225.0, 1800.0]))


@pytest.mark.parametrize("load", [(-100e3, 0.0, 0.0), (60e3, -150e3, 2e6), (-5.5e3, 358e3, 509e3)])
def test_a_generous_plant_changes_nothing(psv, load):
    # 3600 kW per switchboard, 3240 kW usable > 2000 + 900 kW of thrusters.
    supplied = [dataclasses.replace(t, power_supply=((bus, 1.0),)) for t, bus in zip(psv, ["S1", "S2", "S1", "S2"])]
    sources = (PowerSource("S1", 3600.0), PowerSource("S2", 3600.0))
    a = allocate_thrust(supplied, load, power_sources=sources)
    assert a.utilisation == pytest.approx(allocate_thrust(psv, load).utilisation, abs=1e-8)
    assert len(a.source_power_kw) == 2


def test_power_is_reported_without_sources(thruster):
    # thrust_fraction and power_kw don't need a power plant; source_power_kw is empty.
    azimuth = thruster("azimuth")
    a = allocate_thrust([azimuth], (-0.25 * effective_thrust(azimuth), 0.0, 0.0))
    assert a.thrust_fraction == pytest.approx([0.25])
    assert a.power_kw == pytest.approx([125.0])  # 0.25^1.5 * 1000
    assert a.source_power_kw.shape == (0,)


def test_rejects_a_thruster_without_a_power_supply(thruster):
    with pytest.raises(ValueError, match="no power_supply"):
        allocate_thrust([thruster("azimuth")], (1.0, 0.0, 0.0), power_sources=(PowerSource("SWBD", 1000.0),))


def test_rejects_loss_factors_of_the_wrong_length(thruster):
    with pytest.raises(ValueError):
        allocate_thrust([thruster("azimuth")], (1.0, 0.0, 0.0), beta_t=[(0.9, 0.9), (0.9, 0.9)])


def test_rejects_water_jets(thruster):
    with pytest.raises(ValueError):
        allocate_thrust([thruster("water_jet")], (1.0, 0.0, 0.0))


def test_rejects_a_rudder_on_an_azimuth(thruster, rudder):
    with pytest.raises(ValueError, match="shaft line"):
        allocate_thrust([thruster("azimuth", rudder=rudder)], (1.0, 0.0, 0.0))


def test_rejects_a_load_for_several_headings(thruster):
    loads = (np.zeros(36), np.zeros(36), np.zeros(36))
    with pytest.raises(ValueError):
        allocate_thrust([thruster("azimuth")], loads)
