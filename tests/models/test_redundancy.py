import pytest

from dp_capability.models.power import thruster_power_kw
from dp_capability.models.redundancy import failure_case
from dp_capability.models.thrust import nominal_thrust
from dp_capability.vessel import PowerSource, RedundancyGroup, Thruster


@pytest.fixture
def thruster():
    # Round azimuth at the origin, 100% on "S1"; tests override what they need.
    def make(name, **overrides):
        fields = dict(name=name, kind="azimuth", diameter=2.0, power_kw=1000.0, x=0.0, y=0.0, z=2.0,
                      power_supply=(("S1", 1.0),))
        fields.update(overrides)
        return Thruster(**fields)

    return make


@pytest.fixture
def two_buses(thruster):
    # Two switchboards with the bus-tie open, two thrusters on each, as in
    # config.py.
    thrusters = [
        thruster("A1", power_supply=(("S1", 1.0),)),
        thruster("A2", power_supply=(("S2", 1.0),)),
        thruster("T1", power_supply=(("S1", 1.0),)),
        thruster("T2", power_supply=(("S2", 1.0),)),
    ]
    sources = [PowerSource("S1", 3000.0), PowerSource("S2", 3000.0)]
    return thrusters, sources


def test_the_groups_thrusters_and_sources_are_removed(two_buses):
    thrusters, sources = two_buses
    group = RedundancyGroup("S1", thrusters=("A1", "T1"), power_sources=("S1",))
    remaining, left = failure_case(thrusters, group, sources)
    assert [t.name for t in remaining] == ["A2", "T2"]
    assert remaining[0] is thrusters[1]  # not fed from S1, so unchanged
    assert [s.name for s in left] == ["S2"]


def test_a_group_of_thrusters_only_keeps_all_sources(two_buses):
    # E.g. the loss of one thruster: its switchboard stays.
    thrusters, sources = two_buses
    remaining, left = failure_case(thrusters, RedundancyGroup("A1", thrusters=("A1",)), sources)
    assert [t.name for t in remaining] == ["A2", "T1", "T2"]
    assert left == sources


def test_a_split_feed_is_capped_at_the_remaining_share(thruster):
    # 50% from S1 and 50% from S2, S1 lost: it may still consume its 50% of
    # S2, so P_B = 0.5 * 1000 = 500 kW, all of it from S2.
    # T_Nominal ~ P_B^(2/3), so the thrust drops to 0.5^(2/3) = 0.630.
    split = thruster("A", power_supply=(("S1", 0.5), ("S2", 0.5)))
    (derated,), _ = failure_case([split], RedundancyGroup("S1", power_sources=("S1",)))
    assert derated.power_kw == pytest.approx(500.0)
    assert derated.power_supply == (("S2", 1.0),)
    assert nominal_thrust(derated) / nominal_thrust(split) == pytest.approx(0.5 ** (2 / 3))
    assert 0.5 ** (2 / 3) == pytest.approx(0.630, abs=1e-3)


def test_the_remaining_shares_are_rescaled_to_sum_to_one(thruster):
    # 25% lost: P_B = 0.75 * 1000 = 750 kW, shares 0.5/0.75 = 2/3 and
    # 0.25/0.75 = 1/3, i.e. still 500 and 250 kW from S2 and S3.
    split = thruster("A", power_supply=(("S1", 0.25), ("S2", 0.5), ("S3", 0.25)))
    (derated,), _ = failure_case([split], RedundancyGroup("S1", power_sources=("S1",)))
    assert derated.power_kw == pytest.approx(750.0)
    (s2, share2), (s3, share3) = derated.power_supply
    assert (s2, s3) == ("S2", "S3")
    assert (share2, share3) == pytest.approx((2 / 3, 1 / 3))


def test_the_cap_leaves_the_power_per_thrust_unchanged(thruster):
    # At full thrust the derated thruster (P_B = 500 kW) gives 0.630 of the
    # intact nominal thrust. The intact one needs 1000 * 0.630^1.5 =
    # 1000 * 0.5 = 500 kW for that same thrust: the same power.
    split = thruster("A", power_supply=(("S1", 0.5), ("S2", 0.5)))
    (derated,), _ = failure_case([split], RedundancyGroup("S1", power_sources=("S1",)))
    same_thrust = nominal_thrust(derated) / nominal_thrust(split)
    assert thruster_power_kw(derated, 1.0) == pytest.approx(thruster_power_kw(split, same_thrust))
    assert thruster_power_kw(split, same_thrust) == pytest.approx(500.0)


def test_without_power_sources_thrusters_are_still_derated(thruster):
    split = thruster("A", power_supply=(("S1", 0.5), ("S2", 0.5)))
    (derated,), left = failure_case([split], RedundancyGroup("S1", power_sources=("S1",)))
    assert left is None
    assert derated.power_kw == pytest.approx(500.0)


def test_a_thruster_left_without_power_must_be_in_the_group(two_buses):
    # A1 and T1 take all their power from S1, so a group that loses S1 but
    # not them contradicts Table A-5.
    thrusters, sources = two_buses
    with pytest.raises(ValueError, match="A1"):
        failure_case(thrusters, RedundancyGroup("S1", power_sources=("S1",)), sources)


@pytest.mark.parametrize("group", [
    RedundancyGroup("typo", thrusters=("A3",)),
    RedundancyGroup("typo", power_sources=("S3",)),
])
def test_unknown_names_raise(two_buses, group):
    thrusters, sources = two_buses
    with pytest.raises(ValueError, match="unknown"):
        failure_case(thrusters, group, sources)
