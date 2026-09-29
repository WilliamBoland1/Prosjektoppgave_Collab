import dataclasses


def failure_case(thrusters, group, power_sources=None):
    """
    What is left of the vessel after the loss of one redundancy group,
    DNV-ST-0111 [2.4.8] and [2.5.4]: the thrusters and power sources of the
    failure run.

    The group's thrusters and power sources are removed. A remaining thruster
    that took part of its power from a lost source keeps running on the
    others, but can only consume its Table A-5 share of them (A.3.5): it
    lost a share s, so its power becomes (1 - s) * P_B and its remaining
    shares are scaled to sum to 1. Since T_Nominal grows with P_B^(2/3)
    ([3.9.2]), its thrust drops to (1 - s)^(2/3) of the intact value, and
    P_B * r^1.5 stays the same power per newton (HANDOVER.md, decisions).

    Parameters
    ----------
    thrusters : sequence of dp_capability.vessel.Thruster
        The intact vessel's actuators.
    group : dp_capability.vessel.RedundancyGroup
    power_sources : sequence of dp_capability.vessel.PowerSource, optional
        The intact operating mode. None: the run has no power limit, but
        thrusters are still derated by the power_supply shares they lose.

    Returns
    -------
    thrusters : list of dp_capability.vessel.Thruster
        The remaining actuators, in their original order.
    power_sources : list of dp_capability.vessel.PowerSource or None
        The remaining sources, in their original order.

    Raises
    ------
    ValueError
        If the group names a thruster or (with power_sources) a source that
        does not exist, or if a thruster outside the group loses all of its
        power: the group then contradicts Table A-5.
    """
    unknown = set(group.thrusters) - {t.name for t in thrusters}
    if unknown:
        raise ValueError(f"redundancy group {group.name!r}: unknown thrusters {sorted(unknown)}")
    lost_sources = set(group.power_sources)
    if power_sources is not None:
        unknown = lost_sources - {s.name for s in power_sources}
        if unknown:
            raise ValueError(f"redundancy group {group.name!r}: unknown power sources {sorted(unknown)}")
        power_sources = [s for s in power_sources if s.name not in lost_sources]

    remaining = []
    for t in thrusters:
        if t.name in group.thrusters:
            continue
        kept = [(name, share) for name, share in t.power_supply if name not in lost_sources]
        if len(kept) < len(t.power_supply):
            left = sum(share for _, share in kept)
            if left <= 0:
                raise ValueError(f"{t.name} has no power left after the loss of {group.name!r}, "
                                 "but is not in the redundancy group")
            t = dataclasses.replace(t, power_kw=left * t.power_kw,
                                    power_supply=tuple((name, share / left) for name, share in kept))
        remaining.append(t)
    return remaining, power_sources
