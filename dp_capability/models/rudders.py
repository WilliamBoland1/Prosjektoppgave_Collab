import numpy as np

from dp_capability.standard import (
    K1_RUDDER,
    K2_RUDDER,
    RUDDER_ANGLE_CAP_DEG,
    RUDDER_C_X_FROM_C_Y,
    RUDDER_C_Y,
)


def _rudder(thruster):
    """The thruster's rudder; ValueError if it has none or is not a shaft line."""
    if thruster.rudder is None:
        raise ValueError(f"{thruster.name}: has no rudder")
    if thruster.kind != "shaft_line":
        raise ValueError(f"{thruster.name}: only shaft line propellers can have a rudder, [3.10]")
    return thruster.rudder


def rudder_coefficients(thruster):
    """
    Drag and lift coefficients of a rudder behind a propeller, DNV-ST-0111
    [3.10.1]:

        C_Y = 0.0126 * k1 * k2 * A_r / D^2
        C_x = 0.02 * C_Y

    with k1 from Table 3-5 (profile type) and k2 from Table 3-6 (1.15 behind
    a fixed propeller nozzle, else 1.0). Both are per degree of rudder angle
    (C_Y) or per degree squared (C_x).

    Parameters
    ----------
    thruster : dp_capability.vessel.Thruster
        A shaft line propeller with a Rudder (Table A-4).

    Returns
    -------
    (float, float)
        (C_x, C_Y).
    """
    rudder = _rudder(thruster)
    if rudder.profile not in K1_RUDDER:
        raise ValueError(f"{thruster.name}: rudder profile must be one of {sorted(K1_RUDDER)}, got {rudder.profile!r}")
    k2 = K2_RUDDER["fixed_nozzle" if rudder.behind_fixed_nozzle else "other"]
    c_y = RUDDER_C_Y * K1_RUDDER[rudder.profile] * k2 * rudder.area / thruster.diameter ** 2
    return RUDDER_C_X_FROM_C_Y * c_y, c_y


def max_rudder_angle_deg(thruster):
    """The largest rudder angle the [3.10.1] forces use [deg]: the rudder's maximum, but at most 30 deg."""
    return min(_rudder(thruster).max_angle_deg, RUDDER_ANGLE_CAP_DEG)


def rudder_forces(thruster, t_effective, rudder_angle_deg):
    """
    Surge and sway force of a propeller giving positive thrust together with
    the rudder behind it, DNV-ST-0111 [3.10.1]:

        F_Surge = T_Effective * (1 - C_x * alpha^2)
        F_Sway  = T_Effective * C_Y * alpha

    alpha is the rudder angle in degrees. Angles beyond the maximum (at most
    30 deg, see max_rudder_angle_deg) give the values at the maximum. The
    standard does not fix the sign of alpha; here positive alpha gives sway
    to port. With negative thrust the rudder is neglected ([3.10.2]), so
    there is no reverse version of this function.

    Parameters
    ----------
    thruster : dp_capability.vessel.Thruster
        A shaft line propeller with a Rudder (Table A-4).
    t_effective : float
        Forward effective thrust of the propeller [N], [3.9.1].
    rudder_angle_deg : float or array-like
        Rudder angle alpha [deg].

    Returns
    -------
    (numpy.ndarray, numpy.ndarray)
        (F_Surge, F_Sway) [N], the shape of rudder_angle_deg.
    """
    c_x, c_y = rudder_coefficients(thruster)
    limit = max_rudder_angle_deg(thruster)
    alpha = np.clip(np.asarray(rudder_angle_deg, dtype=float), -limit, limit)
    return t_effective * (1 - c_x * alpha ** 2), t_effective * c_y * alpha
