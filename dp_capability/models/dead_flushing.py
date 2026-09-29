import math

import numpy as np

# The loss applies closer than this many diameters of the flushing thruster
# to a dead thruster, [3.11.4].
DEAD_FLUSHING_DISTANCE_D_OPEN = 8.0
DEAD_FLUSHING_DISTANCE_D_DUCTED = 4.0


def dead_flushing_loss(thruster, dead):
    """
    Where and how much a working thruster loses by flushing one dead thruster,
    DNV-ST-0111 [3.11.4]:

        phi  = arctan(0.6 * D / s)    open propeller
               arctan(0.35 * D / s)   ducted propeller
        beta = 1 - 1 / (0.02 * (s/D)^2 + 0.25 * s/D + 1.2)

    D is the diameter of the flushing (working) thruster and s the horizontal
    distance between the two. The sector of half-width phi is centred on the
    vector from the dead thruster to the flushing one: thrust that way sends
    the race onto the dead thruster, as in [3.11.3]. beta is the factor
    there. A dead tunnel thruster may be flushed, and the loss only applies
    closer than 8 D (open) or 4 D (ducted).

    Parameters
    ----------
    thruster : dp_capability.vessel.Thruster
        The working, flushing thruster.
    dead : dp_capability.vessel.Thruster
        The dead thruster.

    Returns
    -------
    (float, float, float) or None
        (centre, phi) as thrust angles [deg] in the [3.8.2] convention, and
        beta at the centre. None if the loss does not apply.
    """
    if dead.kind == "tunnel":
        return None
    dx, dy = thruster.x - dead.x, thruster.y - dead.y
    s = math.hypot(dx, dy)
    if s == 0.0:
        raise ValueError(f"{thruster.name} and {dead.name} are at the same horizontal position")
    d = thruster.diameter
    reach = DEAD_FLUSHING_DISTANCE_D_DUCTED if thruster.ducted else DEAD_FLUSHING_DISTANCE_D_OPEN
    if s >= reach * d:
        return None
    phi = math.atan((0.35 if thruster.ducted else 0.6) * d / s)
    beta = 1.0 - 1.0 / (0.02 * (s / d) ** 2 + 0.25 * s / d + 1.2)
    return math.degrees(math.atan2(dy, dx)), math.degrees(phi), beta


def dead_flushing_factor(thruster, dead_thrusters, angle_deg):
    """
    Thrust loss factor beta_T,flushing dead of DNV-ST-0111 [3.11.4] at the
    given thrust angles ([3.8.2]: 0 deg forward, counter-clockwise).

    Figure 3-6: between the sector centre (beta) and the sector edges (1) the
    capacity is linear in Cartesian coordinates, a straight line from
    beta * (cos c, sin c) to (cos(c +- phi), sin(c +- phi)). Along the ray at
    |angle - c| = delta that line is at the radius

        beta * sin(phi) / (sin(phi - delta) + beta * sin(delta))

    With several dead thrusters the lowest factor counts, as for skegs
    (HANDOVER.md, decisions).

    Parameters
    ----------
    thruster : dp_capability.vessel.Thruster
        The working, flushing thruster.
    dead_thrusters : sequence of dp_capability.vessel.Thruster
    angle_deg : float or array-like
        Thrust angles [deg].

    Returns
    -------
    numpy.ndarray
        The factor, between 0 and 1, the shape of angle_deg. 1 outside every
        sector.
    """
    angle = np.asarray(angle_deg, dtype=float)
    factor = np.ones_like(angle)
    for dead in dead_thrusters:
        loss = dead_flushing_loss(thruster, dead)
        if loss is None:
            continue
        centre, phi, beta = loss
        delta = np.deg2rad(np.abs((angle - centre + 180.0) % 360.0 - 180.0))
        phi = math.radians(phi)
        inside = delta < phi
        delta = np.where(inside, delta, 0.0)
        radius = beta * math.sin(phi) / (np.sin(phi - delta) + beta * np.sin(delta))
        factor = np.minimum(factor, np.where(inside, radius, 1.0))
    return factor


def dead_flushing_breakpoints(thruster, dead):
    """
    The sector edges and centre of dead_flushing_loss() as (angles [deg],
    factors), increasing in angle, for the corners of the capacity polygon.
    The angles may lie below 0 or above 360 deg. None if the loss does not
    apply.
    """
    loss = dead_flushing_loss(thruster, dead)
    if loss is None:
        return None
    centre, phi, beta = loss
    return np.array([centre - phi, centre, centre + phi]), np.array([1.0, beta, 1.0])
