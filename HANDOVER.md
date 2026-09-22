# Handover: DP capability Level 1 (DNV-ST-0111)

_Last updated 2026-09-22, branch `william`. Written at the end of a Claude Code session with William._

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
| 6 | Sweep headings × BF → first real capability plot (**first milestone**) | §2.4, §2.2.2 | **next** |
| 7 | Refinements: ventilation, rudders, flushing/skeg losses, forbidden zones, power | §3.9.4, §3.10, §3.11.2–5, §3.12 | |
| 8 | Redundancy groups, worst single failure, `DP capability-L1(A,B,C,D)`, report tables | §2.4.7–2.5, App. A | |

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

**Tests:** 121 passing (`tests/test_standard.py`: 7, `tests/models/test_environmental_loads.py`: 51, `tests/models/test_thrust.py`: 43, `tests/models/test_thruster_allocation.py`: 20).

## 3. Conventions: read before writing any formula

These come from DNV-ST-0111 §2.8.2 and are written down once, in the module
docstring of `dp_capability/standard.py`.

- **Body frame:** x forward, y to **port**, z up. Origin at Lpp/2, on the centreline, at the keel.
- **Signs:** forces are positive forward and to port. The yaw moment is positive counter-clockwise (bow to port). A force at (x, y) gives `Mz = x·Fy − y·Fx`.
- **Environment direction:** where the wind, current or waves come **from**, measured clockwise. 0° = head-on, 90° = from starboard, 180° = astern, 270° = from port.
- **Units:** SI. Public functions take directions in **degrees** and convert to radians internally (the formulas use radians, note under §2.8.3). Exceptions:
  - the rudder angle α in §3.10 is in degrees;
  - `Thruster.power_kw` is in kW, because the §3.9.2 formula wants kW.
- **`dir` fold:** use `standard.fold_direction()`, which keeps the direction if it is ≤ π and otherwise returns 2π − direction. Wind (§3.5), current (§3.6) and waves (§3.7) all use it, but **only** for `dir` terms (lever arms, `h1`, `h2`), never inside `sin(direction)`, which is what flips the sign of FY for port-side directions.
- **Where numbers live:**
  - Values the standard fixes go in `standard.py`: `RHO_AIR = 1.226`, `RHO_WATER = 1026.0`, `TZ_FROM_TP = 1.4049`, `DYNAMIC_FACTOR_LEVEL1 = 1.25`, Tables 3-1 to 3-4 (`ETA1`, `ETA2_TUNNEL`, `ETA2_FORWARD`, `ETA2_REVERSED`, `ETA_M`), `BETA_MISC = 0.9`, and our choice `G = 9.81`.
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
| `dp_capability/standard.py` | The conventions docstring and constants. `BeaufortCondition` + `ENVIRONMENT_TABLE` (Table 2-1, BF 0–11; BF 0 has `tp = nan`). `environment(bf)` raises ValueError outside 0–11. `fold_direction()`. Tables 3-1 to 3-4 as dicts, `BETA_MISC` |
| `dp_capability/vessel.py` | `Hull` frozen dataclass matching Table A-2: `loa, lpp, draft, breadth, los, x_los, bow_angle [rad], aw_laft, af_wind, al_wind, xl_air, af_current, al_current, xl_current, skegs`. `Thruster` frozen dataclass matching Table A-3: `name, kind, diameter, power_kw, x, y, z, pitch="FPP", ducted, permanent_magnet, contra_rotating, tunnel_inlet` |
| `dp_capability/config.py` | `HULL`: a made-up ~80 m OSV. `THRUSTERS`: its five actuators (both below) |
| `dp_capability/models/thrust.py` | `nominal_thrust(thruster, reverse=False)` [N] and `effective_thrust(thruster, reverse=False, beta_t=BETA_MISC)` [N]. Row pickers `_eta1`, `_eta2`, `_eta_m` (rules in §7). Plain floats, nothing here depends on direction |
| `dp_capability/models/windloads.py` | Blendermann (unchanged) + `wind_loads_level1(hull, wind_speed, direction_deg) -> (fx, fy, mz)` |
| `dp_capability/models/currentloads.py` | `current_loads_level1(hull, current_speed, direction_deg) -> (fx, fy, mz)`. FX uses `breadth · draft` (Level 1 does not use `af_current`); lever factor clipped to [−0.2, 0.25] |
| `dp_capability/models/waveloads.py` | `wave_loads_level1(hull, hs, tp, direction_deg) -> (fx, fy, mz)` and the helper `_period_factor()` = f(T'). Returns exactly 0 where `hs == 0` (BF 0 has `tp = nan`) |
| `dp_capability/models/environmental_loads.py` | `environmental_loads_level1(hull, bf, direction_deg, dynamic_factor=1.25)`: looks up Table 2-1, sums wind + current + waves, multiplies by the dynamic factor |
| `dp_capability/models/thruster_allocation.py` | `allocate_thrust(thrusters, load, n_sides=36) -> Allocation` for **one** heading (not vectorized). `Allocation` has `fx`, `fy` per actuator [N], `utilisation`, and the properties `feasible` (u ≤ 1 + `TOLERANCE`) and `angle_deg` ([3.8.2], nan when idle). Helpers `_capacity_rows`, `_solve` |
| `dp_capability/models/Descriptions/` | Theory write-ups: `windloads.md` (§5 = Level 1), `currentloads.md`, `waveloads.md`, `thrust.md`, `thruster_allocation.md`. Formulas, sign checks, worked examples, code mapping |
| `dp_capability/plotting/capability_plot.py` | `plot_envelope()` polar plot, north-up and clockwise, which matches §2.8.2. Still takes the old list-of-lists sample format |
| `main.py` | Still plots fake sample data; not connected to the models yet |
| `capability.py`, `io_utils.py`, `processing/clean.py` | Empty |

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

A typical PSV layout: two azimuths aft, two bow tunnels and a retractable
azimuth. Positions are in the §2.8.2 frame (y to port, z up from the keel).
`power_kw` is the documented DP power with torque limits, so the 50%-MCR
fallback doesn't apply.

| Name | Kind | D [m] | P_B [kW] | Pitch | Ducted | Inlet | x, y, z [m] | T_nom fwd / rev [kN] |
|---|---|---|---|---|---|---|---|---|
| AZ1 | azimuth, aft port | 3.0 | 2000 | FPP | yes | – | −40, +5.5, 1.8 | 377.52 / 264.26 |
| AZ2 | azimuth, aft stbd | 3.0 | 2000 | FPP | yes | – | −40, −5.5, 1.8 | 377.52 / 264.26 |
| BT1 | tunnel | 2.0 | 900 | CPP | – | rounded | +31, 0, 2.5 | 135.77 / 135.77 |
| BT2 | tunnel | 2.0 | 900 | CPP | – | broken | +28, 0, 2.5 | 126.89 / 126.89 |
| RAZ | retractable azimuth | 1.8 | 800 | FPP | no | – | +22, 0, −1.5 | 97.20 / 87.48 |

- **Different inlets and an open RAZ on purpose.** Real retractable azimuths are usually ducted. This way the Veracity comparison covers several rows of Tables 3-1 to 3-3.
- **Beam capability is BF 7** (step 5 result). At 90°, u = 0.587 at BF 6, 0.826 at BF 7 and 1.106 at BF 8.
  - The earlier rough estimate of "BF 8" added up all sway thrust (≈ 1000 kN) and ignored the moment balance.
  - The forward group (BT1, BT2, RAZ: 324 kN at x ≈ 27.5 m) has to match the moment of the aft azimuths at x = −40 m. Even a pure 664 kN sway load with no moment gives u = 1.055.
  - Worked example with all forces: `Descriptions/thruster_allocation.md` §3.
- **Step-7 losses will apply to this set:**
  - The aft azimuths are 4 m aft and 5.5 m outboard of the skeg's aftmost point (−36, 0), so the skeg losses of §3.11.5 apply.
  - They are also 11 m apart (< 15D), so the flushing rules of §3.11.3 apply.

## 5. Next step: sweep headings × BF → first capability plot (§2.4, §2.2.2)

This is the **first milestone**: a real DP capability plot for `config.HULL` with `config.THRUSTERS`.

- **What the standard asks:**
  - §2.2.2: the DP capability number means station keeping holds in that BF's condition **and all conditions below**, but not in the next one.
  - §2.4.4: start with the lowest environment and step up until the first limiting condition.
  - §2.4.6: at least 10° resolution over the full 360°. So use 36 headings, 0–350°.
- **Per heading:** try BF 1, 2, … 11. The capability number is the last BF before the first one with `allocate_thrust(...).feasible == False`. If every BF balances, it is 11; if BF 1 already fails, it is 0. BF 0 always balances (u = 0).
- **Building blocks:**
  - `environmental_loads_level1(hull, bf, headings)` is vectorized over direction, so one call per BF gives the loads for all 36 headings.
  - `allocate_thrust(thrusters, (fx[i], fy[i], mz[i]))` is **not** vectorized: loop over headings. All 12 BF × 36 headings take about 0.9 s, so stopping early at the first failure is optional.
  - The load elements come back as numpy scalars; `allocate_thrust` accepts them.
- **Where the code goes:** `dp_capability/models/capability.py` (empty now), e.g. `capability_numbers_level1(hull, thrusters, headings_deg) -> int array`. Tests go in `tests/models/test_capability.py`, with their own hull and thrusters.
- **Plot:** change `plot_envelope()` to take (headings, values) instead of the sample list format. Then connect `main.py`: config → capability numbers → plot.
- **Expected result for the test vessel:** BF 7 at 90° and 270° (§4). The envelope should be port/starboard symmetric (`number(360 − θ) == number(θ)`), which is a good test.
- **Test ideas:**
  - A thruster set too weak for BF 1 gives 0 everywhere.
  - A very strong set gives 11 everywhere.
  - Symmetry, as above.
  - The number never exceeds a BF that fails.
- **Also §2.4.2:** a plot in limiting wind speed [m/s] is required too. How to get m/s between Table 2-1 rows is still open (§7). The simplest first version plots the Table 2-1 wind speed of the capability number.

## 6. Later steps: notes and gotchas

**Step 7: refinements**
- The direction-dependent losses and forbidden zones make the allocation non-convex. At that point, move to `scipy.optimize.milp`, or split each thruster's range into convex sectors and solve one LP per combination. `_capacity_rows()` in `thruster_allocation.py` is where each actuator's set is built.
- Ventilation (§3.9.4) uses Φ = the standard normal CDF (`scipy.stats.norm.cdf`), and its `B` term wants the direction in [−π, π].
- Total loss factor: β_T = β_misc · β_vent · β_flushing,dead · β_flushing,skeg (§3.11.6).
- Rudders (§3.10): only count when behind positive thrust; α in degrees, capped at 30°.
- Power (§3.12): reserve 10% of generated power per redundancy group. Electrical losses are included in that 10%.

**Step 8: capability numbers**
- A = lowest BF within ±30° (intact). B = lowest over 0–360° (intact).
- C and D are the same for the worst single failure. They are NA for non-redundant systems.
- Combined worst-failure plot = the lowest value per heading across all redundancy groups (§2.4.7).

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
- **Thrust allocation** (`thruster_allocation.py`; §3.11.1 prescribes no method):
  - **Two LPs** with `scipy.optimize.linprog` (HiGHS), agreed with William.
    - Pass 1 minimises the utilisation u. This is the same problem as HANDOVER's earlier "maximise λ" (u = 1/λ), but BF 0 gives u = 0 instead of an unbounded LP.
    - Pass 2 keeps u and minimises total thrust, so that actuators with room to spare don't push against each other. That makes the forces and angles usable for Table A-8.
  - **Azimuths, pods and cycloidals** push any way, with forward thrust only. They use an inscribed **36-gon** (`n_sides`, a keyword argument, not in `standard.py`), with corners every 10° from 0°. It is at most 0.4% conservative.
  - **Tunnels** push along ±y. **Shaft lines** push along ±x with reversed thrust aft; rudders come in step 7.
  - **Feasible means u ≤ 1 + 10⁻⁶** (`TOLERANCE`). Pass 2 may use the same slack.
  - An unreachable load (e.g. tunnels only against surge) gives u = ∞ and `nan` forces, not an exception.

Open:
- `T_Nominal` in the ventilation formula: maximum nominal thrust or the commanded thrust?
- Limiting wind speed in m/s between Table 2-1 rows (needed for the m/s plot): which interpolation?
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
- **Table A-3** (nominal thrust) for step 4. Can be done now: enter `config.THRUSTERS` and compare against the T_nom column in §4 (377.52 / 377.52 / 135.77 / 126.89 / 97.20 kN). Table A-3 shows one value per thruster, presumably forward;
- **Table A-8** (thruster forces) for steps 5–7.
  - The §3.11.1 guidance note allows the analysis allocation to differ from the DP system's, and Veracity's method is unknown. Individual thruster forces may therefore differ from ours even when both are right.
  - Compare the DP capability numbers per heading first (step 6). Then, where the numbers agree, compare which thrusters are at the limit. For the test vessel at beam, our forward group (BT1, BT2, RAZ) saturates first.

## 9. Environment and workflow

- **Python:** the project `.venv` (Python 3.11.5) has exactly the pinned versions from `requirements.txt`: numpy 2.1.0, matplotlib 3.9.2, scipy 1.14.1, pytest 8.3.3. Run the tests with:
  ```
  ./.venv/Scripts/python.exe -m pytest tests -q
  ```
  The default `python` (Microsoft Store) and Anaconda base have older numpy/scipy and should not be used for this project. `.vscode/settings.json` still sets conda as the default environment manager, so select `.venv` as the interpreter in VS Code.
- Branch workflow is described in `README.md`: work on `william` or `olve`, and merge into `main` when ready. Commit messages have been in Norwegian so far.
- **The standard:** the DNV-ST-0111 PDF is not in git. `theory/` is git-ignored; on William's machine it holds `theory/DNV-ST-0111.pdf` (a copy is also at `Desktop/5/Prosjektoppgave/DNV-ST-0111.pdf`, one level above the repo).
  - The formulas and many tables are **images** in the PDF, so `pdftotext` drops them.
  - To read them, render the page. For example, install PyMuPDF into a scratch folder (not `.venv`) and use `page.get_pixmap(dpi=300)`. Printed page N is PyMuPDF's 0-based `doc[N - 1]` (§3.6–3.7 are on printed pages 26–27; §3.9 on 29–32, so `doc[28]`–`doc[31]`; Table A-3 on 72).
