"""
Vessel parameters and run settings.

HULL describes a made-up ~80 m offshore supply vessel used while developing
and testing the code. It is not a real vessel: the numbers are round and
consistent with each other so results are easy to check by hand, and the same
vessel can be entered in DNV's Veracity DP capability app for comparison.
"""
import math

from dp_capability.vessel import Hull, PowerSource, RedundancyGroup, Thruster

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

# Two azimuths aft and two bow tunnels. Only azimuths and tunnels, because
# those are the kinds available for testing in DNV's Veracity app. power_kw is
# the documented DP power with torque limits, so the 50%-of-MCR fallback of
# [3.9.2] guidance note 3 does not apply. The two tunnels have different
# inlets, so that a comparison with Table A-3 in Veracity covers two rows of
# Table 3-2. power_supply is the thruster's row of Table A-5 (POWER_SOURCES below).
THRUSTERS = (
    Thruster("AZ1", "azimuth", diameter=3.0, power_kw=2000.0, x=-40.0, y=5.5, z=1.8, ducted=True,
             power_supply=(("SWBD 1", 1.0),)),
    Thruster("AZ2", "azimuth", diameter=3.0, power_kw=2000.0, x=-40.0, y=-5.5, z=1.8, ducted=True,
             power_supply=(("SWBD 2", 1.0),)),
    Thruster("BT1", "tunnel", diameter=2.0, power_kw=900.0, x=31.0, y=0.0, z=2.5, pitch="CPP", tunnel_inlet="rounded",
             power_supply=(("SWBD 1", 1.0),)),
    Thruster("BT2", "tunnel", diameter=2.0, power_kw=900.0, x=28.0, y=0.0, z=2.5, pitch="CPP", tunnel_inlet="broken",
             power_supply=(("SWBD 2", 1.0),)),
)

# DP operating mode ([3.12.1]): two switchboards with the bus-tie open, each
# with 2 x 1800 kW gen-sets running. 90% of 3600 kW = 3240 kW is usable
# ([3.12.3]), more than the 2000 + 900 = 2900 kW of thrusters on each, so
# power never limits the intact vessel.
POWER_SOURCES = (
    PowerSource("SWBD 1", available_kw=3600.0),
    PowerSource("SWBD 2", available_kw=3600.0),
)

# Redundancy groups, as a DP FMEA would give them ([2.4.8]): with the bus-tie
# open, losing a switchboard loses its gen-sets and the two thrusters on it.
# The vessel is taken to be redundant, so C and D of DP capability-L1(A, B,
# C, D) apply ([2.5.2]).
REDUNDANCY_GROUPS = (
    RedundancyGroup("SWBD 1", thrusters=("AZ1", "BT1"), power_sources=("SWBD 1",)),
    RedundancyGroup("SWBD 2", thrusters=("AZ2", "BT2"), power_sources=("SWBD 2",)),
)

# Environment directions of the capability plot [deg]. [2.4.6] asks for at
# least 10 deg resolution over the full 360 deg.
HEADINGS_DEG = tuple(range(0, 360, 10))
