# Handover: DP capability Level 1 (DNV-ST-0111)

_Last updated 2026-09-29, branch `william`. Written at the end of a Claude Code session with William._

## 1. Goal

Implement **DNV-ST-0111 (Edition December 2021), DP capability Level 1** in
Python. For each heading (0–350° in 10° steps):

1. Take wind, current and wave loads from the standard's fixed formulas and multiply them by 1.25.
2. Check whether the effective actuator thrust can balance them.
3. Step up the Beaufort-based DP capability number until the first one that can't be balanced.

We build it **one section of the standard at a time**. Each step is small and
covered by hand-calculated tests. Level 1 is prescriptive: the formulas
"shall be strictly followed without any deviations" (§3.2.1).

## 2. Status

| Step | What | Standard | State |
|---|---|---|---|
| – | Cleanup: untrack `__pycache__`, pin scipy/pytest, fix STRUCTURE.md | – | done, committed (`10b075c`, `3370fff`) |
| 0 | Foundations: conventions, Table 2-1, `Hull` dataclass, test vessel | §2.8.2, Table 2-1, Table A-2 | done, committed (`5efcd31`) |
| 1 | Level 1 wind loads | §3.5 | done, committed (`5efcd31`) |
| 2 | Current loads | §3.6 | done |
| 3 | Wave drift loads + total factored load (`environmental_loads_level1`) | §3.7, §3.2.2 | done |
| 4 | Nominal thrust + β_misc, `Thruster` (Table A-3), test thruster set | §3.9.1–3.9.3 | done |
| 5 | Force/moment balance (thrust allocation) at one heading | §2.4.4, §3.8.2, §3.11.1 | done |
| 6 | Sweep headings × BF → first real capability plot (**first milestone**) | §2.4, §2.2.2 | done |
| 7a | Ventilation loss β_vent and total β_T = β_misc · β_vent | §3.9.4, §3.9.5 | done |
| 7b | Forbidden zones: user zones + flushing sectors, non-convex allocation | §3.11.2, §3.11.3 | done |
| 7c | Skeg loss (direction-dependent) + total β_T; star-polygon capacity | §3.11.5, §3.11.6 | done |
| 7d | Rudders behind shaft lines: `Rudder` (Table A-4), fan + astern pieces | §3.10 | done |
| 7e | Power: `PowerSource` (Table A-5), P = P_B·r^1.5, 10% reserve, batteries | §3.12, §2.4.9 | done |
| 8a | Redundancy groups, failure runs, combined worst case, `DP capability-L1(A,B,C,D)`, multi-curve plots | §2.4.7–2.5, A.3.1, A.3.6 | done |
| 8b | Flushing a dead thruster (failure runs only), Figure 3-6 | §3.11.4, §3.11.6 | done |
| 8c | Report tables A-1, A-7 to A-10 (+ rudder angle of A-8) | App. A.3.1, A.3.5 | **next** |

Steps 2–3 complete the **load side** of Level 1: for any heading and any
Beaufort number, `environmental_loads_level1(hull, bf, direction_deg)` returns
the total factored load (fx, fy, mz) the thrusters must balance. The §3.5–3.7
formulas in the code were checked against the PDF of the standard (not only
against earlier transcriptions).

Step 4 adds the **thrust side** per actuator: `nominal_thrust(thruster, reverse)`
([3.9.2]) and `effective_thrust(...)` = nominal × β_misc ([3.9.1], [3.9.3]).
Tables 3-1 to 3-4 were transcribed from 300 dpi renders of PDF pages 30–32 and
checked against the crops with William before any code was written.

Step 5 **connects the two sides**. `allocate_thrust(thrusters, load)` finds
actuator forces that balance Fx, Fy and Mz at the same time for one load. It
returns the utilisation u (balanced if u ≤ 1), the force and [3.8.2] angle per
actuator. The standard prescribes no allocation method (§3.11.1 guidance note);
ours is two linear programs, see §7 and `Descriptions/thruster_allocation.md`.

Step 6 gives the **first real capability plot** (the first milestone).
- `capability_numbers_level1(hull, thrusters, headings_deg)` steps each heading up from BF 1 until the first BF that doesn't balance ([2.2.2], [2.4.4]).
- `limiting_wind_speed_level1(numbers)` gives the m/s value: the Table 2-1 wind speed of each number (decided with William, §7).
- `main.py` now runs config → numbers → the two polar plots of [2.4.2].
- The test vessel (four thrusters since 2026-09-28, §4) gets:
  - BF 6 (13.8 m/s) over 60–90° and 270–300°;
  - BF 11 head-on and astern;
  - 6 as the lowest number over 360°, and 8 as the lowest within ±30° of the bow.
- The full table is in `Descriptions/capability.md` §3.

Step 7a adds the **ventilation loss** ([3.9.4]) and the total thrust loss factor β_T = β_misc · β_vent ([3.9.5]).
- `ventilation_loss_factor(thruster, hull, hs, tp, direction_deg, reverse=False)` and `thrust_loss_factor_level1(...)` are in `thrust.py`.
- `allocate_thrust(..., beta_t=...)` takes a (forward, reverse) β_T pair per thruster.
- `capability_numbers_level1(..., ventilation=True)` computes β_T per (BF, heading); `ventilation=False` gives the old β_misc-only envelope.
- The formulas (p. 32–33, images) were transcribed from 300 dpi crops and checked with William. The decisions are in §7.
- For the test vessel, only 160° and 200° drop (BF 11 → 10). Everything else is unchanged; the 100° margin tightens to u = 0.995 at BF 7. Up to BF 6 the loss is at most about 1.5%, while at BF 11 in beam seas the aft azimuths lose 28%.
- Write-up: `Descriptions/thrust.md` §6.

Step 7b adds the **forbidden zones** ([3.11.2], [3.11.3]).
- **Where they come from:** `Thruster.forbidden_zones` holds user zones (Table A-6). `forbidden_zones.py` adds the flushing sectors: a working non-tunnel thruster closer than 15D may not be flushed, within ± arctan(0.1 + D/s).
- **Allocation:** a zone makes an azimuth's capacity non-convex. `allocate_thrust` splits the allowed directions into convex pieces of at most 180° and solves the LP pair per combination (agreed with William, §7).
- **Switches:** `forbidden_zones=True/False` on `allocate_thrust` and `capability_numbers_level1`.
- **Effect on the test vessel:** none on the numbers. AZ1 and AZ2 get 90° ± 20.44° and 270° ± 20.44°, but they balance yaw by pushing in opposite surge directions, well clear of the zones. u only changes at 10°/350°, BF 6–7 (+0.0015 at u ≈ 0.19). The envelope takes about 1.5 s instead of 0.7 s.
- Write-up: `Descriptions/forbidden_zones.md`.

Step 7c adds the **skeg loss** ([3.11.5]) and completes β_T of [3.11.6] for intact runs.
- **The loss:** `skeg_loss.py` gives the Table 3-7/3-8 factor as a function of thrust direction. It applies to non-tunnel thrusters above the base line within 15D (open) / 8D (ducted) of the skeg plane, and not directly behind the skeg.
- **Capacity shape:** since the loss depends on direction, it changes the *shape* of an azimuth's capacity. `allocate_thrust` now draws every azimuth as a **star polygon** (radius T·β_skeg(θ), corners every 10°, at zone edges, breakpoints and every 1° in loss ramps). It splits the polygon into **convex fans** and enumerates them as in 7b.
  - Without zones or skeg it is exactly the old 36-gon. With `skegs=()` all u values match 7b to 1e-14.
- **Switches:** `skegs=` on `allocate_thrust`, and `skeg_loss=True/False` on `capability_numbers_level1` (which passes `hull.skegs`).
- **Effect on the test vessel:** the aft azimuths lose up to 43.5% around 141° (AZ1) and 219° (AZ2). 100° and 260° drop from BF 7 to 6; nothing else changes. The lowest numbers stay 6 and 8. The envelope takes about 3.8 s (9 LP combinations per call).
- Write-up: `Descriptions/skeg_loss.md`. The transcription was checked with William on the 300 dpi crops, and the decisions are in §7.

Step 7d adds **rudders** behind shaft line propellers ([3.10]).
- **Input:** `Thruster.rudder = Rudder(profile, area, max_angle_deg, behind_fixed_nozzle=False)`, the Table A-4 fields. Tables 3-5 (k1) and 3-6 (k2) are in `standard.py`.
- **Forces:** `rudders.py` gives F_Surge = T(1 − C_x α²) and F_Sway = T·C_y·α ([3.10.1]), with α in degrees, capped at min(maximum, 30°).
- **Allocation:** a rudder shaft line has two pieces: a convex **fan** of these forces ahead (corners every 1° of α), and **astern along −x only** ([3.10.2]). They are enumerated like the 7b/7c pieces, not joined. Zones and β_skeg are taken at the shaft direction (0°/180°).
- **Effect:** none on the test vessel (no shaft lines); the envelope is unchanged. On a twin-screw test layout (two shaft lines + the two bow tunnels) the beam number rises from BF 2 to 5, and every heading but 0°/180° rises. The envelope takes 3.1 s instead of 0.6 s.
- The formulas and tables were checked with William on the p. 34 render (2026-09-29). Write-up: `Descriptions/rudders.md`.

Step 7e adds **power** ([3.12], [2.4.9]). With it, step 7 is complete: every intact-condition refinement of Level 1 is in.
- **Input:** `PowerSource(name, available_kw, electrical=True)`, one Table A-5 column (a switchboard, or a prime mover driving a propeller), and `Thruster.power_supply = ((source, share), ...)`, the Table A-5 row. `battery_power_kw()` gives [3.12.2]'s battery power to add to a switchboard.
- **Power model:** P = P_B·r^1.5, from turning [3.9.2] around (r = thrust before losses / nominal thrust). A switchboard gives 90% of its power to thrusters ([3.12.3]–[3.12.4]).
- **Allocation:** each thruster now has its own fraction r_i ≤ U; power per thruster is bounded below by chords of r^1.5 (conservative); each source gives ≤ U × its usable power. Pass 1 minimises U, so U is the higher of the thrust and power demand. `Allocation` also returns `thrust_fraction`, `power_kw` and `source_power_kw` (for Tables A-8 to A-10).
- **Optional:** `power_sources=None` gives exactly the old results; all 229 earlier tests pass unchanged.
- **Effect:** `config.POWER_SOURCES` (2 × 3600 kW, see §4) doesn't bind, so the test vessel's envelope is unchanged (4.2 s instead of 3.5 s). With 3000 kW per switchboard (2700 kW usable < 2900 kW of thrusters), the psv test layout drops at 100° and 260° (BF 7 → 6).
- All of §3.12 is text in the PDF; the decisions are in §7. Write-up: `Descriptions/power.md`.

Step 8a adds the **failure runs** and the final result string ([2.4.7], [2.4.8], [2.5]).
- **Input:** `RedundancyGroup(name, thrusters, power_sources)`, what the DP FMEA says one single failure loses. `config.REDUNDANCY_GROUPS` has one group per switchboard, with its two thrusters.
- **Failure run:** `failure_case(thrusters, group, power_sources)` (`redundancy.py`) removes the group, and `failure_numbers_level1` runs `capability_numbers_level1` on what is left, for every group.
  - A thruster fed partly from a lost source keeps only its remaining share of P_B (decided with William, §7).
  - A dead thruster's flushing sectors disappear by themselves, because they are only built from the working thrusters.
- **Result:**
  - `worst_case_numbers` gives the combined curve (lowest per heading);
  - `information_elements_level1` gives (A, B, C, D), with ±30° including its edges;
  - `capability_notation` writes `DP capability-L1(A, B, C, D)`, with NA without redundancy.
- **Plots:** `plot_envelopes` draws several curves with a legend. `main.py` prints the notation and draws intact + WCSF (numbers and m/s, Figure A-1) and every group (Figure A-2).
- **Test vessel: DP capability-L1(8, 6, 5, 3).**
  - The loss of SWBD 1 (leaving AZ2 and the weaker tunnel BT2) is the WCSF at most headings.
  - Beam is BF 3–4, and the remaining tunnel is the limit.
  - Step 8b added the §3.11.4 loss where the surviving azimuth pushes onto the dead one; the numbers didn't change.
- Everything read is text (pp. 13, 17–18, 67–69, 77). Table A-1 was checked with William on a 300 dpi crop and is used as a test. Write-up: `Descriptions/redundancy.md`.

Step 8b adds the loss from **flushing a dead thruster** ([3.11.4], Figure 3-6). With it, β_T of [3.11.6] is complete.
- **The loss:** `dead_flushing.py` handles a working thruster whose race hits a dead non-tunnel thruster closer than 8D (open) or 4D (ducted).
  - It gets a notch in its capacity of half-width arctan(0.6D/s) (open) or arctan(0.35D/s) (ducted).
  - At the centre the factor is β = 1 − 1/(0.02(s/D)² + 0.25 s/D + 1.2).
  - The notch has straight sides in Cartesian coordinates (Figure 3-6).
- **Allocation:** `allocate_thrust(..., dead_thrusters=())` multiplies the star-polygon radius by β_dead(θ) next to β_skeg(θ) (corners at the sector edges, the centre and every 1°). Tunnels and shaft lines take the factor of their fixed directions.
- **Runs:** `capability_numbers_level1(..., dead_thrusters=())` passes it on, and `failure_numbers_level1(..., dead_flushing=True)` passes the group's thrusters.
- **Test vessel:**
  - AZ2 flushing the dead AZ1 (and AZ1 flushing AZ2) gets ±5.45° around 270° (90°), with β = 0.581.
  - Its thrust fraction rises at beam (0.227 → 0.355 at 90° BF 4), but the tunnel limits, so no u and no number changes. The result stays **DP capability-L1(8, 6, 5, 3)**.
  - A hand-checked layout (two azimuths 6 m apart, head-on) drops from 7 to 6.
- The p. 36 and p. 39 formulas were checked with William on 300 dpi crops (2026-09-29). Write-up: `Descriptions/dead_flushing.md`.

**Where the standard was read from:** `SOURCES.md` (new 2026-09-29) lists every part used so far: PDF text layer or rendered crop, and whether William checked it.

**Tests:** 293 passing (`tests/test_standard.py`: 7, `tests/models/test_environmental_loads.py`: 51, `tests/models/test_thrust.py`: 59, `tests/models/test_rudders.py`: 19, `tests/models/test_power.py`: 19, `tests/models/test_forbidden_zones.py`: 13, `tests/models/test_skeg_loss.py`: 11, `tests/models/test_dead_flushing.py`: 14, `tests/models/test_thruster_allocation.py`: 62, `tests/models/test_redundancy.py`: 9, `tests/models/test_capability.py`: 23, `tests/plotting/test_capability_plot.py`: 6). Matplotlib's import prints 14 pyparsing deprecation warnings; they don't come from our code.

## 3. Conventions: read before writing any formula

These come from DNV-ST-0111 §2.8.2 and are written down once, in the module
docstring of `dp_capability/standard.py`.

- **Body frame:** x forward, y to **port**, z up. Origin at Lpp/2, on the centreline, at the keel.
- **Signs:** forces are positive forward and to port. The yaw moment is positive counter-clockwise (bow to port). A force at (x, y) gives `Mz = x·Fy − y·Fx`.
- **Environment direction:** where the wind, current or waves come **from**, measured clockwise. 0° = head-on, 90° = from starboard, 180° = astern, 270° = from port.
- **Units:** SI. Public functions take directions in **degrees** and convert to radians internally (the formulas use radians, note under §2.8.3). Exceptions:
  - the rudder angle α in §3.10 is in degrees;
  - `Thruster.power_kw` is in kW, because the §3.9.2 formula wants kW; so are all power values of §3.12 (`PowerSource.available_kw`, `Allocation.power_kw`).
- **`dir` fold:** use `standard.fold_direction()`, which keeps the direction if it is ≤ π and otherwise returns 2π − direction. Wind (§3.5), current (§3.6) and waves (§3.7) all use it, but **only** for `dir` terms (lever arms, `h1`, `h2`), never inside `sin(direction)`, which is what flips the sign of FY for port-side directions.
- **Where numbers live:**
  - Values the standard fixes go in `standard.py`: `RHO_AIR = 1.226`, `RHO_WATER = 1026.0`, `TZ_FROM_TP = 1.4049`, `DYNAMIC_FACTOR_LEVEL1 = 1.25`, Tables 3-1 to 3-4 (`ETA1`, `ETA2_TUNNEL`, `ETA2_FORWARD`, `ETA2_REVERSED`, `ETA_M`), `BETA_MISC = 0.9`, the ventilation coefficients `K_V1`…`K_V5` = 2, 1.5, 15.2, 0.85, 0.38, the rudder coefficients and Tables 3-5/3-6, `POWER_RESERVE_FRACTION = 0.10`, the battery rules `BATTERY_SOC_HIGH/LOW = 0.8/0.2`, `BATTERY_MIN_HOURS = 0.5`, and our choice `G = 9.81`.
  - Vessel values go in `config.py`.
  - Functions never hard-code either.
- **Vectorized:** functions are numpy-vectorized over direction, so one call can evaluate a whole envelope.
- **Dynamic factor:** the individual load functions return the standard's raw (unfactored) formulas, so each stays checkable one-to-one against its section. The 1.25 is applied once, to the sum, in `environmental_loads_level1`.

**Blendermann is not Level 1.** `blendermann_wind_coefficients()` in
`windloads.py` is a Level 2/3 method (§4.6.3, §6.7.1). It also uses y to
**starboard** and ρ_air = 1.23. Keep it for later comparisons, but don't mix
it into the Level 1 chain.

## 4. What exists now

| File | Contents |
|---|---|
| `dp_capability/standard.py` | The conventions docstring and constants. `BeaufortCondition` + `ENVIRONMENT_TABLE` (Table 2-1, BF 0–11; BF 0 has `tp = nan`). `environment(bf)` raises ValueError outside 0–11. `fold_direction()`. Tables 3-1 to 3-4 as dicts, `BETA_MISC`, `K_V1`…`K_V5`. Rudders: `RUDDER_C_Y = 0.0126`, `RUDDER_C_X_FROM_C_Y = 0.02`, `RUDDER_ANGLE_CAP_DEG = 30`, `K1_RUDDER` (Table 3-5), `K2_RUDDER` (Table 3-6). Power: `POWER_RESERVE_FRACTION`, `BATTERY_SOC_HIGH`, `BATTERY_SOC_LOW`, `BATTERY_MIN_HOURS`. `BOW_SECTOR_DEG = 30` ([2.5.1]) |
| `dp_capability/vessel.py` | `Hull` frozen dataclass matching Table A-2: `loa, lpp, draft, breadth, los, x_los, bow_angle [rad], aw_laft, af_wind, al_wind, xl_air, af_current, al_current, xl_current, skegs`. `Thruster` frozen dataclass matching Table A-3: `name, kind, diameter, power_kw, x, y, z, pitch="FPP", ducted, permanent_magnet, contra_rotating, tunnel_inlet, forbidden_zones=(), rudder=None, power_supply=()` (user zones, Table A-6: (start, end) thrust angles in degrees, [3.8.2] convention; `power_supply`: the Table A-5 row, (source name, share) pairs). `Rudder` frozen dataclass matching Table A-4: `profile` (Table 3-5 key), `area` (A_r, chord ≤ 1.0D), `max_angle_deg`, `behind_fixed_nozzle=False`; shaft lines only. `PowerSource(name, available_kw, electrical=True)`: a Table A-5 column (switchboard, or prime mover driving a propeller). `RedundancyGroup(name, thrusters=(), power_sources=())`: the thruster and source names one single failure loses (DP FMEA) |
| `dp_capability/models/power.py` | `thruster_power_kw(thruster, thrust_fraction)` = P_B·r^1.5 (vectorised), `battery_power_kw(energy_kwh, max_discharge_kw)` [3.12.2], `usable_power_kw(source)` (90% of a switchboard, [3.12.3]), `supply_matrix(thrusters, sources)` (Table A-5 shares, (sources × thrusters); `ValueError` for missing/unknown/duplicate/non-summing supplies) |
| `dp_capability/models/redundancy.py` | `failure_case(thrusters, group, power_sources=None) -> (thrusters, power_sources)`: removes the group; a split-fed survivor gets P_B × remaining share and rescaled shares. `ValueError` for unknown names or a thruster outside the group left without power |
| `dp_capability/models/rudders.py` | `rudder_coefficients(thruster) -> (c_x, c_y)`, `max_rudder_angle_deg(thruster)` = min(max, 30), `rudder_forces(thruster, t_effective, rudder_angle_deg) -> (f_surge, f_sway)` [3.10.1], vectorised over α. `ValueError` without a rudder, on a non-shaft line or for an unknown profile |
| `dp_capability/config.py` | `HULL`: a made-up ~80 m OSV. `THRUSTERS`: its four actuators, with their Table A-5 supply. `POWER_SOURCES`: its two switchboards. `REDUNDANCY_GROUPS`: "SWBD 1" (SWBD 1, AZ1, BT1) and "SWBD 2" (SWBD 2, AZ2, BT2) (all below). `HEADINGS_DEG`: 0–350° in 10° steps ([2.4.6]) |
| `dp_capability/models/thrust.py` | `nominal_thrust(thruster, reverse=False)` [N] and `effective_thrust(thruster, reverse=False, beta_t=BETA_MISC)` [N]. Row pickers `_eta1`, `_eta2`, `_eta_m` (rules in §7). `ventilation_loss_factor(thruster, hull, hs, tp, direction_deg, reverse=False)` = β_vent [3.9.4], vectorized over direction, with helpers `_propeller_load_factor`, `_relative_motion_std`. `thrust_loss_factor_level1(...)` = β_misc · β_vent [3.9.5] |
| `dp_capability/models/windloads.py` | Blendermann (unchanged) + `wind_loads_level1(hull, wind_speed, direction_deg) -> (fx, fy, mz)` |
| `dp_capability/models/currentloads.py` | `current_loads_level1(hull, current_speed, direction_deg) -> (fx, fy, mz)`. FX uses `breadth · draft` (Level 1 does not use `af_current`); lever factor clipped to [−0.2, 0.25] |
| `dp_capability/models/waveloads.py` | `wave_loads_level1(hull, hs, tp, direction_deg) -> (fx, fy, mz)` and the helper `_period_factor()` = f(T'). Returns exactly 0 where `hs == 0` (BF 0 has `tp = nan`) |
| `dp_capability/models/environmental_loads.py` | `environmental_loads_level1(hull, bf, direction_deg, dynamic_factor=1.25)`: looks up Table 2-1, sums wind + current + waves, multiplies by the dynamic factor |
| `dp_capability/models/forbidden_zones.py` | `flushing_sectors(thrusters)` ([3.11.3]), `merge_zones(zones)`, `forbidden_zones_level1(thrusters)` (user zones + flushing sectors per thruster = Table A-6 content), `allowed_arcs(zones)` (the arcs between the zones). Degrees, [3.8.2] thrust angles |
| `dp_capability/models/skeg_loss.py` | `skeg_loss_breakpoints(thruster, skeg)` (Table 3-7/3-8 points in degrees, or None if not applicable), `skeg_loss_factor(thruster, skegs, angle_deg)` (interpolated, minimum over skegs, vectorised). `SKEG_DISTANCE_D_OPEN/DUCTED` = 15 / 8 |
| `dp_capability/models/dead_flushing.py` | `dead_flushing_loss(thruster, dead) -> (centre_deg, phi_deg, beta)` or None ([3.11.4]; dead tunnel or not closer than 8D/4D), `dead_flushing_factor(thruster, dead_thrusters, angle_deg)` (straight notch of Figure 3-6, lowest over the dead, vectorised), `dead_flushing_breakpoints(thruster, dead)`. `DEAD_FLUSHING_DISTANCE_D_OPEN/DUCTED` = 8 / 4 |
| `dp_capability/models/thruster_allocation.py` | `allocate_thrust(thrusters, load, n_sides=36, beta_t=None, forbidden_zones=True, skegs=(), power_sources=None, dead_thrusters=()) -> Allocation` (`beta_t`: a (forward, reverse) β_T pair per thruster; None = β_misc) for **one** heading (not vectorized). Azimuth capacity is a star polygon (radius T·β_skeg(θ)·β_dead(θ)) split into convex fans; pass 1 runs per combination of fans. Each thruster has its own fraction r_i ≤ U; with power sources, power chords and source rows are added. `Allocation` has `fx`, `fy` per actuator [N], `utilisation` (U), `thrust_fraction` (r), `power_kw`, `source_power_kw`, and the properties `feasible` (U ≤ 1 + `TOLERANCE`) and `angle_deg` ([3.8.2], nan when idle). A shaft line with a rudder has two pieces (`_rudder_pieces`: fan ahead, −x astern) and free fy. Helpers `_thruster_pieces`, `_rudder_pieces`, `_no_force`, `_along_x`, `_polygon_angles`, `_convex_fans`, `_fan_rows`, `_size_rows`, `_place`, `_power_chords`, `_problem`, `_inequalities`, `_min_utilisation` (pass 1), `_least_total_thrust` (pass 2), `_thrust_fractions`, `_solve`; `RAMP_STEP_DEG = 1.0`, `RUDDER_STEP_DEG = 1.0`, `POWER_STEP = 0.05` |
| `dp_capability/models/capability.py` | `capability_numbers_level1(hull, thrusters, headings_deg, ventilation=True, forbidden_zones=True, skeg_loss=True, power_sources=None, dead_thrusters=()) -> int array` (0–11, same shape as the headings; stops per heading at the first failing BF; β_T per (BF, heading) from the helper `_loss_factors`). `limiting_wind_speed_level1(numbers) -> float array` [m/s] = Table 2-1 wind speed, `ValueError` outside 0–11. `failure_numbers_level1(hull, thrusters, headings_deg, groups, power_sources=None, dead_flushing=True, **options) -> {group name: numbers}` (the group's thrusters are the `dead_thrusters`), `worst_case_numbers(numbers)` (lowest per heading, [2.4.7]), `information_elements_level1(headings_deg, intact, worst=None) -> (A, B, C, D)` (C, D None without worst), `capability_notation(a, b, c=None, d=None, level=1)` |
| `dp_capability/models/Descriptions/` | Theory write-ups: `windloads.md` (§5 = Level 1), `currentloads.md`, `waveloads.md`, `thrust.md`, `rudders.md`, `power.md`, `forbidden_zones.md`, `skeg_loss.md`, `dead_flushing.md`, `thruster_allocation.md`, `capability.md`, `redundancy.md`. Formulas, sign checks, worked examples, code mapping |
| `dp_capability/plotting/capability_plot.py` | `plot_envelope(headings_deg, values, title=None, r_max=None) -> (fig, ax)`: polar plot, north-up and clockwise ([2.8.2]), loop closed back to the first heading. `plot_envelopes(headings_deg, curves, ...)`: several `{label: values}` curves with a legend (Figures A-1/A-2) |
| `main.py` | config (with `POWER_SOURCES`, `REDUNDANCY_GROUPS`) → intact and failure numbers → prints `DP capability-L1(8, 6, 5, 3)` → three plots: intact + WCSF in numbers (r_max 11) and in m/s (r_max 32.6), and every loss case in numbers |
| `io_utils.py`, `processing/clean.py` | Empty |

### Test vessel `config.HULL` (fictional)

| Quantity | Value |
|---|---|
| Loa / Lpp / draft / B | 88 / 80 / 6 / 18 m |
| Los / x_Los | 86 m (under water from x = −44 to +42) / −1 m |
| Bow angle | atan(4.5/10) ≈ 0.4229 rad |
| A_WLaft | 648 m² (C_WLaft = 0.90) |
| A_F,wind / A_L,wind / x_L,air | 280 m² / 700 m² / +12 m |
| A_F,current / A_L,current / x_L,current | 100 m² / 490 m² / −1.5 m |
| Skegs | one, at (−36, 0) |

Sanity check at BF 6 (13.8 m/s wind, 0.75 m/s current, Hs 3.1 m, Tp 8.5 s),
as (fx, fy, mz) in kN and kNm:

| Heading | Wind | Current | Wave | Total × 1.25 |
|---|---|---|---|---|
| 0° | −22.9, 0, 0 | −2.2, 0, 0 | −24.6, 0, 0 | −62.1, 0, 0 |
| 90° | 0, 73.5, 882.6 | 0, 84.8, −127.3 | −4.4, 128.0, −348.1 | −5.5, 358.0, 509.0 |
| 180° | +22.9, 0, 0 | +2.2, 0, 0 | +26.1, 0, 0 | +64.0, 0, 0 |

BF 0 gives exactly (0, 0, 0) at every heading, and over 0–350° the totals are
port/starboard symmetric for every BF: fx(360−θ) = fx(θ), fy and mz flip sign.

The tests build their **own** round-number hull, so changing `config.HULL`
never breaks them.

### Test thrusters `config.THRUSTERS` (fictional)

Two azimuths aft and two bow tunnels. Positions are in the §2.8.2 frame (y to port, z up from the keel).
`power_kw` is the documented DP power with torque limits, so the 50%-MCR
fallback doesn't apply.

| Name | Kind | D [m] | P_B [kW] | Pitch | Ducted | Inlet | x, y, z [m] | T_nom fwd / rev [kN] |
|---|---|---|---|---|---|---|---|---|
| AZ1 | azimuth, aft port | 3.0 | 2000 | FPP | yes | – | −40, +5.5, 1.8 | 377.52 / 264.26 |
| AZ2 | azimuth, aft stbd | 3.0 | 2000 | FPP | yes | – | −40, −5.5, 1.8 | 377.52 / 264.26 |
| BT1 | tunnel | 2.0 | 900 | CPP | – | rounded | +31, 0, 2.5 | 135.77 / 135.77 |
| BT2 | tunnel | 2.0 | 900 | CPP | – | broken | +28, 0, 2.5 | 126.89 / 126.89 |

- **Azimuths and tunnels only** (changed 2026-09-28). These are the kinds available for testing in DNV's Veracity app, so the retractable azimuth `RAZ` (open FPP, D 1.8 m, 800 kW at x = +22, z = −1.5) was removed.
  - The two tunnels still have different inlets, so the Veracity comparison covers two rows of Table 3-2.
  - Without RAZ it no longer covers the open FPP azimuth rows of Tables 3-1 and 3-3 (η1 = 800, reversed η2 = 0.9). `tests/models/test_thrust.py` still checks that case with its own thruster.
- **Beam capability is BF 6.** At 90°, u = 0.537 at BF 5, 0.744 at BF 6 and 1.047 at BF 7 (β_misc only; with ventilation 0.538, 0.747 and 1.055).
  - The forward group (BT1, BT2: 236 kN at x ≈ 29.6 m) has to match the moment of the aft azimuths at x = −40 m. Even a pure 500 kN sway load (BF 7) with no moment gives u = 1.007.
  - Worked example with all forces: `Descriptions/thruster_allocation.md` §3.
  - With RAZ (five thrusters) it was BF 7.
- **The whole envelope** (with ventilation, zones and skeg loss, steps 7a–7c):
  - BF 11 at 0–10°, 170–190° and 350°; BF 10 at 160° and 200° (11 without ventilation);
  - BF 6 over 60–100° and 260–300° (100°/260° were 7 without the skeg loss);
  - symmetric port/starboard.
  - Close calls: at 50° BF 7 balances with u = 0.962, and at 100° BF 7 fails with u = 1.011. Neither changes with 72 or 360 polygon corners.
  - Table: `Descriptions/capability.md` §3.
- **Ventilation** (`Descriptions/thrust.md` §6): propeller load factor 7.78 (AZ), 8.57 (BT1), 8.29 (BT2). β_vent at beam is 0.985 / 0.999 / 0.999 at BF 6 and 0.725 / 0.861 / 0.883 at BF 11.
- **Forbidden zones** (`Descriptions/forbidden_zones.md` §5): AZ1 69.56–110.44°, AZ2 249.56–290.44° (flushing each other, 11 m < 15D = 45 m); tunnels none. No effect on the numbers.
- **Skeg loss** (`Descriptions/skeg_loss.md` §5): the aft azimuths are 4 m aft and 5.5 m outboard of the skeg end (−36, 0), s = 6.80 m < 8D = 24 m.
  - AZ1 loses thrust over 111.20–180° (minimum 0.565 at 140.85°), AZ2 over 180–248.80° (0.565 at 219.15°). The tunnels are exempt.
  - Together with the zones, each azimuth has 3 convex pieces.
- **Rudders (7d):** none, since it has no shaft lines.
- **Power (7e), `config.POWER_SOURCES`:** two switchboards, bus-tie open, each with 2 × 1800 kW gen-sets. SWBD 1 feeds AZ1 + BT1, SWBD 2 feeds AZ2 + BT2.
  - 90% of 3600 = 3240 kW usable > 2000 + 900 = 2900 kW, so power never binds and the envelope is unchanged.
  - Losing a switchboard also loses its two thrusters (step 8a, below).
- **Failure runs (8a), `config.REDUNDANCY_GROUPS`:** loss of SWBD 1 leaves AZ2 + BT2, loss of SWBD 2 leaves AZ1 + BT1.
  - Result **DP capability-L1(8, 6, 5, 3)**: C = 5 at 30°/330°, D = 3 at 60–80° and 280–300° (loss of SWBD 1).
  - The loss of SWBD 1 is the WCSF almost everywhere, because BT2 (broken inlet) is weaker than BT1. The loss of SWBD 2 is lower only at 190° and 350°.
  - The remaining tunnel saturates first except near head and stern seas. Power never binds.
  - Close calls: the loss of SWBD 1 fails at 170° BF 9 (u = 1.0011) and 300° BF 4 (1.005); the loss of SWBD 2 fails at 20° BF 7 (1.0013). They are the same with 72 or 360 polygon corners.
  - Full table: `Descriptions/redundancy.md` §5. The two failure runs take about 2.4 s.
  - **Dead flushing (8b).** AZ1 and AZ2 are 11 m apart, less than 4D = 12 m (ducted). In the loss of SWBD 1, AZ2 pushes at 265–285° for loads from starboard, right into the dead AZ1.
    - AZ2 gets a notch of ±5.45° around 270° with β = 0.581 (AZ1 mirrors this at 90°).
    - The tunnel limits there, so no u changes (`Descriptions/dead_flushing.md` §5).

## 5. Next step: the report tables (step 8c)

Step 7 is done (7a–7e below), and so are 8a and 8b (§2, `Descriptions/redundancy.md`, `Descriptions/dead_flushing.md`). With 8b, every loss factor Level 1 prescribes is in. What is left of step 8:
- **8a. Redundancy groups and failure runs: done (2026-09-29).** See §2, §7 and `Descriptions/redundancy.md`.
- **8b. Flushing a dead thruster, §3.11.4: done (2026-09-29).** See §2, §7 and `Descriptions/dead_flushing.md`.
- **8c. Report tables (next):** Table A-1 and Tables A-7 to A-10, one set per run (intact, then each group, A.3.6).
  - The column lists are in the text layer of pp. 69 and 74–77. Read them again before designing the output (`SOURCES.md`).
  - **Table A-1:** heading, then the number of each run. It comes straight from `capability_numbers_level1` and `failure_numbers_level1`.
  - **Table A-7:** per heading, the number, the limiting wind speed, and the wind, current and wave forces at that number, from `wind_loads_level1`, `current_loads_level1` and `wave_loads_level1`. Decide with William whether to show the 1.25 (the template doesn't say, §8).
  - **Tables A-8 to A-10:** rerun `allocate_thrust` at each heading's number and read the `Allocation`.
    - A-8 per thruster: direction `angle_deg`, utilisation `thrust_fraction`, thrust loss factor, rudder angle and rudder F_surge/F_sway, and power `power_kw`.
    - A-9: `power_kw` split per source with the Table A-5 shares.
    - A-10: `source_power_kw`, plus usable and reserved power per source.
  - **The thrust loss factor of A-8** now depends on direction: β_misc · β_vent · β_skeg(θ) · β_dead(θ) at the thruster's angle. Expose it from the allocation or recompute it from the angle.
  - **Rudder angle:** from a rudder shaft line's force, fy/fx = C_y α / (1 − C_x α²) (§6).
  - **Structure:** build the tables as data (e.g. a new `models/report.py` returning arrays or dicts) and keep file writing in `io_utils.py` (STRUCTURE.md: nothing else opens files). Saving plots to `output/` goes there too.
  - A capability number of 0 has no allocation to report (BF 0 is calm). Decide what the row shows.

Step 7 added everything Level 1 prescribes on top of β_misc, one section at a time. For each part:
- render the formula pages first (most of §3.9.4–§3.11.6 are images);
- show the crops next to any transcription before writing code.

The text of pages 32–40 was skimmed on 2026-09-22 to plan this.

**Rendering the PDF:** PyMuPDF is not in `.venv`. A previous session installed
it in a Claude scratchpad (`…/b59274f0-…/scratchpad/pylib`); put that folder on
`PYTHONPATH`, or install PyMuPDF into a new scratch folder, and use
`import pymupdf`. Claude Code's Read tool can't render the PDF on this machine
(no poppler). Earlier renders and where each part came from are listed in
`SOURCES.md`. The formulas are vector drawings, but Tables 2-1 and 3-1 to 3-6
and the Appendix A tables are in the text layer (`page.get_text()`).

- **7a. Ventilation, §3.9.4 + §3.9.5: done (2026-09-28).** See §2, §7 and `Descriptions/thrust.md` §6.
  - β_T reaches `allocate_thrust` as a per-thruster `(forward, reverse)` pair. That only works for losses that don't depend on the thrust direction.
- **7b. Forbidden zones, §3.11.2 + §3.11.3: done (2026-09-28).** See §2, §7 and `Descriptions/forbidden_zones.md`.
  - The allocation solves one LP pair per combination of convex pieces of each azimuth's allowed directions.
- **7c. Skeg loss, §3.11.5 + total β_T, §3.11.6: done (2026-09-28).** See §2, §7 and `Descriptions/skeg_loss.md`.
  - An azimuth's capacity is now a general **star polygon** (corners at angle θ, radius T·β_skeg(θ)), split into convex fans by `_convex_fans`. The zones of 7b go through the same machinery.
  - The combinations multiply (3 × 3 = 9 for the test vessel). If a layout makes that slow, `scipy.optimize.milp` is the fallback.
  - §3.11.6's β_flushing,dead (§3.11.4) only exists in failure cases. Step 8b reused the polygon for it: it multiplies the radius, with straight sides in *Cartesian* coordinates as Figure 3-6 says.
- **7d. Rudders, §3.10: done (2026-09-29).** See §2, §7 and `Descriptions/rudders.md`.
  - A rudder shaft line has two pieces (fan ahead, −x astern), so each one doubles the combinations. The LPs stay small (61 fan corners).
  - Table A-8's rudder angle and rudder F_surge/F_sway are left for step 8. α follows from fy/fx = C_y α / (1 − C_x α²).
- **7e. Power, §3.12: done (2026-09-29).** See §2, §7 and `Descriptions/power.md`.
  - The LP now has a fraction r_i per thruster and, with power sources, chords of P_B·r^1.5 and a row per source. Without sources it gives the old results exactly.
  - Failures (step 8a) pass a reduced set of `power_sources` and thrusters.

**Keep in mind:** numbers near the margin (the test vessel at 50°, u = 0.962 at
BF 7, §4) are the first to drop if more losses come in. Rerun `main.py` after
each sub-step and record the envelope.

## 6. Later steps: notes and gotchas

**Step 8: capability numbers** (8a done; see `Descriptions/redundancy.md`)
- A and C are the lowest BF within ±30° of the bow, edges included. B and D are the lowest over 0–360°. A and B are intact; C and D are the combined worst case. For the test vessel: (8, 6, 5, 3).
- §3.11.4 (flushing a *dead* thruster) is in since step 8b (`Descriptions/dead_flushing.md`); dead thrusters only exist in failure runs.
- Table A-7 (loads per heading at its number) and Table A-8 (thruster forces) can be built from `environmental_loads_level1` and `allocate_thrust` at each heading's number.
  - Table A-8 also asks for the rudder angle and rudder F_surge/F_sway (A.3.5). α follows from a rudder shaft line's force: fy/fx = C_y α / (1 − C_x α²).
  - Table A-4 asks for the "maximum side force from rudder" as an output: T·C_y·α_max.

## 7. Decisions and open questions

Decided:
- **g = 9.81 m/s²** for wave drift (§3.7 uses g, but the standard gives no value). `standard.G`.
- **The 1.25 dynamic factor is applied in `environmental_loads_level1`**, once, to the sum of wind + current + waves. The three load functions return the unfactored formulas of §3.5–3.7.
- **Picking rows in Tables 3-1 to 3-4** (`thrust.py`, where the tables leave gaps; agreed with William):
  - η1: tunnels and cycloidals ignore the ducted/contra-rotating flags. Ducted *and* contra-rotating raises `ValueError`, since Table 3-1 has no row for it.
  - η2: tunnels use Table 3-2 in both directions. A tunnel without `tunnel_inlet` raises; there is no silent fallback to 0.93. Cycloidals get 1.0 both ways (guidance note to Table 3-3).
  - η_M: any permanent magnet actuator other than a cycloidal counts as **rim-driven** (0.995), because Table A-3 only has a "permanent magnet" flag.
  - Water jets raise `ValueError`, because §3.8.1 asks for manufacturer data.
- **The 50%-of-MCR rule (§3.9.2 GN3) is an input choice, not code.** `Thruster.power_kw` is whatever P_B is documented.
- **`effective_thrust` takes β_T as `beta_t`, defaulting to β_misc.** §3.9.5 defines β_T = β_misc · β_vent. The flushing and skeg factors of §3.11 multiply on top in step 7.
- **Ventilation, §3.9.4** (step 7a, agreed with William 2026-09-28; details in `Descriptions/thrust.md` §6):
  - **T_Nominal in PropellerLoad is the [3.9.2] nominal thrust**, not the commanded thrust. [3.9.2] uses the same symbol and defines it as "thrust with no wind, waves or current".
    - It is taken in the direction of the capacity row: reversed for the negative limit of tunnels and shaft lines.
    - So β_vent is fixed per (thruster, BF, heading), and the LPs need no iteration.
  - **T_Nominal is in N.** The PDF says "[N]", and with kN the propeller-load term would never switch on.
  - **B's second range is read as a union.** The PDF prints ∩ between [−π, −π/2] and [π/2, π].
  - **It applies to every actuator kind, tunnels included.** §3.9.4 excludes none.
  - **Tz = Tp / 1.4049**, as for wave drift.
  - A consequence of the formula: more power at the same D raises the propeller load and so the ventilation. At 10× power the test PSV's azimuths have β_vent ≈ 0.001 at BF 11. The BF 11 cap test therefore runs with `ventilation=False`.
- **Thrust allocation** (`thruster_allocation.py`; §3.11.1 prescribes no method):
  - **Two LPs** with `scipy.optimize.linprog` (HiGHS), agreed with William.
    - Pass 1 minimises the utilisation u. This is the same problem as HANDOVER's earlier "maximise λ" (u = 1/λ), but BF 0 gives u = 0 instead of an unbounded LP.
    - Pass 2 keeps u and minimises total thrust, so that actuators with room to spare don't push against each other. That makes the forces and angles usable for Table A-8.
  - **Azimuths, pods and cycloidals** push any way, with forward thrust only. They use an inscribed **36-gon** (`n_sides`, a keyword argument, not in `standard.py`), with corners every 10° from 0°. It is at most 0.4% conservative.
  - **Tunnels** push along ±y. **Shaft lines** push along ±x with reversed thrust aft; rudders come in step 7.
  - **Feasible means u ≤ 1 + 10⁻⁶** (`TOLERANCE`). Pass 2 may use the same slack.
  - An unreachable load (e.g. tunnels only against surge) gives u = ∞ and `nan` forces, not an exception.
- **Forbidden zones** (step 7b, agreed with William 2026-09-28; details in `Descriptions/forbidden_zones.md`):
  - **Non-convex allocation by convex pieces.** Each azimuth's allowed directions are split into arcs of at most 180°. Pass 1 runs for every combination and the lowest u is kept; pass 2 runs in the first combination that reaches it. It is exact, with no big-M/MILP. MILP stays the fallback if 7c makes the combinations too many.
  - **The [3.11.3] sector is centred on the vector from the flushed to the flushing thruster**, since pushing away from a thruster sends the race onto it. Figure A-4 / Table A-6 confirm this (port aft azimuth 80–100°).
  - **The boundary counts as allowed** ("less than" arctan(0.1 + D/s)).
  - **User zones** are a `Thruster` field in the Table A-6 format: thrust angles in degrees, [3.8.2] convention, counter-clockwise from start to end.
  - **Flushing sectors are found among the thrusters passed to `allocate_thrust`**, i.e. the working ones. Step 8 can pass a reduced set for a failure case.
  - **A tunnel or shaft line direction strictly inside a zone** is removed (limit 0).
- **Skeg loss** (step 7c, agreed with William 2026-09-28; details in `Descriptions/skeg_loss.md`):
  - **Several skegs take the minimum factor** per direction (no double counting where regions overlap).
  - **Port/starboard is relative to the skeg** (y_thr > y_skeg → Table 3-7), since the formulas use y_skeg − y_thr. y_thr = y_skeg gets no loss: behind the skeg by the text, and on neither side otherwise.
  - **"Above the base line" is z > 0.** Tunnels are exempt. Shaft lines use the factor at 0°/180°.
  - **The "polar" interpolation** is linear in θ between the table points (Figure 3-7), drawn with polygon corners every 1° (`RAMP_STEP_DEG`). The chords are inside the true curve, so the polygon is conservative.
  - **Capacity is a star polygon split into convex fans.** This replaces 7b's "36-gon + cone rows" pieces. Without zones or skeg it is exactly the 36-gon, and with zones only it reproduces 7b to 1e-14. Pass 2 measures |f| with a separate unit 36-gon.
- **Rudders** (step 7d, agreed with William 2026-09-29; details in `Descriptions/rudders.md` §3):
  - **k2 comes from an explicit flag**, `Rudder.behind_fixed_nozzle` (Table A-4 lists k2 separately), not from `Thruster.ducted`. A nozzle rudder turns its nozzle, so it gets k2 = 1.0 even on a ducted shaft line.
  - **A_r is an input**, with the chord already capped at 1.0D.
  - **α_max = min(maximum rudder angle, 30°).** Positive α gives sway to port (the standard leaves the sign open; the capacity is symmetric).
  - **Capacity = a fan ahead ∪ the −x segment astern**, as two pieces, not their convex hull: the propeller is either ahead or astern. The fan has corners every 1° of α, on the parabola, so it is conservative.
  - **Zones and β_skeg use the shaft direction** (0° ahead, 180° astern), as [3.11.3] defines the thrust direction through the propeller shaft.
  - **Only shaft lines** may have a rudder; anything else raises `ValueError`.
- **Power** (step 7e, agreed with William 2026-09-29; details in `Descriptions/power.md` §3):
  - **P = P_B · r^1.5** at a fraction r of the nominal thrust, from turning [3.9.2] around. The standard gives no part-load relation. r = 1 uses P_B, and r is the thrust before losses / nominal thrust (the Table A-8 "Utilization %").
  - **The LP draws r^1.5 as chords** every 0.05 (`POWER_STEP`). They lie above the curve, so power is overestimated by at most 0.002 P_B (conservative).
  - **Usable power = 90% of a switchboard's available power**; the electrical losses of [3.12.4] are inside the 10%. A prime mover driving a propeller directly (`electrical=False`) reserves nothing.
  - **Batteries count toward the switchboard's available power**, and the 10% applies to the whole bus.
  - **Table A-5 shares are fixed fractions.** A closed bus-tie is modelled as one source with the gen-sets of both switchboards.
  - **The 10% is taken per source.** A redundancy group is one or more sources, so it is also 10% per group.
  - **U = the higher of the thrust and the power demand**, each as a fraction of what is available, so "balanced" is still U ≤ 1.
  - **Power is optional** (`power_sources=None` = no limit, the old results).
- **Redundancy groups and failure runs** (step 8a, agreed with William 2026-09-29; details in `Descriptions/redundancy.md` §3):
  - **Redundancy groups are input** (`RedundancyGroup`), consistent with the DP FMEA ([2.4.8]). A failure run is the intact run with the group's thrusters and power sources removed.
  - **A split feed is capped at the remaining share.** A thruster that loses a share s of its Table A-5 supply keeps running with P_B' = (1 − s)·P_B. Its remaining shares are rescaled to 1, so its thrust drops to (1 − s)^(2/3).
    - This follows A.3.5: Table A-5 is "how much power each thruster can consume from each switchboard".
    - The power per newton is unchanged. T_Nominal in the ventilation formula and the Table A-8 utilisation use the reduced value.
  - **No silent removals.** Unknown names raise `ValueError`, and so does a thruster outside the group that would be left without power.
  - **"Within ±30°" includes 330° and 30°** and is measured from the bow only. The standard's example agrees: with Table A-1, Figure A-2 reports L1(9, 7, 5, 2), and A = 9 and C = 5 are exactly the 30° values.
  - **C and D come from the combined curve** (lowest per heading, [2.4.7]), which is the same as the lowest over all group cases ([2.5.4]).
  - **Without groups, C and D are NA** ([2.5.2]).
  - **A dead thruster's flushing sectors disappear** ([3.11.3] counts only working thrusters). So failure numbers are not forced to be ≤ intact, though for the test vessel they are.
- **Flushing a dead thruster** (step 8b, agreed with William 2026-09-29; details in `Descriptions/dead_flushing.md` §3):
  - **The sector is centred on the vector from the dead thruster to the flushing one**, so the race hits the dead one. This is the same reading as [3.11.3] (7b).
  - **Figure 3-6 is a straight line** from β·T at the centre to T at the sector edges, in Cartesian coordinates: β_dead(δ) = β sin φ / (sin(φ − |δ|) + β sin|δ|).
  - **Several dead thrusters: the lowest factor per direction**, as for skegs.
  - **Every kind of flushing thruster**, with the flushing thruster's D and `ducted` flag (a tunnel counts as open). Tunnels and shaft lines take the factor of their fixed directions, and a rudder shaft line takes that of its shaft direction.
  - **Dead = the group's thrusters.** A derated split-fed thruster is working.
  - **It multiplies β_skeg** in the polygon radius ([3.11.6]).
- **DP capability number** (`capability.py`, [2.2.2], [2.4.4]):
  - Each heading steps up from BF 1 and **stops at the first BF that fails**. The number is the BF before it.
  - u is not assumed to rise monotonically with BF, so a higher BF that happens to balance never counts.
  - BF 0 isn't tried (zero load). The cap is 11.
  - Headings are the run setting `config.HEADINGS_DEG` (0–350° in 10° steps, the [2.4.6] minimum).
- **Limiting wind speed for Level 1 = the Table 2-1 wind speed of the DP capability number** (agreed with William, 2026-09-22).
  - There is no interpolation between rows: Level 1 defines wind, current and waves together only at the Table 2-1 rows, and interpolating would add to the prescriptive method (§3.2.1).
  - The m/s plot therefore has the same shape as the number plot.
- **`config.THRUSTERS` is AZ1, AZ2, BT1 and BT2 only** (2026-09-28). The Veracity app only offers azimuths and tunnels for testing, so the retractable azimuth was removed to keep the comparison one-to-one (§4, §8).
- **Plots** (`plot_envelope`, `plot_envelopes`): the loop is closed back to the first heading, with straight lines between points ([2.4.6] allows linear interpolation for visualization). `r_max` is fixed at 11 / 32.6 m/s in `main.py`, so envelopes stay comparable between runs.
  - `main.py` draws Figure A-1 (intact + WCSF, with the notation in the title) in numbers and in m/s, and Figure A-2 (every loss case) in numbers.
  - Separate per-group plots for the appendices ([2.4.8]) are left for when results are saved to `output/` (8c).

Open:
- `Hull.bow_angle` is an input for now; it could be derived from waterline geometry later.
- `tests/models/test_environmental_loads.py` holds wind, current, wave and total-load tests together (51 tests). Split it per module if it gets harder to navigate.

## 8. Validation plan

§1.6.2 says DNV's web app on veracity.com computes Level 1. It hasn't been
checked yet whether the app is still available or needs a login. This has
**never been attempted**, and it is the only check that would catch a
formula that was mis-read from the standard the same way in both the code
and the tests.

The idea is to enter `config.HULL` there (plus thrusters once they are
defined) and compare step by step:
- **Table A-7** (environmental forces per heading) for steps 1–3. Now worth doing, since the load side is complete.
  - Table A-7 lists wind, current and wave force and moment **separately** per heading, each at that heading's DP capability number. Compare each row against `wind_loads_level1` / `current_loads_level1` / `wave_loads_level1` at the row's BF, not against the total.
  - The table template doesn't say whether its values include the 1.25 factor. Check whether they match the raw functions or 1.25 × them.
  - Because each row states its own BF, any thruster set that the app accepts will do.
- **Table A-3** (nominal thrust) for step 4. Can be done now: enter `config.THRUSTERS` and compare against the T_nom column in §4 (377.52 / 377.52 / 135.77 / 126.89 kN). Table A-3 shows one value per thruster, presumably forward;
- **Table A-6** (forbidden zones) for step 7b. Enter `config.THRUSTERS` and compare the app's forbidden zones with `forbidden_zones_level1(config.THRUSTERS)`: AZ1 69.56–110.44° (in [−180, 180]: 69.56 to 110.44), AZ2 249.56–290.44° (−110.44 to −69.56), none for the tunnels. This also checks our sign reading of [3.11.3].
- **Skeg loss** for step 7c. The app's numbers at 100°/260° (BF 6 with skeg loss, 7 without) are a direct check of Tables 3-7/3-8 and our readings (§7).
- **Rudders** (step 7d) can't be compared there, as the app only offers azimuths and tunnels for testing (§7). They rest on the hand-checked tests and the 2026-09-29 check of p. 34.
- **Failure runs** (step 8a), if the app can remove a switchboard with its thrusters.
  - Compare the per-heading numbers of the loss of SWBD 1 / SWBD 2 and `DP capability-L1(8, 6, 5, 3)`.
  - Our failure numbers include the §3.11.4 loss (8b). For the test vessel it changes no number, so a mismatch in the failure runs would point elsewhere, e.g. at how the app handles the group or its tunnel.
- **Table A-8** (thruster forces) for steps 5–7.
  - The §3.11.1 guidance note allows the analysis allocation to differ from the DP system's, and Veracity's method is unknown. Individual thruster forces may therefore differ from ours even when both are right.
  - Compare the DP capability numbers per heading first. They exist since step 6: run `main.py`, or see the table in `Descriptions/capability.md` §3. Our numbers include ventilation (7a), forbidden zones and flushing sectors (7b) and the skeg loss (7c), so for this azimuth-and-tunnel vessel the intact numbers should now match. (Flushing of a *dead* thruster, §3.11.4, only matters in failure cases, step 8.) A mismatch at 100°/260° (BF 6 with skeg loss, 7 without) would point at Tables 3-7/3-8. A mismatch at 160°/200° (BF 10 with ventilation, 11 without) would point at the ventilation formula or the T_Nominal reading. Then, where the numbers agree, compare which thrusters are at the limit. For the test vessel at beam, our forward group (BT1, BT2) saturates first.

## 9. Environment and workflow

- **Python:** the project `.venv` (Python 3.11.5) has exactly the pinned versions from `requirements.txt`: numpy 2.1.0, matplotlib 3.9.2, scipy 1.14.1, pytest 8.3.3. Run the tests with:
  ```
  ./.venv/Scripts/python.exe -m pytest tests -q
  ```
  The default `python` (Microsoft Store) and Anaconda base have older numpy/scipy and should not be used for this project. `.vscode/settings.json` still sets conda as the default environment manager, so select `.venv` as the interpreter in VS Code.
- Branch workflow is described in `README.md`: work on `william` or `olve`, and merge into `main` when ready. Commit messages have been in Norwegian so far.
- **The standard:** the DNV-ST-0111 PDF is not in git. `theory/` is git-ignored; on William's machine it holds `theory/DNV-ST-0111.pdf` (a copy is also at `Desktop/5/Prosjektoppgave/DNV-ST-0111.pdf`, one level above the repo).
  - The formulas and many tables are **images** in the PDF, so `pdftotext` drops them.
  - To read them, render the page. For example, install PyMuPDF into a scratch folder (not `.venv`) and use `page.get_pixmap(dpi=300)`. Printed page N is PyMuPDF's 0-based `doc[N - 1]` (§3.6–3.7 are on printed pages 26–27; §3.9 on 29–33, so `doc[28]`–`doc[32]`, with the ventilation formulas on 32–33; Table A-3 on 72).
