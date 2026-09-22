"""
Vessel parameters and run settings.

HULL describes a made-up ~80 m offshore supply vessel used while developing
and testing the code. It is not a real vessel: the numbers are round and
consistent with each other so results are easy to check by hand, and the same
vessel can be entered in DNV's Veracity DP capability app for comparison.
"""
import math

from dp_capability.vessel import Hull

HULL = Hull(
    loa=88.0,
    lpp=80.0,
    draft=6.0,
    breadth=18.0,
    # Under water the hull reaches from x = -44 m (thrusters) to x = +42 m (bulb).
    los=86.0,
    x_los=-1.0,
    # The waterline ends at x = 40 m and is B/4 = 4.5 m wide at x = 30 m.
    bow_angle=math.atan(4.5 / (40.0 - 30.0)),
    # Gives C_WLaft = 648 / (40 * 18) = 0.90, inside the [0.85, 1.15] range of [3.7].
    aw_laft=648.0,
    # Superstructure is forward, so the side area centre is forward of midships.
    af_wind=280.0,
    al_wind=700.0,
    xl_air=12.0,
    af_current=100.0,
    al_current=490.0,
    xl_current=-1.5,
    skegs=((-36.0, 0.0),),
)
