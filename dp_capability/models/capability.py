import numpy as np

from dp_capability.models.environmental_loads import environmental_loads_level1
from dp_capability.models.thruster_allocation import allocate_thrust
from dp_capability.standard import ENVIRONMENT_TABLE, environment


def capability_numbers_level1(hull, thrusters, headings_deg):
    """
    DP capability number per heading for DP capability level 1, DNV-ST-0111
    [2.2.2], [2.4.4] and [3.2.2].

    For each heading the Table 2-1 conditions are balanced from the lowest
    one upwards ([2.4.4]): the factored load of environmental_loads_level1()
    against allocate_thrust(). The number is the last condition before the
    first one that cannot be balanced, so the vessel also holds in every
    condition below it ([2.2.2]). Later conditions are not tried after the
    first failure. 11 if all balance, 0 if BF 1 already fails.

    Parameters
    ----------
    hull : dp_capability.vessel.Hull
        Vessel hull data.
    thrusters : sequence of dp_capability.vessel.Thruster
        The active actuators (Table A-3).
    headings_deg : float or array-like
        Direction the environment is coming from, clockwise: 0 deg = head-on,
        90 deg = from starboard. [2.4.6] asks for at least 10 deg resolution
        over the full 360 deg.

    Returns
    -------
    numpy.ndarray of int
        DP capability number (0-11) per heading, the same shape as
        headings_deg.
    """
    headings = np.asarray(headings_deg, dtype=float)
    numbers = np.full(headings.shape, ENVIRONMENT_TABLE[-1].bf)
    holding = np.ones(headings.shape, dtype=bool)
    # BF 0 is calm and gives zero load, so it always balances.
    for condition in ENVIRONMENT_TABLE[1:]:
        fx, fy, mz = environmental_loads_level1(hull, condition.bf, headings)
        for i in np.ndindex(headings.shape):
            if holding[i] and not allocate_thrust(thrusters, (fx[i], fy[i], mz[i])).feasible:
                numbers[i] = condition.bf - 1
                holding[i] = False
        if not holding.any():
            break
    return numbers


def limiting_wind_speed_level1(numbers):
    """
    Limiting wind speed [m/s] for DP capability level 1, for the m/s
    capability plot of DNV-ST-0111 [2.4.2]: the Table 2-1 wind speed of each
    DP capability number.

    Level 1 only defines the environment at the Table 2-1 rows, so the
    limiting wind speed steps with the number rather than being interpolated
    between rows (HANDOVER.md, decisions).

    Parameters
    ----------
    numbers : int or array-like of int
        DP capability numbers, 0-11, e.g. from capability_numbers_level1().
        Anything else raises ValueError.

    Returns
    -------
    numpy.ndarray of float
        Wind speed [m/s], the same shape as numbers.
    """
    return np.vectorize(lambda bf: environment(bf).wind_speed, otypes=[float])(numbers)
