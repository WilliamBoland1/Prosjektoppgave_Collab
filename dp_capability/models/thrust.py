import numpy as np
from scipy.stats import norm

from dp_capability.standard import (
    BETA_MISC,
    ETA1,
    ETA2_FORWARD,
    ETA2_REVERSED,
    ETA2_TUNNEL,
    ETA_M,
    K_V1,
    K_V2,
    K_V3,
    K_V4,
    K_V5,
    TZ_FROM_TP,
    fold_direction,
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

    beta_T defaults to beta_misc = 0.9 ([3.9.3]), i.e. without the
    ventilation loss. For level 1 pass thrust_loss_factor_level1() as beta_t
    ([3.9.5]).

    Returns
    -------
    float
        Effective thrust [N].
    """
    return nominal_thrust(thruster, reverse) * beta_t


def _propeller_load_factor(t_nominal, diameter):
    """PropellerLoadFactor in [3.9.4]: sqrt(|T_Nominal| / D^3) / k_V3, T in N and D in m."""
    return np.sqrt(np.abs(t_nominal) / diameter ** 3) / K_V3


def _relative_motion_std(hull, x, hs, tz, direction_rad, propeller_load_factor):
    """
    sigma in [3.9.4]: the standard deviation of the relative vertical motion
    between the actuator and the free surface [m].

        sigma = 0.25 * (A * Hs * min(T0, 1) + max(PropellerLoadFactor - 1, 0))

    direction_rad is where the waves come from; only its size matters (the
    abs(direction) of the standard, over [-pi, pi]). Where hs = 0 the wave
    term is 0, whatever tz is.
    """
    folded = fold_direction(np.mod(direction_rad, 2 * np.pi))
    # B rises from 1 in head seas to 1 + k_V5/2 at beam and falls back to 1
    # astern. The standard writes the second range with an intersection sign,
    # which can only mean the union [-pi, -pi/2] and [pi/2, pi].
    b = np.where(folded <= np.pi / 2, 1 + K_V5 * folded / np.pi, (1 + K_V5) - K_V5 * folded / np.pi)
    # Aft of midships the relative motion is smaller.
    c = 1.0 if x >= 0 else 1 + 0.4 * x / hull.lpp
    a = K_V4 * b * c
    hs = np.asarray(hs, dtype=float)
    t0 = 0.64 * np.sqrt(hull.lpp) / np.asarray(tz, dtype=float)
    waves = np.where(hs == 0.0, 0.0, a * hs * np.minimum(t0, 1.0))
    return 0.25 * (waves + max(propeller_load_factor - 1, 0.0))


def ventilation_loss_factor(thruster, hull, hs, tp, direction_deg, reverse=False):
    """
    Thrust loss factor for ventilation, DNV-ST-0111 [3.9.4]:

        beta_vent = Phi(k_V1 * 2 * xi / D - k_V2 * sigma)

    with Phi the standard normal distribution function, xi = draft - z the
    submergence of the actuator ([3.8.3]) and sigma from
    _relative_motion_std(). T_Nominal in the propeller load is the nominal
    thrust of [3.9.2] in the direction considered (HANDOVER.md, decisions).
    Applies to every actuator kind, tunnel thrusters included.

    Parameters
    ----------
    thruster : dp_capability.vessel.Thruster
        Actuator data (Table A-3); uses diameter, x and z.
    hull : dp_capability.vessel.Hull
        Vessel hull data; uses draft and lpp.
    hs : float or array-like
        Significant wave height [m]. hs = 0 leaves only the propeller load.
    tp : float or array-like
        Peak period [s]; Tz = Tp / 1.4049 ([3.3.3]). May be nan when hs = 0,
        as for BF 0 in Table 2-1.
    direction_deg : float or array-like
        Direction the waves are coming from, clockwise: 0 deg = head-on,
        90 deg = from starboard. Can be a numpy array.
    reverse : bool, optional
        True for the reversed thrust, which changes T_Nominal ([3.9.2]).

    Returns
    -------
    numpy.ndarray
        beta_vent, between 0 and 1, the shape of direction_deg.
    """
    tz = np.asarray(tp, dtype=float) / TZ_FROM_TP
    plf = _propeller_load_factor(nominal_thrust(thruster, reverse), thruster.diameter)
    sigma = _relative_motion_std(hull, thruster.x, hs, tz, np.deg2rad(direction_deg), plf)
    xi = hull.draft - thruster.z
    return norm.cdf(K_V1 * 2 * xi / thruster.diameter - K_V2 * sigma)


def thrust_loss_factor_level1(thruster, hull, hs, tp, direction_deg, reverse=False):
    """
    Total thrust loss factor, DNV-ST-0111 [3.9.5]: beta_T = beta_misc * beta_vent.
    Same parameters as ventilation_loss_factor(). Pass the result as beta_t
    to effective_thrust().

    [3.11.6] extends this to beta_misc * beta_vent * beta_flushing,dead *
    beta_flushing,skeg. The skeg factor depends on the thrust direction, so
    allocate_thrust() applies it to the capacity polygon (skeg_loss.py);
    flushing a dead thruster only happens in failure cases (step 8).
    """
    return BETA_MISC * ventilation_loss_factor(thruster, hull, hs, tp, direction_deg, reverse)
