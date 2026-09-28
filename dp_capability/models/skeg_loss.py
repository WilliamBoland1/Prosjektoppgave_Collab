import math

import numpy as np

# The skeg loss applies closer than this many diameters to the skeg plane, [3.11.5].
SKEG_DISTANCE_D_OPEN = 15.0
SKEG_DISTANCE_D_DUCTED = 8.0


def skeg_loss_breakpoints(thruster, skeg):
    """
    Thrust loss factor due to one skeg as breakpoints of Table 3-7 (port
    thrusters) or Table 3-8 (starboard thrusters), DNV-ST-0111 [3.11.5]:

        s         = sqrt((x_skeg - x_thr)^2 + (y_skeg - y_thr)^2)   if x_skeg > x_thr
                    |y_skeg - y_thr|                                if x_skeg <= x_thr
        alpha_jet = arctan(0.6 * D / s)

    Port (y_thr > y_skeg):
        alpha_flush   = pi/2 - arctan((x_skeg - x_thr) / (y_skeg - y_thr))
        alpha_maxloss = min(max(alpha_flush + alpha_jet, pi/2), pi)
        1 from 0 to max(alpha_flush - alpha_jet, 0),
        2 * alpha_maxloss / pi - 1 at alpha_maxloss,
        1 from min(alpha_maxloss + 4 * alpha_jet, pi) to 2 pi.
    Starboard (y_thr < y_skeg):
        alpha_flush   = 3pi/2 - arctan((x_skeg - x_thr) / (y_skeg - y_thr))
        alpha_maxloss = max(min(alpha_flush - alpha_jet, 3pi/2), pi)
        1 from pi to max(alpha_maxloss - 4 * alpha_jet, pi),
        3 - 2 * alpha_maxloss / pi at alpha_maxloss,
        1 from min(alpha_flush + alpha_jet, 2 pi) to 2 pi.

    alpha_flush is the thrust angle ([3.8.2]) that sends the race at the aft
    most point of the skeg. The loss applies to thrusters above the base line
    (z > 0) other than tunnel thrusters, closer than 15 D (open) or 8 D
    (ducted) to the skeg plane and not directly behind the skeg. A thruster
    level with the skeg (y_thr = y_skeg) is on neither side, so neither table
    applies.

    Parameters
    ----------
    thruster : dp_capability.vessel.Thruster
    skeg : (float, float)
        (x, y) of the aft most point of the skeg or gondola [m].

    Returns
    -------
    (numpy.ndarray, numpy.ndarray) or None
        Thrust angles [deg], increasing from 0 to 360, and the loss factor at
        each; linear in between. None if the loss does not apply.
    """
    x_skeg, y_skeg = skeg
    dx, dy = x_skeg - thruster.x, y_skeg - thruster.y
    if thruster.kind == "tunnel" or thruster.z <= 0 or dy == 0:
        return None
    s = math.hypot(dx, dy) if x_skeg > thruster.x else abs(dy)
    reach = SKEG_DISTANCE_D_DUCTED if thruster.ducted else SKEG_DISTANCE_D_OPEN
    if s >= reach * thruster.diameter:
        return None
    alpha_jet = math.atan(0.6 * thruster.diameter / s)
    pi = math.pi
    if dy < 0:  # port of the skeg, Table 3-7
        alpha_flush = pi / 2 - math.atan(dx / dy)
        alpha_maxloss = min(max(alpha_flush + alpha_jet, pi / 2), pi)
        points = [
            (0.0, 1.0),
            (max(alpha_flush - alpha_jet, 0.0), 1.0),
            (alpha_maxloss, 2 * alpha_maxloss / pi - 1),
            (min(alpha_maxloss + 4 * alpha_jet, pi), 1.0),
            (2 * pi, 1.0),
        ]
    else:  # starboard of the skeg, Table 3-8
        alpha_flush = 3 * pi / 2 - math.atan(dx / dy)
        alpha_maxloss = max(min(alpha_flush - alpha_jet, 3 * pi / 2), pi)
        points = [
            (0.0, 1.0),
            (pi, 1.0),
            (max(alpha_maxloss - 4 * alpha_jet, pi), 1.0),
            (alpha_maxloss, 3 - 2 * alpha_maxloss / pi),
            (min(alpha_flush + alpha_jet, 2 * pi), 1.0),
            (2 * pi, 1.0),
        ]
    # Drop repeated angles (a range of zero width), keeping the lower factor.
    angles, factors = [], []
    for angle, factor in points:
        if angles and math.isclose(angle, angles[-1], abs_tol=1e-12):
            factors[-1] = min(factors[-1], factor)
        else:
            angles.append(angle)
            factors.append(factor)
    return np.degrees(angles), np.array(factors)


def skeg_loss_factor(thruster, skegs, angle_deg):
    """
    Thrust loss factor due to skeg(s), beta_T,flushing skeg of DNV-ST-0111
    [3.11.5], at the given thrust angles ([3.8.2]: 0 deg forward,
    counter-clockwise). Linear in the angle between the breakpoints of
    skeg_loss_breakpoints() ("linear interpolation in polar coordinates").
    With several skegs the lowest factor counts (HANDOVER.md, decisions).

    Parameters
    ----------
    thruster : dp_capability.vessel.Thruster
    skegs : sequence of (float, float)
        Aft most point of each skeg or gondola, e.g. Hull.skegs.
    angle_deg : float or array-like
        Thrust angles [deg].

    Returns
    -------
    numpy.ndarray
        The factor, between 0 and 1, the shape of angle_deg. 1 where no skeg
        applies.
    """
    angle = np.mod(np.asarray(angle_deg, dtype=float), 360.0)
    factor = np.ones_like(angle)
    for skeg in skegs:
        breakpoints = skeg_loss_breakpoints(thruster, skeg)
        if breakpoints is not None:
            factor = np.minimum(factor, np.interp(angle, *breakpoints))
    return factor
