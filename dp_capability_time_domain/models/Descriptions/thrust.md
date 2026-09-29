# Thrust — DP capability Level 1

This document explains `nominal_thrust(...)` and `effective_thrust(...)` in
`thrust.py` and maps DNV-ST-0111 (Edition December 2021) [3.9.1]–[3.9.3] to
the code. The formula and Tables 3-1 to 3-4 below were transcribed from
300 dpi renders of the PDF (pages 29–32) and checked against them.

## 1. Background

The environmental load of [3.5]–[3.7] has to be balanced by the actuators.
[3.9] gives how much thrust each actuator can deliver. Like the loads, it is
prescriptive: a fixed formula with coefficients read from tables by actuator
type. There is no manufacturer data, except for types the section does not
cover, such as water jets ([3.8.1]).

The thrust direction and position conventions are in [3.8]:
- **Actuator angle ([3.8.2]):** 0° when the actuator pushes forward along x, increasing counter-clockwise, so 90° pushes to port.
- **Position ([3.8.3]):**
  - tunnel thrusters: the volume centre of the tunnel;
  - azimuths: the intersection of the propeller shaft and the azimuthing axis;
  - shaft propellers: the hub centre, or the rudder stock/propeller axis intersection when there is a rudder;
  - cycloidals: the centre of the rotation mechanism, halfway down the blades.

Positions are in the [2.8.2] frame, like the hull data.

## 2. Formulas

```
T_Effective = T_Nominal · β_T                        [3.9.1]
T_Nominal   = η1 · η2 · (D · P)^(2/3)     [N]        [3.9.2]
P           = P_B · η_M                   [kW]
β_misc      = 0.9                                    [3.9.3]
```

- `D` is the propeller diameter in **m** and `P` the power applied to the propeller in **kW**; with these units the formula gives newtons.
- `P_B` is the MCR brake power available in DP mode/bollard pull, taking power and torque limitations into account. The limitations relevant in DP mode shall be documented.
  - Guidance note 3: for dedicated DP actuators, CPP propellers and cycloidals the torque limitation need not be documented.
  - For other actuators without documented torque limits, 50% of MCR may be accepted as `P_B`.
- `D` has special definitions:
  - permanent magnet tunnel thrusters: the diameter of the blade tip circle (guidance note 1);
  - contra-rotating propellers, and pods with a propeller at each end of the pod house: the largest propeller;
  - cycloidals: `√(blade length · diameter of blade pivot points)`.

  Propellers close to each other count as a contra-rotating unit. Pods with a propeller on each side of the pod house do not (guidance note 2).

### Table 3-1: η1

| Type of actuator | η1 |
|---|---|
| Azimuths, pods and shaft line propellers | 800 |
| Cycloidal actuators | 900 |
| Tunnel thrusters | 900 |
| Contra-rotating azimuths, pods and shaft line propellers | 950 |
| Ducted azimuths, pods and shaft line propellers | 1200 |

### Table 3-2: η2 for tunnel thrusters

| Inlet shape | η2 |
|---|---|
| Broken inlets with α ∈ [20, 50] deg and b > 0.1D | 1.0 |
| Rounded inlet with r > 0.05D | 1.07 |
| All other inlet shapes | 0.93 |

The symbols come from Figure 3-4:
- `α`: the angle between the tunnel wall and the cone;
- `b`: the smallest breadth of the cone;
- `r`: the smallest radius of the rounding.

### Table 3-3: η2 for actuators other than tunnel thrusters

| Thrust direction and type of actuator | η2 |
|---|---|
| Forward thrust | 1.0 |
| Reversed thrust from FPP propellers without duct | 0.9 |
| Reversed thrust from FPP propellers with duct | 0.7 |
| Reversed thrust from CPP propellers without duct | 0.65 |
| Reversed thrust from CPP propellers with duct | 0.5 |

The guidance note to Table 3-3 says:
- For FPP, reversed thrust means the propeller turning opposite to its design direction.
- Contra-rotating actuators typically have FPP propellers and no duct.
- Cycloidals are typically not reversed, so η2 = 1.0.

### Table 3-4: mechanical efficiency η_M

| Type of actuator | η_M |
|---|---|
| Cycloidal actuators | 0.91 |
| Permanent magnet cycloidal actuators | 0.97 |
| Tunnel and azimuth thrusters | 0.93 |
| Rim-driven permanent magnet actuators | 0.995 |
| Shaft line propellers | 0.97 |
| Pods | 0.98 |

## 3. Choosing the table row

The tables don't cover every combination of the Table A-3 inputs, so the code
picks rows by these rules:

1. **η1:**
   - Tunnels and cycloidals have their own rows, so the ducted and contra-rotating flags are ignored for them.
   - Azimuths, pods and shaft lines use the ducted row if ducted, the contra-rotating row if contra-rotating, and otherwise the 800 row.
   - Ducted *and* contra-rotating has no row, so it raises `ValueError`.
2. **η2:**
   - Tunnels use Table 3-2 by inlet shape, the same in both directions (the table does not depend on direction).
   - A tunnel without an inlet shape raises `ValueError`. It does not fall back to "all other inlet shapes".
   - Cycloidals get 1.0 both ways.
   - All others get 1.0 forward and the Table 3-3 row for their pitch and duct in reverse.
3. **η_M:**
   - A permanent magnet cycloidal gets 0.97.
   - Table A-3 only asks whether an actuator is a permanent magnet thruster, not whether it is rim-driven. Any other permanent magnet actuator therefore gets the rim-driven row, 0.995. Guidance note 1's blade tip circle also describes a rim-driven unit.
   - Everything else uses its own row.
4. **Water jets** raise `ValueError`. They are not in the tables, and [3.8.1] asks for manufacturer data.
5. **The 50%-of-MCR rule is not applied in the code.** `power_kw` is the `P_B` the user documents, and whoever enters the data decides which case applies.

## 4. Checks

- Nominal thrust grows as `(D·P_B)^(2/3)`: doubling `D` and multiplying `P_B` by 4 gives 8× `D·P` and so 4× the thrust.
- Reversed thrust is never more than forward thrust. It is equal for tunnels and cycloidals, and 0.5–0.9 of it for the rest.
- Ducted propellers get 1.5× the thrust of open ones at the same power (1200 against 800). In reverse, part of that is lost again (0.7 against 0.9 for FPP).

### Worked example (the test vessel, `config.THRUSTERS`)

| Thruster | η1 | η2 fwd / rev | η_M | P [kW] | D·P | (D·P)^(2/3) | T_Nominal fwd / rev [kN] | T_Effective fwd [kN] |
|---|---|---|---|---|---|---|---|---|
| AZ1, AZ2: ducted FPP azimuth, D 3.0, 2000 kW | 1200 | 1.0 / 0.7 | 0.93 | 1860 | 5580 | 314.598 | 377.52 / 264.26 | 339.77 |
| BT1: tunnel, rounded inlet, D 2.0, 900 kW | 900 | 1.07 / 1.07 | 0.93 | 837 | 1674 | 140.984 | 135.77 / 135.77 | 122.19 |
| BT2: tunnel, broken inlet, D 2.0, 900 kW | 900 | 1.0 / 1.0 | 0.93 | 837 | 1674 | 140.984 | 126.89 / 126.89 | 114.20 |
| RAZ: open FPP azimuth, D 1.8, 800 kW | 800 | 1.0 / 0.9 | 0.93 | 744 | 1339.2 | 121.496 | 97.20 / 87.48 | 87.48 |

The T_Nominal column is what Table A-3 reports as "Nominal thrust [kN]". It is
the number to compare with DNV's Veracity app. `tests/models/test_thrust.py`
checks the formula with its own thrusters. For example, the ducted azimuth
case there has the same data as AZ1.

## 5. In the code

- `Thruster` in `dp_capability/vessel.py` holds the Table A-3 inputs.
  - `kind` is one of `"azimuth"`, `"pod"`, `"shaft_line"`, `"tunnel"`, `"cycloidal"`, `"water_jet"`.
  - `pitch` is `"FPP"` or `"CPP"`, and `tunnel_inlet` is `"broken"`, `"rounded"` or `"other"`.
  - `power_kw` is the one field not in SI units, because the formula wants kW.
- The table values live in `dp_capability/standard.py`, one dict per table: `ETA1`, `ETA2_TUNNEL`, `ETA2_FORWARD` and `ETA2_REVERSED` (keyed by `(pitch, ducted)`), `ETA_M` and `BETA_MISC`.
- `_eta1`, `_eta2` and `_eta_m` in `thrust.py` pick the row by the rules of §3.
- `nominal_thrust(thruster, reverse=False)` returns newtons.
- `effective_thrust(thruster, reverse=False, beta_t=BETA_MISC)` multiplies the nominal thrust by β_T.
  - For now β_T is just β_misc.
  - [3.9.5] defines β_T = β_misc · β_vent. The ventilation loss of [3.9.4] depends on the waves and on the actuator's submergence `ξ = draft − z`, and will be passed in through `beta_t` when it is added.
