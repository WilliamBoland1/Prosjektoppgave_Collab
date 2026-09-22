from dp_capability.models.currentloads import current_loads_level1
from dp_capability.models.waveloads import wave_loads_level1
from dp_capability.models.windloads import wind_loads_level1
from dp_capability.standard import DYNAMIC_FACTOR_LEVEL1, environment


def environmental_loads_level1(hull, bf, direction_deg, dynamic_factor=DYNAMIC_FACTOR_LEVEL1):
    """
    Total factored environmental load for DP capability level 1: wind [3.5],
    current [3.6] and wave drift [3.7] in the Table 2-1 environment for `bf`,
    summed and multiplied by the dynamic factor of [3.2.2].

    Wind, current and waves are collinear ([3.3.1]), all coming from
    direction_deg. The individual load functions return the standard's
    formulas unfactored; the dynamic factor is applied only here, once, to
    the sum.

    Parameters
    ----------
    hull : dp_capability.vessel.Hull
        Vessel hull data.
    bf : int
        DP capability number (Beaufort number), 0-11.
    direction_deg : float or array-like
        Direction the environment is coming from, clockwise: 0 deg = head-on,
        90 deg = from starboard. Can be a numpy array.
    dynamic_factor : float, optional
        Defaults to DYNAMIC_FACTOR_LEVEL1 = 1.25.

    Returns
    -------
    fx, fy, mz
        Surge force [N], sway force [N] and yaw moment [Nm] that the actuators
        must balance.
    """
    env = environment(bf)
    wind = wind_loads_level1(hull, env.wind_speed, direction_deg)
    current = current_loads_level1(hull, env.current_speed, direction_deg)
    wave = wave_loads_level1(hull, env.hs, env.tp, direction_deg)
    return tuple(dynamic_factor * (w + c + s) for w, c, s in zip(wind, current, wave))
