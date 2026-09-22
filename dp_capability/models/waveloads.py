import numpy as np

from dp_capability.standard import G, RHO_WATER, TZ_FROM_TP, fold_direction


def _period_factor(t_prime):
    """
    f(T') in DNV-ST-0111 [3.7]: 1 for T' < 1, T'^-3 * e^(1 - T'^-3) for
    T' >= 1. Both branches give exactly 1 at T' = 1, so f is continuous.
    """
    t_prime = np.asarray(t_prime, dtype=float)
    return np.where(t_prime < 1.0, 1.0, t_prime ** -3 * np.exp(1 - t_prime ** -3))


def wave_loads_level1(hull, hs, tp, direction_deg):
    """
    Wave drift forces and yaw moment for DP capability level 1,
    DNV-ST-0111 [3.7].

    Uses the standard's body frame and sign convention (x forward, y to port,
    yaw positive counter-clockwise, see dp_capability/standard.py).

    Parameters
    ----------
    hull : dp_capability.vessel.Hull
        Vessel hull data; uses breadth, lpp, los, x_los, bow_angle and aw_laft.
    hs : float or array-like
        Significant wave height [m]. hs = 0 gives zero load, whatever tp is.
    tp : float or array-like
        Peak period [s] of the Pierson-Moskowitz spectrum ([3.3.3]). May be
        nan when hs = 0, as for BF 0 in Table 2-1.
    direction_deg : float or array-like
        Direction the waves are coming from, clockwise: 0 deg = head-on,
        90 deg = from starboard. Values outside 0-360 deg are wrapped. Can be
        a numpy array, e.g. to evaluate all headings of an envelope at once.

    Returns
    -------
    fx, fy, mz
        Surge force [N], sway force [N] and yaw moment [Nm].
    """
    direction = np.deg2rad(np.mod(direction_deg, 360.0))
    folded = fold_direction(direction)
    hs = np.asarray(hs, dtype=float)
    q = 0.5 * RHO_WATER * G * hs ** 2
    tz = np.asarray(tp, dtype=float) / TZ_FROM_TP

    c_wlaft = np.clip(hull.aw_laft / (hull.lpp / 2 * hull.breadth), 0.85, 1.15)
    h1a = 0.8 * hull.bow_angle ** 0.45
    h1b = 0.7 * c_wlaft ** 2
    h1 = h1a + folded / np.pi * (h1b - h1a)
    # h2 < 0 (pushed aft) in head seas and > 0 (pushed forward) in following
    # seas; it changes sign at dir = 1.7137 rad (98.2 deg).
    h2 = 0.05 + 0.95 * np.arctan(1.45 * (folded - 1.75))

    t_surge = tz / (0.9 * hull.lpp ** 0.33)
    t_sway = tz / (0.75 * hull.breadth ** 0.5)

    fx = q * hull.breadth * 0.09 * h1 * h2 * _period_factor(t_surge)
    fy = q * hull.los * (0.09 * np.sin(direction)) * _period_factor(t_sway)
    # The centre of pressure moves from 0.05*Los forward of x_Los in head
    # seas to 0.09*Los aft of it in following seas.
    mz = fy * (hull.x_los + (0.05 - 0.14 * folded / np.pi) * hull.los)

    # BF 0 has hs = 0 and tp = nan, and 0 * nan = nan, so calm sea is set to
    # zero explicitly.
    calm = hs == 0.0
    return tuple(np.where(calm, 0.0, load) for load in (fx, fy, mz))
