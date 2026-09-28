# Thrust — DP capability Level 1

This document explains `nominal_thrust(...)`, `effective_thrust(...)`,
`ventilation_loss_factor(...)` and `thrust_loss_factor_level1(...)` in
`thrust.py` and maps DNV-ST-0111 (Edition December 2021) [3.9.1]–[3.9.5] to
the code. The formulas and Tables 3-1 to 3-4 below were transcribed from
300 dpi renders of the PDF (pages 29–33) and checked against them.

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
  - The default is β_misc alone.
  - For Level 1, β_T = β_misc · β_vent from `thrust_loss_factor_level1` (§6) is passed in as `beta_t`. `capability_numbers_level1` does this per condition and heading.

## 6. Ventilation loss [3.9.4] and total thrust loss factor [3.9.5]

A propeller close to the free surface can draw in air (ventilation, or
aeration, p. 12), which costs a large part of its thrust. [3.9.4] gives the
loss as a probability: the chance that the relative vertical motion between
the actuator and the sea surface stays small enough for the propeller to
stay submerged. The formulation is new in the December 2021 edition. The change
log (p. 3) says it now accounts for the **propeller load** and is valid for
propellers close to the surface, e.g. in ballast.

### Formulas (PDF p. 32–33, images)

```
β_vent = Φ(k_V1 · 2ξ/D − k_V2 · σ)
σ      = 0.25 · (A · Hs · min(T0, 1) + max(PropellerLoadFactor − 1, 0))
A      = k_V4 · B · C
B      = 1 + k_V5 · |dir|/π                 for dir ∈ [−π/2, π/2]
         (1 + k_V5) − k_V5 · |dir|/π        for dir ∈ [−π, −π/2] ∪ [π/2, π]
C      = 1                                  for x ≥ 0
         1 + 0.4 · x/Lpp                    for x ≤ 0
T0     = 0.64 · √Lpp / Tz
PropellerLoadFactor = √PropellerLoad / k_V3
PropellerLoad       = |T_Nominal| / D³      (T_Nominal in N, D in m)

β_T    = β_misc · β_vent                                    [3.9.5]
```

| Symbol | Meaning |
|---|---|
| Φ | standard normal distribution function (mean 0, standard deviation 1) |
| ξ | draft − actuator z: the submergence of the actuator centre ([3.8.3]), positive under water; ξ = 0 is the centre at the waterline |
| D | propeller diameter [m] |
| σ | standard deviation of the relative vertical motion between the actuator and the free surface |
| Hs, Tz | significant wave height [m] and zero-up-crossing period [s]; Tz = Tp / 1.4049 ([3.3.3], `standard.TZ_FROM_TP`) |
| x | the thruster's x position ([2.8.2], from Lpp/2) |
| dir | the direction the waves come from |
| T_Nominal | actuator nominal thrust, "thrust before losses" [N] |
| k_V1 … k_V5 | 2, 1.5, 15.2, 0.85, 0.38 (`standard.K_V1` …) |

What the terms do:
- **2ξ/D** is the submergence in propeller radii. k_V1 · 2ξ/D is how far the propeller is from the surface, and k_V2 · σ how much the surface moves.
- **B** is 1 in head and following seas and 1 + k_V5/2 = 1.19 in beam seas, linear in between.
- **C** is 1 forward of midships and falls to 0.8 at the aft perpendicular (x = −Lpp/2).
- **min(T0, 1)** reduces the motion in long waves (Tz > 0.64·√Lpp).
- **The propeller load term** is there even in calm water. A heavily loaded propeller (large T/D³) draws the surface down, and that counts as extra relative motion.

### Decisions

1. **T_Nominal is the [3.9.2] nominal thrust** (agreed with William, 2026-09-28). [3.9.2] uses the same symbol and defines it as "thrust with no wind, waves or current", not the thrust the allocation asks for.
   - It is taken in the direction used: the reversed nominal thrust for a reverse capacity row. Only shaft lines differ; tunnels are equal both ways, and azimuths only use forward.
   - So β_vent depends on the thruster, the condition and the heading, but not on the allocation, and the LPs of `thruster_allocation.py` stay linear.
2. **The second range of B is a union.** The PDF writes `[−π, −π/2] ∩ [π/2, π]`, whose intersection is empty. The two branches meet at |dir| = π/2 with the same value (1.19), so which branch owns that point doesn't matter.
3. **Every actuator kind is included, tunnels too.** [3.9.4] excludes none.
4. **Units: T_Nominal in N.** The PDF writes "T_Nominal[N]". With kN, the factor could never exceed 1 for a real thruster, and the propeller-load term the change log mentions would do nothing. With N a typical DP thruster has a factor of about 8.

|dir| over [−π, π] is exactly the `fold_direction` of the other Level 1
formulas, applied to the direction wrapped to [0, 2π).

### Checks

- **Centre at the waterline in calm water with a light propeller:** ξ = 0, σ = 0, so β_vent = Φ(0) = 0.5.
- **Deep:** β_vent → 1. **Above the surface** (ξ < 0): β_vent < 0.5.
- **Port/starboard:** only |dir| enters, so 90° and 270° give the same loss.
- **Continuity:** B = 1.19 from both branches at π/2; C = 1 from both sides at x = 0; min(T0, 1) is continuous.
- **Reversed thrust** has a lower T_Nominal (η2 < 1), so a lower propeller load and less ventilation.
- **More power at the same diameter ventilates more.** The factor grows as P^(1/3). `tests/models/test_capability.py` shows this: the test PSV at 10× power has β_vent ≈ 0.001 at BF 11.

### Worked example (the test vessel, `config.HULL` and `config.THRUSTERS`)

| Thruster | T_Nominal [kN] | D [m] | Factor | ξ [m] | ξ/D | C |
|---|---|---|---|---|---|---|
| AZ1, AZ2 (x = −40, z = 1.8) | 377.52 | 3.0 | 7.779 | 4.2 | 1.40 | 0.8 |
| BT1 (x = +31, z = 2.5) | 135.77 | 2.0 | 8.571 | 3.5 | 1.75 | 1 |
| BT2 (x = +28, z = 2.5) | 126.89 | 2.0 | 8.285 | 3.5 | 1.75 | 1 |

"Factor" is PropellerLoadFactor. β_vent at BF 6 (Hs 3.1 m, Tp 8.5 s, Tz 6.05 s,
T0 = 0.946) and BF 11 (Hs 12.1 m, Tp 12.0 s, Tz 8.54 s, T0 = 0.670):

| Thruster | BF 6, 0° | BF 6, 90° | BF 11, 0° | BF 11, 90° |
|---|---|---|---|---|
| AZ1, AZ2 | 0.9896 | 0.9849 | 0.8389 | 0.7248 |
| BT1 | 0.9994 | 0.9989 | 0.9425 | 0.8611 |
| BT2 | 0.9996 | 0.9992 | 0.9538 | 0.8834 |

By hand for AZ1, BF 6, beam:
- A = 0.85 · 1.19 · 0.8 = 0.8092;
- σ = 0.25 · (0.8092 · 3.1 · 0.9461 + (7.779 − 1)) = 0.25 · (2.3734 + 6.779) = 2.2881;
- β_vent = Φ(2 · 2 · 4.2/3 − 1.5 · 2.2881) = Φ(5.6 − 3.4322) = Φ(2.1678) = 0.9849.

The aft azimuths lose more than the tunnels, despite C = 0.8, because they
sit higher relative to their diameter (ξ/D = 1.4 against 1.75). Up to BF 6 the
loss is at most about 1.5%; at BF 11 in beam seas it is 28% for the azimuths.

### In the code

- `K_V1` … `K_V5` in `dp_capability/standard.py`.
- `_propeller_load_factor(t_nominal, diameter)` and `_relative_motion_std(hull, x, hs, tz, direction_rad, propeller_load_factor)` in `thrust.py`, one formula each.
  - `_relative_motion_std` sets the wave term to 0 where `hs == 0`, so BF 0's `tp = nan` gives no nan, as in `wave_loads_level1`.
- `ventilation_loss_factor(thruster, hull, hs, tp, direction_deg, reverse=False)` returns β_vent, vectorized over direction. It takes Tp, like `wave_loads_level1`, and converts to Tz itself. Φ is `scipy.stats.norm.cdf`.
- `thrust_loss_factor_level1(...)` returns β_misc · β_vent: the part of the [3.11.6] total that doesn't depend on the thrust direction.
  - The skeg factor β_T,flushing skeg does depend on it, so `allocate_thrust` applies it to the capacity polygon (`skeg_loss.md`).
  - β_T,flushing dead only exists in failure cases (step 8).
