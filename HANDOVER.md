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
| 5 | Force/moment balance (thrust allocation) at one heading | §2.4.4, §3.11.1 | **next** |
| 6 | Sweep headings × BF → first real capability plot (**first milestone**) | §2.4, §2.2.2 | |
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

**Tests:** 101 passing (`tests/test_standard.py`: 7, `tests/models/test_environmental_loads.py`: 51, `tests/models/test_thrust.py`: 43).

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
| `dp_capability/models/Descriptions/` | Theory write-ups: `windloads.md` (§5 = Level 1), `currentloads.md`, `waveloads.md`, `thrust.md`. Formulas, sign checks, worked examples, code mapping |
| `dp_capability/plotting/capability_plot.py` | `plot_envelope()` polar plot, north-up and clockwise, which matches §2.8.2. Still takes the old list-of-lists sample format |
| `main.py` | Still plots fake sample data; not connected to the models yet |
| `thruster_allocation.py`, `capability.py`, `io_utils.py`, `processing/clean.py` | Empty |

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
- **Rough capability estimate.** After β_misc, all five together give about 1000 kN of sway force. The factored beam load is about 358 kN at BF 6 and about 750 kN at BF 8, so expect roughly BF 8 in beam seas.
- **Step-7 losses will apply to this set:**
  - The aft azimuths are 4 m aft and 5.5 m outboard of the skeg's aftmost point (−36, 0), so the skeg losses of §3.11.5 apply.
  - They are also 11 m apart (< 15D), so the flushing rules of §3.11.3 apply.

## 5. Next step: force balance at one heading (§2.4.4, §3.11.1)

- **What must balance:** Fx, Fy and Mz at the same time (§2.4.4). The load is `environmental_loads_level1(hull, bf, direction_deg)`, already factored by 1.25.
- **Thrust available:** `effective_thrust(thruster, reverse)` from `thrust.py` (= nominal × 0.9 for now). Each thruster's force acts at (x, y), so its moment is `Mz = x·Fy − y·Fx`.
- **Suggested approach:** `scipy.optimize.linprog`, maximising λ such that the thrusters produce λ·(−τ_env). The heading is feasible if λ ≥ 1, and λ also gives the utilisation.
- **Thruster models:**
  - azimuth/pod: can point any way, so only forward thrust is needed. The circular limit becomes a polygon (e.g. 16–36 sides, inscribed so it stays conservative).
  - tunnel: force along ±y, `effective_thrust` both ways (the same for tunnels).
  - shaft propeller without rudder: force along ±x, reverse with `reverse=True`.
  - cycloidal: any direction, like an azimuth.
- **Actuator angle** (§3.8.2): 0° pushes forward, increasing counter-clockwise, so 90° pushes to port. Report angles this way (Table A-8).
- **Not yet:** forbidden zones, flushing, skeg losses, ventilation, rudders and power limits all belong to step 7.
- **Where the code goes:** `thruster_allocation.py` (empty now) and `tests/models/test_thruster_allocation.py`.
- **Tests:** use hand-checkable layouts. Examples: two tunnels only with a pure sway load, and one azimuth at the origin with a pure surge load.

## 6. Later steps: notes and gotchas

**Step 5: force balance** (see §5)
- The direction-dependent losses and forbidden zones in step 7 make the problem non-convex. At that point, move to `scipy.optimize.milp` or split each thruster's range into convex sectors.

**Step 6: sweep**
- For 36 headings, try BF 0, 1, 2, … until the first failure. The capability number is the last BF that balances, and every lower BF must also balance (§2.2.2, §3.2.2).
- `environmental_loads_level1` takes `bf` directly and is vectorized over direction, so one call per BF gives the whole envelope.
- Change `plot_envelope()` to take (headings, values) instead of the sample list format.

**Step 7: refinements**
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
