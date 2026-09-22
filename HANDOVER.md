# Handover: DP capability Level 1 (DNV-ST-0111)

_Last updated 2026-09-16, branch `william`. Written at the end of a Claude Code session with William._

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
| 0 | Foundations: conventions, Table 2-1, `Hull` dataclass, test vessel | §2.8.2, Table 2-1, Table A-2 | done, **not committed** |
| 1 | Level 1 wind loads | §3.5 | done, **not committed** |
| 2 | Current loads | §3.6 | **next** |
| 3 | Wave drift loads | §3.7 | |
| 4 | Nominal thrust + β_misc | §3.9.1–3.9.3 | |
| 5 | Force/moment balance (thrust allocation) at one heading | §2.4.4, §3.11.1 | |
| 6 | Sweep headings × BF → first real capability plot (**first milestone**) | §2.4, §2.2.2 | |
| 7 | Refinements: ventilation, rudders, flushing/skeg losses, forbidden zones, power | §3.9.4, §3.10, §3.11.2–5, §3.12 | |
| 8 | Redundancy groups, worst single failure, `DP capability-L1(A,B,C,D)`, report tables | §2.4.7–2.5, App. A | |

**Tests:** 16 passing (`tests/test_standard.py`, `tests/models/test_environmental_loads.py`).

**Uncommitted files for steps 0–1:**

```
new:       dp_capability/standard.py
new:       dp_capability/vessel.py
new:       tests/test_standard.py
modified:  dp_capability/config.py
modified:  dp_capability/models/windloads.py
modified:  dp_capability/models/Descriptions/windloads.md
modified:  tests/models/test_environmental_loads.py
modified:  STRUCTURE.md
new:       HANDOVER.md (this file)
```

## 3. Conventions: read before writing any formula

These come from DNV-ST-0111 §2.8.2 and are written down once, in the module
docstring of `dp_capability/standard.py`.

- **Body frame:** x forward, y to **port**, z up. Origin at Lpp/2, on the centreline, at the keel.
- **Signs:** forces are positive forward and to port. The yaw moment is positive counter-clockwise (bow to port). A force at (x, y) gives `Mz = x·Fy − y·Fx`.
- **Environment direction:** where the wind, current or waves come **from**, measured clockwise. 0° = head-on, 90° = from starboard, 180° = astern, 270° = from port.
- **Units:** SI. Public functions take directions in **degrees** and convert to radians internally (the formulas use radians, note under §2.8.3). Exception: the rudder angle α in §3.10 is in degrees.
- **`dir` fold:** use `standard.fold_direction()`, which keeps the direction if it is ≤ π and otherwise returns 2π − direction. Wind (§3.5), current (§3.6) and waves (§3.7) all use it.
- **Where numbers live:**
  - Values the standard fixes go in `standard.py`: `RHO_AIR = 1.226`, `RHO_WATER = 1026.0`, `DYNAMIC_FACTOR_LEVEL1 = 1.25`.
  - Vessel values go in `config.py`.
  - Functions never hard-code either.
- **Vectorized:** functions are numpy-vectorized over direction, so one call can evaluate a whole envelope.

**Blendermann is not Level 1.** `blendermann_wind_coefficients()` in
`windloads.py` is a Level 2/3 method (§4.6.3, §6.7.1). It also uses y to
**starboard** and ρ_air = 1.23. Keep it for later comparisons, but don't mix
it into the Level 1 chain.

## 4. What exists now

| File | Contents |
|---|---|
| `dp_capability/standard.py` | The conventions docstring and constants. `BeaufortCondition` + `ENVIRONMENT_TABLE` (Table 2-1, BF 0–11; BF 0 has `tp = nan`). `environment(bf)` raises ValueError outside 0–11. `fold_direction()` |
| `dp_capability/vessel.py` | `Hull` frozen dataclass matching Table A-2: `loa, lpp, draft, breadth, los, x_los, bow_angle [rad], aw_laft, af_wind, al_wind, xl_air, af_current, al_current, xl_current, skegs` |
| `dp_capability/config.py` | `HULL`: a made-up ~80 m OSV (see below) |
| `dp_capability/models/windloads.py` | Blendermann (unchanged) + `wind_loads_level1(hull, wind_speed, direction_deg) -> (fx, fy, mz)` |
| `dp_capability/models/Descriptions/windloads.md` | Theory write-up. Section 5 covers Level 1 and how its frame differs from Blendermann's |
| `dp_capability/plotting/capability_plot.py` | `plot_envelope()` polar plot, north-up and clockwise, which matches §2.8.2. Still takes the old list-of-lists sample format |
| `main.py` | Still plots fake sample data; not connected to the models yet |
| `currentloads.py`, `waveloads.py`, `thruster_allocation.py`, `capability.py`, `io_utils.py`, `processing/clean.py` | Empty |

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

Sanity check at BF 6 (13.8 m/s): head-on Fx = −22.9 kN; at 90°, Fy = 73.5 kN and Mz = 882.6 kNm.

The tests build their **own** round-number hull, so changing `config.HULL`
never breaks them.

## 5. Next step: current loads (§3.6)

Add `current_loads_level1(hull, current_speed, direction_deg) -> (fx, fy, mz)`
to `dp_capability/models/currentloads.py`, following the same pattern as
`wind_loads_level1`:

```
FX = ½·ρ_water·V²·B·draft·(−0.07·cos(direction))
FY = ½·ρ_water·V²·A_L,current·(0.6·sin(direction))
MZ = FY·(x_L,current + max(min(0.4·(1 − 2·dir/π), 0.25), −0.2)·Lpp)
```

FX uses `breadth · draft`, **not** `af_current`.

Suggested test values, worked out by hand for this handover; re-check them
when writing the tests. Inputs: B = 18 m, draft = 6 m, A_L,current = 490 m²,
x_L,current = −1.5 m, Lpp = 80 m, V = 1 m/s, so q = ½·1026·1² = 513 Pa.

| Direction | Expected | Why this point |
|---|---|---|
| 0° | FX = −3878.28 N, FY = MZ = 0 | head-on |
| 30° | FY = 75411 N, MZ = 1 395 103.5 Nm | upper clamp 0.25 → lever 18.5 m |
| 45° | MZ ≈ 1 546 385 Nm | no clamp (0.2) → lever 14.5 m |
| 90° | FY = 150 822 N, MZ = −226 233 Nm | lever = x_L,current = −1.5 m |
| 150° | MZ = −1 319 692.5 Nm | lower clamp −0.2 → lever −17.5 m |
| 180° | FX = +3878.28 N | astern |

Also add the same symmetry, sign, V² and array-shape tests as for wind.

## 6. Later steps: notes and gotchas

**Step 3: waves (§3.7)**
- Tz = Tp / 1.4049 (§3.3.3). The standard gives no value for g: pick one (e.g. 9.81) and put it in `standard.py`.
- BF 0 has `hs = 0` and `tp = nan`. Return zero force explicitly, because nan·0 = nan.
- Derived parameters:
  - C_WLaft = aw_laft / (Lpp/2 · B), clamped to [0.85, 1.15];
  - h1A = 0.8·bow_angle^0.45 and h1B = 0.7·C_WLaft²;
  - h1 = h1A + (dir/π)·(h1B − h1A);
  - h2 = 0.05 + 0.95·arctan(1.45·(dir − 1.75)), in radians.
- f(T') = 1 if T' < 1, otherwise T'^−3 · e^(1 − T'^−3). T'surge = Tz / (0.9·Lpp^0.33) and T'sway = Tz / (0.75·B^0.5).
- Forces:
  - FX = ½ρg·Hs²·B·0.09·h1·h2·f(T'surge)
  - FY = ½ρg·Hs²·Los·0.09·sin(direction)·f(T'sway)
  - MZ = FY·(x_Los + (0.05 − 0.14·dir/π)·Los)
- Sanity check: h2 < 0 at 0° (vessel pushed aft) and h2 > 0 at 180°.

**Step 4: thrust (§3.9)**
- Add a `Thruster` dataclass (Table A-3) to `vessel.py` with: type, D, P_B [kW], FPP/CPP, ducted, permanent magnet, contra-rotating, tunnel inlet shape, and x/y/z position.
- T_nominal [N] = η1·η2·(D·P)^(2/3), where P = P_B·η_M in kW.
  - η1: Table 3-1.
  - η2: Tables 3-2 and 3-3, including reverse thrust.
  - η_M: Table 3-4.
- β_misc = 0.9 (§3.9.3).
- If torque limits aren't documented, 50% of MCR may be used as P_B (guidance note 3 in §3.9.2).

**Step 5: force balance**
- Fx, Fy and Mz must balance at the same time (§2.4.4).
- Suggested approach: `scipy.optimize.linprog`, maximising λ such that the thrusters produce λ·(−τ_env). The heading is feasible if λ ≥ 1, and λ also gives the utilisation.
- Thruster models:
  - azimuth: circular limit approximated by a polygon;
  - tunnel: force along y within its limits;
  - shaft propeller: x only, with reverse thrust reduced by η2.
- The direction-dependent losses and forbidden zones in step 7 make the problem non-convex. At that point, move to `scipy.optimize.milp` or split each thruster's range into convex sectors.

**Step 6: sweep**
- For 36 headings, try BF 0, 1, 2, … until the first failure. The capability number is the last BF that balances, and every lower BF must also balance (§2.2.2, §3.2.2).
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

## 7. Open decisions (write down the choice when made)

- Value of g for wave drift (not given in the standard).
- `T_Nominal` in the ventilation formula: maximum nominal thrust or the commanded thrust?
- Limiting wind speed in m/s between Table 2-1 rows (needed for the m/s plot): which interpolation?
- `Hull.bow_angle` is an input for now; it could be derived from waterline geometry later.
- `tests/models/test_environmental_loads.py` will hold wind, current and wave tests together; split it per module if it gets long.

## 8. Validation plan

§1.6.2 says DNV's web app on veracity.com computes Level 1. It hasn't been
checked yet whether the app is still available or needs a login.

The idea is to enter `config.HULL` there (plus thrusters once they are
defined) and compare step by step:
- **Table A-7** (environmental forces per heading) for steps 1–3;
- **Table A-3** (nominal thrust) for step 4;
- **Table A-8** (thruster forces) for steps 5–7.

## 9. Environment and workflow

- **Python environments:**
  - The default `python` (3.11, Microsoft Store) has numpy 1.26 and scipy 1.11, but **no pytest**.
  - The tests were run with Anaconda base (3.11.5, pytest 7.4): `C:\Users\willi\anaconda3\python.exe -m pytest tests -v`
  - VS Code is set to use conda.
- `requirements.txt` pins numpy 2.1.0, matplotlib 3.9.2, scipy 1.14.1 and pytest 8.3.3. These versions haven't been installed in either environment yet.
- Branch workflow is described in `README.md`: work on `william` or `olve`, and merge into `main` when ready. Commit messages have been in Norwegian so far.
- The DNV-ST-0111 PDF is not in git (`theory/` is git-ignored), so each person needs a local copy.
