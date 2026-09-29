import numpy as np

from dp_capability.models.environmental_loads import environmental_loads_level1
from dp_capability.models.redundancy import failure_case
from dp_capability.models.thrust import thrust_loss_factor_level1
from dp_capability.models.thruster_allocation import allocate_thrust
from dp_capability.standard import BETA_MISC, BOW_SECTOR_DEG, ENVIRONMENT_TABLE, environment


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


def capability_numbers_level1(hull, thrusters, headings_deg, ventilation=True, forbidden_zones=True, skeg_loss=True,
                              power_sources=None, dead_thrusters=()):
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
    direction-dependent skeg loss of [3.11.5] and, in a failure run, the
    loss from flushing dead thrusters of [3.11.4] (together beta_T of
    [3.11.6]). With power sources, no source may give more than its usable
    power ([2.4.9], [3.12]).

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
    power_sources : sequence of dp_capability.vessel.PowerSource, optional
        The switchboards and prime movers of the operating mode, see
        allocate_thrust(). None: no power limit.
    dead_thrusters : sequence of dp_capability.vessel.Thruster, optional
        The thrusters lost in a failure run, for the dead flushing loss of
        [3.11.4]. Empty for the intact vessel.

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
                forbidden_zones=forbidden_zones, skegs=skegs, power_sources=power_sources,
                dead_thrusters=dead_thrusters,
            ).feasible:
                numbers[i] = condition.bf - 1
                holding[i] = False
        if not holding.any():
            break
    return numbers


def failure_numbers_level1(hull, thrusters, headings_deg, groups, power_sources=None, dead_flushing=True, **options):
    """
    DP capability numbers after the loss of each redundancy group,
    DNV-ST-0111 [2.4.8] and [2.5.4]: capability_numbers_level1() on what
    failure_case() leaves of the vessel.

    The group's thrusters are dead: they no longer cause flushing sectors
    ([3.11.3]), and working thrusters that flush them lose thrust instead
    ([3.11.4]). A failure number can therefore be higher than the intact one
    at some heading. A thruster that only lost part of its power supply is
    still working.

    Parameters
    ----------
    hull, thrusters, headings_deg, power_sources
        The intact vessel, as for capability_numbers_level1().
    groups : sequence of dp_capability.vessel.RedundancyGroup
        The redundancy groups of the DP FMEA, one failure run each.
    dead_flushing : bool, optional
        False leaves out the dead flushing loss of [3.11.4], e.g. to see its
        effect. Level 1 includes it.
    **options
        ventilation, forbidden_zones and skeg_loss, passed on to
        capability_numbers_level1().

    Returns
    -------
    dict of str to numpy.ndarray of int
        DP capability numbers per heading, keyed by group name, in the order
        of groups (A.3.6).
    """
    numbers = {}
    for group in groups:
        remaining, sources = failure_case(thrusters, group, power_sources)
        dead = [t for t in thrusters if t.name in group.thrusters] if dead_flushing else []
        numbers[group.name] = capability_numbers_level1(hull, remaining, headings_deg, power_sources=sources,
                                                        dead_thrusters=dead, **options)
    return numbers


def worst_case_numbers(numbers):
    """
    The combined (amalgamated) worst case single failure result,
    DNV-ST-0111 [2.4.7]: the lowest number per heading across all the
    redundancy groups.

    Parameters
    ----------
    numbers : iterable of array-like
        One array of DP capability numbers per redundancy group, all the
        same shape, e.g. failure_numbers_level1(...).values().

    Returns
    -------
    numpy.ndarray
        The lowest number per heading.
    """
    return np.min(np.stack([np.asarray(n) for n in numbers]), axis=0)


def information_elements_level1(headings_deg, intact, worst=None):
    """
    The information elements A, B, C and D of DP capability-L1(A, B, C, D),
    DNV-ST-0111 [2.5.1]-[2.5.4]:

        A, C = smallest number within +-30 deg of the bow
        B, D = smallest number over 0-360 deg

    A and B from the intact vessel, C and D from the worst case single
    failure. The sector includes its edges, 330 and 30 deg.

    Parameters
    ----------
    headings_deg : array-like
        Direction the environment is coming from [deg], clockwise from the bow.
    intact : array-like of int
        DP capability number per heading, intact vessel.
    worst : array-like of int, optional
        DP capability number per heading, worst case single failure
        (worst_case_numbers()). None for a non-redundant DP system, whose
        C and D are not applicable ([2.5.2]).

    Returns
    -------
    tuple
        (A, B, C, D) as ints; C and D are None without worst.
    """
    headings = np.asarray(headings_deg, dtype=float)
    off_bow = np.abs((headings + 180.0) % 360.0 - 180.0)
    bow = off_bow <= BOW_SECTOR_DEG
    if not bow.any():
        raise ValueError(f"no heading within +-{BOW_SECTOR_DEG:g} deg of the bow")

    def smallest(numbers):
        numbers = np.asarray(numbers)
        return int(numbers[bow].min()), int(numbers.min())

    a, b = smallest(intact)
    c, d = smallest(worst) if worst is not None else (None, None)
    return a, b, c, d


def capability_notation(a, b, c=None, d=None, level=1):
    """
    The DP capability numbers as DNV-ST-0111 [2.5.1] presents them,
    e.g. "DP capability-L1(8, 6, 5, 4)". C and D that are None are written
    "NA" ([2.5.2]).
    """
    elements = ", ".join("NA" if e is None else str(e) for e in (a, b, c, d))
    return f"DP capability-L{level}({elements})"


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
