"""
Values and conventions fixed by DNV-ST-0111 (Edition December 2021) that are
the same for every vessel.

Coordinate system (DNV-ST-0111 [2.8.2])
---------------------------------------
- Body axes: right-handed, x forward, y to port, z upwards. Origin at Lpp/2,
  on the centreline, at the keel.
- Forces are positive pushing the vessel forward (surge) and to port (sway).
  The yaw moment is positive counter-clockwise seen from above (bow to port).
- Environmental directions are the direction the wind, current or waves are
  coming FROM, measured clockwise: 0 deg = head-on, 90 deg = from starboard,
  180 deg = from astern, 270 deg = from port.

Public functions take directions in degrees, like the report does ([2.8.3]).
The formulas in the standard use radians, so the conversion happens inside
each function.
"""
from dataclasses import dataclass
import math

import numpy as np

RHO_AIR = 1.226  # kg/m^3, DNV-ST-0111 [3.5]
RHO_WATER = 1026.0  # kg/m^3, DNV-ST-0111 [3.6]
# m/s^2, used in the wave drift formulas [3.7]. The standard does not fix a
# value for g; this is our choice (HANDOVER.md, open decisions).
G = 9.81
TZ_FROM_TP = 1.4049  # Tp = 1.4049 * Tz for Pierson-Moskowitz with cos^2 spreading, [3.3.3]
DYNAMIC_FACTOR_LEVEL1 = 1.25  # applied to wind, current and wave loads, [3.2.2]

# Efficiency factors for the nominal thrust formula of [3.9.2]. Which row
# applies to a given thruster is decided in dp_capability/models/thrust.py.
ETA1 = {  # Table 3-1
    "propeller": 800.0,  # azimuths, pods and shaft line propellers
    "cycloidal": 900.0,  # cycloidal actuators
    "tunnel": 900.0,  # tunnel thrusters
    "contra_rotating": 950.0,  # contra-rotating azimuths, pods and shaft line propellers
    "ducted": 1200.0,  # ducted azimuths, pods and shaft line propellers
}
ETA2_TUNNEL = {  # Table 3-2, tunnel thrusters, by inlet shape (Figure 3-4)
    "broken": 1.0,  # broken inlets with alpha in [20, 50] deg and b > 0.1D
    "rounded": 1.07,  # rounded inlet with r > 0.05D
    "other": 0.93,  # all other inlet shapes
}
ETA2_FORWARD = 1.0  # Table 3-3, forward thrust
ETA2_REVERSED = {  # Table 3-3, reversed thrust, keyed by (pitch, ducted)
    ("FPP", False): 0.9,
    ("FPP", True): 0.7,
    ("CPP", False): 0.65,
    ("CPP", True): 0.5,
}
ETA_M = {  # Table 3-4, mechanical efficiency
    "cycloidal": 0.91,  # cycloidal actuators
    "pm_cycloidal": 0.97,  # permanent magnet cycloidal actuators
    "tunnel": 0.93,  # tunnel and azimuth thrusters
    "azimuth": 0.93,
    "rim_driven_pm": 0.995,  # rim-driven permanent magnet actuators
    "shaft_line": 0.97,  # shaft line propellers
    "pod": 0.98,  # pods
}
BETA_MISC = 0.9  # constant 10% thrust loss, [3.9.3]


@dataclass(frozen=True)
class BeaufortCondition:
    """One row of DNV-ST-0111 Table 2-1: the environment for one DP capability number."""

    bf: int  # Beaufort number, equal to the DP capability number (0-11)
    description: str
    wind_speed: float  # upper limit of the mean wind speed 10 m above sea level [m/s]
    hs: float  # significant wave height [m]
    tp: float  # peak wave period [s]; nan for BF 0, which the table gives as NA
    current_speed: float  # [m/s]


# DNV-ST-0111 Table 2-1. BF 12 (hurricane force) has no DP capability number
# and is therefore left out.
ENVIRONMENT_TABLE = (
    BeaufortCondition(0, "Calm", 0.0, 0.0, math.nan, 0.0),
    BeaufortCondition(1, "Light air", 1.5, 0.1, 3.5, 0.25),
    BeaufortCondition(2, "Light breeze", 3.4, 0.4, 4.5, 0.50),
    BeaufortCondition(3, "Gentle breeze", 5.4, 0.8, 5.5, 0.75),
    BeaufortCondition(4, "Moderate breeze", 7.9, 1.3, 6.5, 0.75),
    BeaufortCondition(5, "Fresh breeze", 10.7, 2.1, 7.5, 0.75),
    BeaufortCondition(6, "Strong breeze", 13.8, 3.1, 8.5, 0.75),
    BeaufortCondition(7, "Moderate gale", 17.1, 4.2, 9.0, 0.75),
    BeaufortCondition(8, "Gale", 20.7, 5.7, 10.0, 0.75),
    BeaufortCondition(9, "Strong gale", 24.4, 7.4, 10.5, 0.75),
    BeaufortCondition(10, "Storm", 28.4, 9.5, 11.5, 0.75),
    BeaufortCondition(11, "Violent storm", 32.6, 12.1, 12.0, 0.75),
)


def environment(bf):
    """
    Return the Table 2-1 environment for DP capability number `bf` (0-11).

    Raises ValueError for anything outside 0-11, including BF 12, which has
    no DP capability number.
    """
    if bf not in range(len(ENVIRONMENT_TABLE)):
        raise ValueError(f"DP capability number must be an integer 0-11, got {bf!r}")
    return ENVIRONMENT_TABLE[bf]


def fold_direction(direction_rad):
    """
    The `dir` term used in the wind, current and wave formulas ([3.5]-[3.7]).

    Folds a direction in [0, 2*pi] onto [0, pi], so a direction from port
    gets the same value as the mirrored direction from starboard:
        dir = direction            for 0 <= direction <= pi
        dir = 2*pi - direction     for pi <= direction <= 2*pi
    """
    direction = np.asarray(direction_rad, dtype=float)
    return np.where(direction <= np.pi, direction, 2 * np.pi - direction)
