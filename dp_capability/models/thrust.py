from dp_capability.standard import (
    BETA_MISC,
    ETA1,
    ETA2_FORWARD,
    ETA2_REVERSED,
    ETA2_TUNNEL,
    ETA_M,
)

KINDS = ("azimuth", "pod", "shaft_line", "tunnel", "cycloidal")


def _check_kind(thruster):
    if thruster.kind == "water_jet":
        # [3.8.1]: actuator types not covered by the section, e.g. water jets,
        # need data supplied by the manufacturer.
        raise ValueError(f"{thruster.name}: water jets are not covered by Tables 3-1 to 3-4, see [3.8.1]")
    if thruster.kind not in KINDS:
        raise ValueError(f"{thruster.name}: unknown actuator kind {thruster.kind!r}")


def _eta1(thruster):
    """Efficiency factor eta_1 from DNV-ST-0111 Table 3-1."""
    _check_kind(thruster)
    if thruster.kind in ("tunnel", "cycloidal"):
        return ETA1[thruster.kind]
    if thruster.ducted and thruster.contra_rotating:
        raise ValueError(f"{thruster.name}: Table 3-1 has no row for ducted contra-rotating propellers")
    if thruster.ducted:
        return ETA1["ducted"]
    if thruster.contra_rotating:
        return ETA1["contra_rotating"]
    return ETA1["propeller"]


def _eta2(thruster, reverse=False):
    """
    Efficiency factor eta_2 from DNV-ST-0111 Table 3-2 (tunnel thrusters, by
    inlet shape, the same in both directions) or Table 3-3 (all other
    actuators, 1.0 forward and by pitch and duct in reverse).
    """
    _check_kind(thruster)
    if thruster.kind == "tunnel":
        if thruster.tunnel_inlet not in ETA2_TUNNEL:
            raise ValueError(
                f"{thruster.name}: tunnel inlet must be one of {sorted(ETA2_TUNNEL)}, got {thruster.tunnel_inlet!r}"
            )
        return ETA2_TUNNEL[thruster.tunnel_inlet]
    if thruster.pitch not in ("FPP", "CPP"):
        raise ValueError(f"{thruster.name}: pitch must be 'FPP' or 'CPP', got {thruster.pitch!r}")
    # Cycloidals are not reversed, so eta_2 = 1.0 (guidance note to Table 3-3).
    if not reverse or thruster.kind == "cycloidal":
        return ETA2_FORWARD
    return ETA2_REVERSED[(thruster.pitch, thruster.ducted)]


def _eta_m(thruster):
    """
    Mechanical efficiency eta_M from DNV-ST-0111 Table 3-4.

    Table A-3 only records whether a thruster is a permanent magnet thruster,
    so every permanent magnet actuator other than a cycloidal is taken as
    rim-driven.
    """
    _check_kind(thruster)
    if thruster.permanent_magnet:
        return ETA_M["pm_cycloidal"] if thruster.kind == "cycloidal" else ETA_M["rim_driven_pm"]
    return ETA_M[thruster.kind]


def nominal_thrust(thruster, reverse=False):
    """
    Nominal thrust of one actuator, DNV-ST-0111 [3.9.2]:

        T_Nominal = eta_1 * eta_2 * (D * P)^(2/3),   P = P_B * eta_M

    with D in m and P in kW, which gives the thrust in N.

    Parameters
    ----------
    thruster : dp_capability.vessel.Thruster
        Actuator data (Table A-3).
    reverse : bool, optional
        True for reversed thrust. Only changes eta_2, and only for actuators
        other than tunnel thrusters and cycloidals (Table 3-3).

    Returns
    -------
    float
        Nominal thrust [N], i.e. the thrust with no wind, waves or current.
    """
    power = thruster.power_kw * _eta_m(thruster)
    return _eta1(thruster) * _eta2(thruster, reverse) * (thruster.diameter * power) ** (2 / 3)


def effective_thrust(thruster, reverse=False, beta_t=BETA_MISC):
    """
    Effective thrust of one actuator, DNV-ST-0111 [3.9.1]:
    T_Effective = T_Nominal * beta_T.

    beta_T defaults to beta_misc = 0.9 ([3.9.3]). The ventilation loss
    ([3.9.4]-[3.9.5]) is not included yet; pass the full loss factor as
    beta_t when it is.

    Returns
    -------
    float
        Effective thrust [N].
    """
    return nominal_thrust(thruster, reverse) * beta_t
