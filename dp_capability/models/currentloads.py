import numpy as np

from dp_capability.standard import RHO_WATER, fold_direction


def current_loads_level1(hull, current_speed, direction_deg):
    """
    Current forces and yaw moment for DP capability level 1, DNV-ST-0111 [3.6].

    Uses the standard's body frame and sign convention (x forward, y to port,
    yaw positive counter-clockwise, see dp_capability/standard.py).

    Parameters
    ----------
    hull : dp_capability.vessel.Hull
        Vessel hull data; uses breadth, draft, al_current, xl_current and lpp.
        FX uses breadth * draft, not af_current, which Level 1 does not use.
    current_speed : float or array-like
        Current speed, vertically uniform ([3.3.2]) [m/s].
    direction_deg : float or array-like
        Direction the current is coming from, clockwise: 0 deg = head-on,
        90 deg = from starboard. Values outside 0-360 deg are wrapped. Can be
        a numpy array, e.g. to evaluate all headings of an envelope at once.

    Returns
    -------
    fx, fy, mz
        Surge force [N], sway force [N] and yaw moment [Nm].
    """
    direction = np.deg2rad(np.mod(direction_deg, 360.0))
    q = 0.5 * RHO_WATER * np.asarray(current_speed, dtype=float) ** 2

    fx = q * hull.breadth * hull.draft * (-0.07 * np.cos(direction))
    fy = q * hull.al_current * (0.6 * np.sin(direction))
    # Like wind, the centre of pressure moves aft as the current comes more
    # from astern, but the shift is clipped to 0.25*Lpp forward (below
    # 33.75 deg) and 0.2*Lpp aft (above 135 deg) of xl_current.
    shift = np.clip(0.4 * (1 - 2 * fold_direction(direction) / np.pi), -0.2, 0.25)
    mz = fy * (hull.xl_current + shift * hull.lpp)

    return fx, fy, mz
