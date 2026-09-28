import math

import pytest

from dp_capability.models.forbidden_zones import (
    allowed_arcs,
    flushing_sectors,
    forbidden_zones_level1,
    merge_zones,
)
from dp_capability.vessel import Thruster

# arctan(0.1 + 2 / 10) = arctan(0.3): the half-angle for D = 2 m, s = 10 m.
HALF_D2_S10 = math.degrees(math.atan(0.3))  # 16.699 deg


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


def test_half_angle():
    assert HALF_D2_S10 == pytest.approx(16.6992, abs=1e-4)
    # The test vessel: D = 3 m, s = 11 m, arctan(0.1 + 3 / 11) = arctan(0.37273).
    assert math.degrees(math.atan(0.1 + 3 / 11)) == pytest.approx(20.4418, abs=1e-4)


def test_side_by_side_azimuths_may_not_push_towards_each_other(thruster):
    # s = 10 < 15D = 30. The vector from the starboard azimuth to the port one
    # points to port (90 deg): pushing that way sends the port azimuth's race
    # onto the starboard one. And the other way round, around -90 deg.
    port, starboard = thruster(y=5.0), thruster(y=-5.0)
    sectors = flushing_sectors([port, starboard])
    assert sectors[0] == [pytest.approx((90 - HALF_D2_S10, 90 + HALF_D2_S10))]
    assert sectors[1] == [pytest.approx((-90 - HALF_D2_S10, -90 + HALF_D2_S10))]


def test_thruster_aft_may_not_push_aft(thruster):
    # Flushing at x = -10, flushed at x = 0: the vector points aft (180 deg).
    # Pushing aft sends the race forward onto the other thruster.
    sectors = flushing_sectors([thruster(x=-10.0), thruster(x=0.0)])
    assert sectors[0] == [pytest.approx((180 - HALF_D2_S10, 180 + HALF_D2_S10))]
    assert sectors[1] == [pytest.approx((-HALF_D2_S10, HALF_D2_S10))]


def test_only_closer_than_15_diameters(thruster):
    # D = 2 m: 15D = 30 m. "Closer than" 15D, so exactly 30 m is allowed.
    assert flushing_sectors([thruster(), thruster(y=29.9)])[0] != []
    assert flushing_sectors([thruster(), thruster(y=30.0)])[0] == []


def test_uses_the_diameter_of_the_flushing_thruster(thruster):
    # s = 25: the D = 2 thruster (15D = 30) flushes the D = 1 one (15D = 15),
    # but not the other way round.
    big, small = thruster(diameter=2.0), thruster(diameter=1.0, y=25.0)
    sectors = flushing_sectors([big, small])
    assert sectors[0] == [pytest.approx((-90 - math.degrees(math.atan(0.1 + 2 / 25)),
                                         -90 + math.degrees(math.atan(0.1 + 2 / 25))))]
    assert sectors[1] == []


def test_tunnels_may_be_flushed_but_can_flush(thruster):
    # The azimuth may flush the tunnel. The tunnel, 10 m to starboard of the
    # azimuth, may not push towards starboard (race to port onto the azimuth).
    tunnel, azimuth = thruster("tunnel"), thruster(y=10.0)
    sectors = flushing_sectors([tunnel, azimuth])
    assert sectors[0] == [pytest.approx((-90 - HALF_D2_S10, -90 + HALF_D2_S10))]
    assert sectors[1] == []


def test_same_position_raises(thruster):
    with pytest.raises(ValueError):
        flushing_sectors([thruster(), thruster()])


def test_figure_a_4_layout(thruster):
    # Figure A-4 / Table A-6: the port aft azimuth (THR 4) has 80-100 deg, the
    # starboard one (THR 5) -100 to -80 deg. The same layout here gives zones
    # around 90 and 270 deg.
    zones = forbidden_zones_level1([thruster(x=-40.0, y=5.0), thruster(x=-40.0, y=-5.0)])
    assert zones[0] == [pytest.approx((90 - HALF_D2_S10, 90 + HALF_D2_S10))]
    assert zones[1] == [pytest.approx((270 - HALF_D2_S10, 270 + HALF_D2_S10))]


def test_user_zones_are_normalised_and_merged(thruster):
    assert merge_zones([(-100.0, -80.0)]) == [(260.0, 280.0)]
    assert merge_zones([(350.0, 10.0)]) == [(350.0, 370.0)]
    # A zone through 0 deg swallows one that starts just after it.
    assert merge_zones([(350.0, 10.0), (5.0, 20.0)]) == [(350.0, 380.0)]
    assert merge_zones([(0.0, 360.0)]) == [(0.0, 360.0)]
    assert merge_zones([(30.0, 30.0)]) == []
    # A user zone overlapping a flushing sector becomes one zone.
    port = thruster(y=5.0, forbidden_zones=((100.0, 120.0),))
    zones = forbidden_zones_level1([port, thruster(y=-5.0)])
    assert zones[0] == [pytest.approx((90 - HALF_D2_S10, 120.0))]


def test_allowed_arcs_without_zones_is_the_full_circle():
    assert allowed_arcs([]) == [None]


def test_allowed_arc_around_one_zone():
    # The test vessel's AZ1: 69.56-110.44 deg forbidden leaves one arc of
    # 319.12 deg, from the end of the zone round to its start.
    assert allowed_arcs([(69.56, 110.44)]) == [pytest.approx((110.44, 429.56))]


def test_allowed_arcs_between_two_zones():
    # Allowed: 100-350 deg and 20-80 deg, the latter written as 380-440 since
    # it follows the zone through 0 deg.
    arcs = allowed_arcs([(350.0, 20.0), (80.0, 100.0)])
    assert arcs == [pytest.approx((100.0, 350.0)), pytest.approx((380.0, 440.0))]


def test_allowed_arcs_everything_forbidden():
    assert allowed_arcs([(0.0, 360.0)]) == []
