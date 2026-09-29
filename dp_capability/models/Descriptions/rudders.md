# Rudders — DP capability Level 1

This document explains `rudders.py` and how `allocate_thrust(...)` uses a
rudder behind a shaft line propeller. It maps DNV-ST-0111 (Edition December
2021) [3.10] to the code. The formulas (PDF page 34) are drawn, not text. They
were transcribed from a 300 dpi render and checked with William on
2026-09-29 before any code was written. Tables 3-5 and 3-6 are also in the PDF's
text layer (`SOURCES.md`).

## 1. Background

Without a rudder, a shaft line propeller can only push along its shaft, ±x.
A rudder in the propeller race turns part of the forward thrust into side
force, so the propeller and rudder together give a 2-D force. [3.10] says:
- [3.10.1] "For a rudder behind a propeller giving positive thrust the effect of rudder shall be accounted for with the following equations."
- [3.10.2] "For a rudder behind a propeller giving negative thrust the effect of the rudder shall be neglected."
- [3.8.3] "Shaft propellers with rudder: the intersection of the rudder stock and the propeller axis." That is the position (x, y) to give the thruster, since that is where the side force acts.
- Table A-4 (p. 72) lists the rudder input: profile type, A_r, k1, k2 and the maximum rudder angle. The maximum side force is an output.

## 2. Formulas

The forces produced by the propeller and the rudder together:
```
F_Surge = T_Effective · (1 − C_x · α²)
F_Sway  = T_Effective · C_y · α
C_x     = 0.02 · C_y
C_Y     = 0.0126 · k1 · k2 · A_r / D²
```

- α is the rudder angle **in degrees**. "For rudder angle above 30 degrees values for 30 degrees shall be used."
- A_r is "the area of the movable part of the rudder directly behind the propeller. When computing this area the chord length at any position is limited to maximum 1.0D."
- T_Effective is the forward effective thrust of [3.9.1], so it includes β_misc and the ventilation loss.

**Table 3-5, rudder profile type (Figure 3-5), k1, ahead:**

| Profile type | k1 | Key in `K1_RUDDER` |
|---|---|---|
| NACA – Göttingen | 1.1 | `naca` |
| Hollow profile¹⁾ | 1.35 | `hollow` |
| Flat-sided | 1.1 | `flat_sided` |
| Profile with «fish tail» | 1.4 | `fish_tail` |
| Rudder with flap | 1.65 | `flap` |
| Nozzle rudder | 1.9 | `nozzle` |
| Mixed profiles (e.g. HSVA) | 1.21 | `mixed` |

¹⁾ Width somewhere along the length is 75% or less of a flat-sided profile with the same nose radius and a straight tangent to the aft end.

**Table 3-6, rudder/nozzle arrangement, k2:**

| Arrangement | k2 | Key in `K2_RUDDER` |
|---|---|---|
| All other arrangements | 1.0 | `other` |
| Rudder behind a fixed propeller nozzle | 1.15 | `fixed_nozzle` |

**Size of the effect.** With A_r = D² and a NACA rudder, C_y = 0.01386 and
C_x = 0.0002772. At 30° the force is (0.75052, 0.4158)·T: 42% of the thrust
sideways, for a 25% loss in surge. The force points at
atan2(0.4158, 0.75052) = 28.99° off the shaft, and its size is 0.858 T.

## 3. Decisions (agreed with William, 2026-09-29)

1. **k2 comes from an explicit flag**, `Rudder.behind_fixed_nozzle`, because Table A-4 lists k2 as its own row. It is not derived from `Thruster.ducted`: a nozzle rudder (k1 = 1.9) turns its nozzle, so k2 = 1.0 even though the propeller is ducted for Table 3-1.
2. **A_r is an input**, already computed with the chord capped at 1.0D. The code can't check the cap without the rudder's shape.
3. **The angle limit** is min(maximum rudder angle, 30°). A rudder that only turns 20° uses 20°.
4. **Sign of α:** positive α gives sway to port. The standard doesn't say, and the capacity is symmetric, so it doesn't matter for the result.
5. **The capacity is two pieces, not their convex hull.**
   - With positive thrust (0 to T) and any α in [−α_max, α_max], the forces fill a **fan**: the origin plus the curve (T(1 − C_x α²), T C_y α). That curve is a parabola, x = T − (C_x / (C_y² T))·y², bulging away from the origin, so the fan is convex.
   - With negative thrust the force is along −x only, up to T_rev ([3.10.2]).
   - The propeller gives one or the other at a time, so a force between the two (backing *and* pushing sideways) is not available. The two are separate pieces, enumerated like the zone and skeg pieces (`thruster_allocation.md` §2).
6. **The fan has corners every 1° of rudder angle** (`RUDDER_STEP_DEG`), from −α_max to +α_max. The chords lie inside the parabola, so the fan is conservative. The largest gap is tiny: the curve bends very little over 1°.
7. **Forbidden zones and the skeg loss use the shaft direction (0° / 180°)**, not the deflected force. [3.11.3] defines the thrust direction as the "vector through propeller shaft for non-cycloidal actuators". So a zone containing 0° removes the whole forward fan, and a zone at, say, 20–40° removes nothing. The fan is scaled by β_skeg(0°) and the reverse limit by β_skeg(180°), as for a shaft line without a rudder.
8. **A rudder on anything but a shaft line raises `ValueError`.**

## 4. Checks

- **Round case** (tested): A_r = D² = 4 m², NACA, T = 1000 N.
  - α = 0: (1000, 0) N, the plain thrust.
  - α = 30°: (750.52, 415.8) N, and −30° mirrors the sway.
  - α = 35° with max 35° gives the 30° values; with max 20° it gives (889.12, 277.2) N.
- **Allocation, one shaft line at the origin:**
  - A load needing half the 30° force gives u = 0.5 at 28.99°, a fan corner.
  - Pure sway, or any direction beyond 28.99°, gives u = ∞.
  - Backing with a side force gives u = ∞ ([3.10.2]). Pure backing gives u = 0.5 for 0.45 T, as without a rudder.
- **Sign check:** a load from starboard pushes the vessel to port (Fy > 0). The starboard shaft line goes ahead with its rudder at −30°, pushing to starboard at 331°, while the port one backs to cancel the surge. The yaw moment of the stern sway force is balanced by the bow tunnels, which also push to starboard.

## 5. Worked example: twin screw with bow tunnels

This is the layout of `test_rudders_never_lower_a_number` (tests/models/test_capability.py), on the round test hull:
- SL1 and SL2: shaft lines, open FPP, D = 3 m, 2000 kW, at (−38, ±5). T = 232.96 kN forward, T_rev = 209.66 kN (β_misc).
- NACA rudders with A_r = D² = 9 m² and a maximum angle of 35° (so 30° is used).
- The two bow tunnels of `config.THRUSTERS`.
- The shaft lines flush each other (10 m < 15D = 45 m): zones 68.2–111.8° (SL1) and 248.2–291.8° (SL2). Neither contains 0° or 180°, so they don't matter.
- Each shaft line has 2 pieces: a fan with 61 corners (62 rows including the two rays) and the reverse segment (4 rows). That gives 2 × 2 = 4 combinations per allocation.

Beam (90°), with ventilation:

| BF | Load Fy [kN] | u without rudders | u with rudders |
|---|---|---|---|
| 2 | 61.3 | 0.804 | 0.224 |
| 3 | 148.7 | 1.952 | 0.544 |
| 5 | 269.2 | 3.470 | 0.970 |
| 6 | 371.1 | 4.757 | 1.333 |

- **Without rudders** only the tunnels give sway. Their yaw moment (lever about 30 m) must be cancelled by opposite surge from shaft lines only 10 m apart, about three times the tunnel force. The reversed thrust limits that to **BF 2**.
- **With rudders**, at BF 5 SL2 goes ahead at 331° (168.9, −93.6) kN, near the fan edge, and SL1 backs with 165.6 kN. The tunnels give −64.9 and −110.8 kN. So the beam number is **BF 5**.
- Over 360° the rudders raise every heading except 0° and 180° (11 both ways), and never lower one. The envelope takes about 3.1 s instead of 0.6 s.

## 6. In the code

- `dp_capability/standard.py`: `RUDDER_C_Y = 0.0126`, `RUDDER_C_X_FROM_C_Y = 0.02`, `RUDDER_ANGLE_CAP_DEG = 30.0`, `K1_RUDDER` (Table 3-5), `K2_RUDDER` (Table 3-6).
- `dp_capability/vessel.py`: `Rudder(profile, area, max_angle_deg, behind_fixed_nozzle=False)` (Table A-4) and `Thruster.rudder` (default `None`).
- `dp_capability/models/rudders.py`:
  - `rudder_coefficients(thruster) -> (c_x, c_y)`;
  - `max_rudder_angle_deg(thruster)`: min(maximum, 30°);
  - `rudder_forces(thruster, t_effective, rudder_angle_deg) -> (f_surge, f_sway)`, vectorised over the angle, which is clipped to ±the maximum.
  - All three raise `ValueError` without a rudder, on a non-shaft line, or for an unknown profile.
- `allocate_thrust` in `thruster_allocation.py`:
  - `_rudder_pieces()` builds the fan (via `rudder_forces`, then `_convex_fans` and `_fan_rows`) and the reverse segment (`_along_x`). It drops a piece whose shaft direction is inside a zone; if both are dropped, the thruster gets `_no_force()`.
  - `_problem()` only fixes fy = 0 for shaft lines **without** a rudder.
  - `_size_rows()` measures a rudder shaft line's |f| with the unit N-gon, like an azimuth.
- `capability_numbers_level1` needs no change: the rudder is part of the `Thruster`.
- Not done yet (step 8, Table A-8): the rudder angle and the rudder F_surge / F_sway per heading. `Allocation.angle_deg` gives the direction of the total force, not α. α can be recovered from fy/fx = C_y α / (1 − C_x α²).
