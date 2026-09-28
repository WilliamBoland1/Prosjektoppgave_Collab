import numpy as np

from dp_capability.models.environmental_loads import environmental_loads_level1
from dp_capability.models.thrust import thrust_loss_factor_level1
from dp_capability.models.thruster_allocation import allocate_thrust
from dp_capability.standard import BETA_MISC, ENVIRONMENT_TABLE, environment


def _loss_factors(hull, thrusters, condition, headings, ventilation=True):
    """
    Thrust loss factor beta_T ([3.9.5]) of every thruster in one Table 2-1
    condition, with shape (thrusters, 2, *headings.shape): index 0 of the
    second axis is forward thrust, 1 reversed. Without ventilation it is
    beta_misc throughout.
    """
    headings = np.asarray(headings, dtype=float)
    if not ventilation:
        return np.full((len(thrusters), 2) + headings.shape, BETA_MISC)
    return np.array([
        [thrust_loss_factor_level1(t, hull, condition.hs, condition.tp, headings, reverse)
         for reverse in (False, True)]
        for t in thrusters
    ])


def capability_numbers_level1(hull, thrusters, headings_deg, ventilation=True, forbidden_zones=True, skeg_loss=True):
    """
    DP capability number per heading for DP capability level 1, DNV-ST-0111
    [2.2.2], [2.4.4] and [3.2.2].

    For each heading the Table 2-1 conditions are balanced from the lowest
    one upwards ([2.4.4]): the factored load of environmental_loads_level1()
    against allocate_thrust(). The number is the last condition before the
    first one that cannot be balanced, so the vessel also holds in every
    condition below it ([2.2.2]). Later conditions are not tried after the
    first failure. 11 if all balance, 0 if BF 1 already fails.

    Each thruster's effective thrust includes the ventilation loss of the
    condition and heading, beta_T = beta_misc * beta_vent ([3.9.5]); the
    allocation respects the forbidden zones of [3.11.2]-[3.11.3] and the
    direction-dependent skeg loss of [3.11.5] (together beta_T of [3.11.6]).

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
    ventilation : bool, optional
        False leaves out the ventilation loss (beta_T = beta_misc), e.g. to
        see its effect. Level 1 includes it.
    forbidden_zones : bool, optional
        False ignores the forbidden zones in the allocation, e.g. to see
        their effect. Level 1 includes them.
    skeg_loss : bool, optional
        False leaves out the skeg loss of hull.skegs. Level 1 includes it.

    Returns
    -------
    numpy.ndarray of int
        DP capability number (0-11) per heading, the same shape as
        headings_deg.
    """
    headings = np.asarray(headings_deg, dtype=float)
    numbers = np.full(headings.shape, ENVIRONMENT_TABLE[-1].bf)
    holding = np.ones(headings.shape, dtype=bool)
    skegs = hull.skegs if skeg_loss else ()
    # BF 0 is calm and gives zero load, so it always balances.
    for condition in ENVIRONMENT_TABLE[1:]:
        fx, fy, mz = environmental_loads_level1(hull, condition.bf, headings)
        beta_t = _loss_factors(hull, thrusters, condition, headings, ventilation)
        for i in np.ndindex(headings.shape):
            if holding[i] and not allocate_thrust(
                thrusters, (fx[i], fy[i], mz[i]), beta_t=beta_t[(..., *i)],
                forbidden_zones=forbidden_zones, skegs=skegs,
            ).feasible:
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
