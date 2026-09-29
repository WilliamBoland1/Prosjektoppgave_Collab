import math

import numpy as np
import pytest

from dp_capability.models.dead_flushing import dead_flushing_breakpoints, dead_flushing_factor, dead_flushing_loss
from dp_capability.vessel import Thruster


@pytest.fixture
def thruster():
    # Round open azimuth, D = 2 m, at the origin; tests override what they need.
    def make(kind="azimuth", **overrides):
        fields = dict(name="T", kind=kind, diameter=2.0, power_kw=1000.0, x=0.0, y=0.0, z=2.0)
        if kind == "tunnel":
            fields["tunnel_inlet"] = "broken"
        fields.update(overrides)
        return Thruster(**fields)

    return make


def test_open_propeller_ten_metres_ahead_of_a_dead_one(thruster):
    # Dead thruster 10 m aft: the race of forward thrust hits it, so the
    # sector is centred on 0 deg. s/D = 10/2 = 5 < 8:
    #   phi  = arctan(0.6 * 2 / 10) = arctan(0.12) = 6.8428 deg
    #   beta = 1 - 1 / (0.02 * 25 + 0.25 * 5 + 1.2) = 1 - 1/2.95 = 0.66102
    centre, phi, beta = dead_flushing_loss(thruster(), thruster(name="DEAD", x=-10.0))
    assert centre == pytest.approx(0.0)
    assert phi == pytest.approx(6.8428, abs=1e-4)
    assert beta == pytest.approx(0.66102, abs=1e-5)


def test_ducted_propeller_uses_the_narrower_sector(thruster):
    # Ducted, dead 6 m aft: s/D = 3 < 4.
    #   phi  = arctan(0.35 * 2 / 6) = 6.6544 deg
    #   beta = 1 - 1 / (0.02 * 9 + 0.25 * 3 + 1.2) = 1 - 1/2.13 = 0.53052
    centre, phi, beta = dead_flushing_loss(thruster(ducted=True), thruster(name="DEAD", x=-6.0))
    assert centre == pytest.approx(0.0)
    assert phi == pytest.approx(6.6544, abs=1e-4)
    assert beta == pytest.approx(0.53052, abs=1e-5)


def test_the_sector_points_away_from_the_dead_thruster(thruster):
    # Dead thruster 10 m to port: pushing to starboard (270 deg) sends the
    # race onto it.
    centre, _, _ = dead_flushing_loss(thruster(), thruster(name="DEAD", y=10.0))
    assert centre % 360.0 == pytest.approx(270.0)


@pytest.mark.parametrize("ducted, distance, applies", [
    (False, 15.9, True), (False, 16.0, False),  # 8 D = 16 m, "closer than"
    (True, 7.9, True), (True, 8.0, False),      # 4 D = 8 m
])
def test_only_closer_than_8d_open_or_4d_ducted(thruster, ducted, distance, applies):
    loss = dead_flushing_loss(thruster(ducted=ducted), thruster(name="DEAD", x=-distance))
    assert (loss is not None) == applies


def test_a_dead_tunnel_may_be_flushed(thruster):
    assert dead_flushing_loss(thruster(), thruster("tunnel", name="DEAD", x=-6.0)) is None


def test_the_factor_is_beta_at_the_centre_and_one_from_the_sector_edges(thruster):
    flushing, dead = thruster(), thruster(name="DEAD", x=-10.0)
    factor = dead_flushing_factor(flushing, [dead], [0.0, 6.8428, -6.8428, 10.0, 180.0])
    np.testing.assert_allclose(factor, [0.66102, 1.0, 1.0, 1.0, 1.0], atol=1e-4)


def test_the_notch_is_straight_in_cartesian_coordinates(thruster):
    # Figure 3-6: the capacity goes in a straight line from
    # A = beta * (1, 0) = (0.66102, 0) at the centre to
    # B = (cos phi, sin phi) = (0.99288, 0.11915) at the sector edge.
    # Its midpoint M = (0.82695, 0.05957) lies at 4.1204 deg, |M| = 0.82909.
    # (Linear in the angle instead would give 0.86514 there.)
    flushing, dead = thruster(), thruster(name="DEAD", x=-10.0)
    assert dead_flushing_factor(flushing, [dead], 4.1204) == pytest.approx(0.82909, abs=1e-4)
    assert dead_flushing_factor(flushing, [dead], -4.1204) == pytest.approx(0.82909, abs=1e-4)
    # Every angle in between lands on the line through A and B.
    _, phi, beta = dead_flushing_loss(flushing, dead)
    a = np.array([beta, 0.0])
    b = np.array([math.cos(math.radians(phi)), math.sin(math.radians(phi))])
    for angle in np.linspace(0.0, phi, 7):
        r = float(dead_flushing_factor(flushing, [dead], angle))
        p = r * np.array([math.cos(math.radians(angle)), math.sin(math.radians(angle))])
        (ex, ey), (qx, qy) = b - a, p - a
        assert ex * qy - ey * qx == pytest.approx(0.0, abs=1e-12)


def test_several_dead_thrusters_take_the_lowest_factor(thruster):
    # Dead at 10 m aft (beta 0.66102) and at 6 m aft (s/D = 3: beta 0.53052,
    # open, phi = arctan(0.2) = 11.3 deg), both centred on 0 deg.
    flushing = thruster()
    dead = [thruster(name="D1", x=-10.0), thruster(name="D2", x=-6.0)]
    assert dead_flushing_factor(flushing, dead, 0.0) == pytest.approx(0.53052, abs=1e-5)


def test_breakpoints_are_the_sector_edges_and_centre(thruster):
    angles, factors = dead_flushing_breakpoints(thruster(), thruster(name="DEAD", x=-10.0))
    np.testing.assert_allclose(angles, [-6.8428, 0.0, 6.8428], atol=1e-4)
    np.testing.assert_allclose(factors, [1.0, 0.66102, 1.0], atol=1e-5)
    assert dead_flushing_breakpoints(thruster(), thruster(name="DEAD", x=-20.0)) is None


def test_no_dead_thrusters_no_loss(thruster):
    np.testing.assert_array_equal(dead_flushing_factor(thruster(), [], np.arange(0, 360, 10)), np.ones(36))


def test_same_position_raises(thruster):
    with pytest.raises(ValueError):
        dead_flushing_loss(thruster(), thruster(name="DEAD", z=-3.0))
