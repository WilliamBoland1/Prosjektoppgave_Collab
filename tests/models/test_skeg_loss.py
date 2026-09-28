import numpy as np
import pytest

from dp_capability.models.skeg_loss import skeg_loss_breakpoints, skeg_loss_factor
from dp_capability.vessel import Thruster

SKEG = (-36.0, 0.0)


@pytest.fixture
def thruster():
    # Builds a thruster with round default data; tests override what they
    # need. Tunnels get a broken inlet by default, since they need one.
    def make(kind="azimuth", **overrides):
        fields = dict(name="T", kind=kind, diameter=2.0, power_kw=1000.0, x=0.0, y=0.0, z=2.0)
        if kind == "tunnel":
            fields["tunnel_inlet"] = "broken"
        fields.update(overrides)
        return Thruster(**fields)

    return make


@pytest.fixture
def round_port(thruster):
    # Open, D = 10, at (-30, 6), forward and to port of the skeg end (-36, 0):
    #   x_skeg <= x_thr, so s = |0 - 6| = 6;  alpha_jet = arctan(0.6 * 10 / 6) = 45 deg
    #   alpha_flush = 90 - arctan(-6 / -6) = 90 - 45 = 45 deg
    #   alpha_maxloss = min(max(45 + 45, 90), 180) = 90 deg, factor 2 * 90/180 - 1 = 0
    #   1 up to max(45 - 45, 0) = 0 deg, back to 1 at min(90 + 4 * 45, 180) = 180 deg
    return thruster(diameter=10.0, x=-30.0, y=6.0)


def test_round_port_thruster_breakpoints(round_port):
    angles, factors = skeg_loss_breakpoints(round_port, SKEG)
    assert angles == pytest.approx([0.0, 90.0, 180.0, 360.0])
    assert factors == pytest.approx([1.0, 0.0, 1.0, 1.0])


def test_round_port_thruster_is_linear_in_the_angle(round_port):
    # Pushing at 45 deg sends the race at 225 deg, straight at the skeg end.
    beta = skeg_loss_factor(round_port, [SKEG], [0.0, 45.0, 90.0, 135.0, 180.0, 270.0, -270.0])
    assert beta == pytest.approx([1.0, 0.5, 0.0, 0.5, 1.0, 1.0, 0.0])


def test_starboard_thruster_is_the_mirror(thruster, round_port):
    # At (-30, -6): alpha_flush = 270 - arctan(-6 / 6) = 315 deg,
    # alpha_maxloss = max(min(315 - 45, 270), 180) = 270 deg, factor 3 - 3 = 0,
    # 1 from 180 to max(270 - 180, 180) = 180 deg and from min(360, 360).
    starboard = thruster(diameter=10.0, x=-30.0, y=-6.0)
    angles, factors = skeg_loss_breakpoints(starboard, SKEG)
    assert angles == pytest.approx([0.0, 180.0, 270.0, 360.0])
    assert factors == pytest.approx([1.0, 1.0, 0.0, 1.0])
    theta = np.arange(0.0, 360.0, 7.5)
    assert skeg_loss_factor(starboard, [SKEG], 360.0 - theta) == pytest.approx(skeg_loss_factor(round_port, [SKEG], theta))


def test_thruster_aft_of_the_skeg(thruster):
    # The test vessel's AZ1: ducted, D = 3, at (-40, 5.5). x_skeg > x_thr, so
    #   s = sqrt(4^2 + 5.5^2) = sqrt(46.25) = 6.8007 < 8D = 24
    #   alpha_jet = arctan(1.8 / 6.8007) = 14.826 deg
    #   alpha_flush = 90 - arctan(4 / -5.5) = 90 + 36.027 = 126.027 deg
    #   alpha_maxloss = 126.027 + 14.826 = 140.852 deg, factor 2 * 140.852/180 - 1 = 0.56503
    #   1 up to 126.027 - 14.826 = 111.202 deg, back to 1 at min(140.852 + 59.30, 180) = 180
    az1 = thruster(diameter=3.0, power_kw=2000.0, x=-40.0, y=5.5, z=1.8, ducted=True)
    angles, factors = skeg_loss_breakpoints(az1, SKEG)
    assert angles == pytest.approx([0.0, 111.202, 140.852, 180.0, 360.0], abs=1e-3)
    assert factors == pytest.approx([1.0, 1.0, 0.56503, 1.0, 1.0], abs=1e-5)


@pytest.mark.parametrize(
    "kind, overrides",
    [
        ("tunnel", {}),  # tunnels are exempt
        ("azimuth", {"z": 0.0}),  # not above the base line
        ("azimuth", {"y": 0.0}),  # directly behind the skeg
        ("azimuth", {"diameter": 0.8, "ducted": True}),  # s = 6.80 >= 8D = 6.4
    ],
)
def test_not_applicable(thruster, kind, overrides):
    unit = thruster(kind, **{"x": -40.0, "y": 5.5, **overrides})
    assert skeg_loss_breakpoints(unit, SKEG) is None
    assert skeg_loss_factor(unit, [SKEG], [0.0, 90.0, 135.0, 225.0]) == pytest.approx([1.0] * 4)


def test_open_propeller_reaches_further(thruster):
    # Same place and D = 0.8 as the ducted case above, but open: 15D = 12 > 6.80.
    assert skeg_loss_breakpoints(thruster(diameter=0.8, x=-40.0, y=5.5), SKEG) is not None


def test_no_skegs_no_loss(round_port):
    assert skeg_loss_factor(round_port, [], [45.0, 90.0]) == pytest.approx([1.0, 1.0])


def test_several_skegs_take_the_lowest_factor(round_port):
    # A second skeg end at (-36, 12) is 6 m to port of the thruster, so it is
    # the starboard case mirrored: no thrust at 270 deg. The first skeg still
    # takes 90 deg.
    beta = skeg_loss_factor(round_port, [SKEG, (-36.0, 12.0)], [0.0, 45.0, 90.0, 225.0, 270.0])
    assert beta == pytest.approx([1.0, 0.5, 0.0, 0.5, 0.0])
