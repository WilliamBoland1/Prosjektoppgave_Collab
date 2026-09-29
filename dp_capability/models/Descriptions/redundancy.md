# Redundancy groups, failure runs and DP capability-L1(A, B, C, D) — DP capability Level 1

This document covers step 8a:
- `failure_case(...)` in `redundancy.py`;
- `failure_numbers_level1(...)`, `worst_case_numbers(...)`, `information_elements_level1(...)` and `capability_notation(...)` in `capability.py`;
- `plot_envelopes(...)` in `plotting/capability_plot.py`.

They map DNV-ST-0111 (Edition December 2021) [2.4.7], [2.4.8], [2.5] and App. A.3 to the code. All of it is text in the PDF (pages 13, 17–18, 67–69 and 77). Table A-1 was also checked with William on a 300 dpi crop (`SOURCES.md`).

## 1. Background

- **Table 1-5, WCSF:** worst case single failure, "failure modes which, after a failure, result in the largest reduction of the position and/or heading keeping capacity. This means loss of the most significant redundancy group, given the prevailing operation."
- **[2.4.7]:** "When presenting the result for the WCSF condition(s), an amalgamated plot shall be provided with the lowest result for each heading across all the redundancy groups." The guidance note says the WCSF will typically depend on the heading.
- **[2.4.8]:** the report shows three kinds of plot:
  - the intact vessel;
  - the combined plot (lowest per heading);
  - a plot for the failure of each redundancy group (in appendices).

  The redundancy groups "shall be consistent with the redundancy concept determined by the DP FMEA".
- **[2.5.1]:** the result is written `DP capability-LX(A, B, C, D)`:
  - A = the smallest DP capability number "within heading ±30° relative to the environmental forces", intact;
  - B = the smallest within 0–360°, intact;
  - C and D = the same two for "the worst case single failure condition relevant for the class notation".
- **[2.5.2]:** C and D are NA for non-redundant DP systems.
- **[2.5.4]:** a capability plot is calculated for the failure of each redundancy group. "C and D numbers shall be the lowest numbers obtained across all the redundancy group cases."
- **A.3.1** (p. 67) lists the executive-summary plots:
  - the intact vessel plus the combined plot (Figure A-1);
  - all redundancy groups in one plot (Figure A-2);
  - a per-heading table (Table A-1).
- **A.3.6** (p. 77): runs come in the order intact, each redundancy group, then any others.
- **A.3.5** (p. 73), Table A-5: "how much power each thruster can consume from each switchboard and/or prime mover".

## 2. Method

A redundancy group is **input**. It is what the DP FMEA says is lost together in one single failure: a name, the thrusters, and the power sources (`RedundancyGroup`).

```
for each group g:
    thrusters_g, sources_g = failure_case(thrusters, g, sources)      # what is left
    numbers_g = capability_numbers_level1(hull, thrusters_g, headings, power_sources=sources_g)
worst = lowest numbers_g per heading                                   # [2.4.7]
A = min intact over |heading| ≤ 30°,  B = min intact                    # [2.5.1]
C = min worst  over |heading| ≤ 30°,  D = min worst
```

**What is left** (`failure_case`):
- The group's thrusters and power sources are removed.
- A remaining thruster that took a share s of its power from a lost source keeps running on its other sources, but only up to their shares (decision 2):
  ```
  P_B' = (1 − s) · P_B,      shares' = shares / (1 − s)      (remaining sources only)
  T_Nominal' = T_Nominal · (1 − s)^(2/3)                        ([3.9.2]: T ~ P_B^(2/3))
  ```
- The power per newton does not change: P_B'·(T/T_Nominal')^1.5 = P_B·(T/T_Nominal)^1.5. So the cap only lowers the maximum thrust.

**Everything else is the intact machinery.** Ventilation, forbidden zones, skeg loss, rudders and power (steps 7a–7e) are computed for the thrusters and sources that are left. In particular, the flushing sectors of [3.11.3] only come from *working* thrusters, so a dead thruster stops blocking the others. Instead, a working thruster whose race hits a dead one loses thrust in that direction ([3.11.4], step 8b, `dead_flushing.md`).

## 3. Decisions (agreed with William, 2026-09-29)

1. **Redundancy groups are input**, consistent with the DP FMEA ([2.4.8]). A failure run is the intact run with the group's thrusters and sources removed.
2. **Split feed: capped at the remaining share.** This follows A.3.5's "how much power each thruster *can consume* from each switchboard".
   - The alternative, full power from the remaining source like a changeover, is less conservative. If a vessel really has a changeover, its Table A-5 row for that run can say so.
   - A side effect: T_Nominal in the ventilation formula ([3.9.4]) and the Table A-8 utilisation use the reduced nominal thrust.
3. **No silent removals.**
   - A group that names an unknown thruster or source raises `ValueError`.
   - So does a thruster outside the group that would have no power left. The group then contradicts Table A-5, and should list that thruster.
4. **"Within ±30°" includes the edges and is measured from the bow**: environment from 330° to 30°.
   - "Relative to the environmental forces" is the vessel heading relative to the weather, i.e. bow into it; the stern is not included.
   - The standard's own example supports the edges. With Table A-1, Figure A-2 reports L1(9, 7, 5, 2), and A = 9 and C = 5 are exactly the values at 30°.
5. **C and D come from the combined curve.** The lowest of all group curves within the sector is the same as the lowest group minimum ([2.5.4]).
6. **Without redundancy groups, C and D are NA** ([2.5.2]). `information_elements_level1(..., worst=None)` gives None, and `capability_notation` writes NA.
7. **Failure numbers are not forced to be ≤ intact.** A dead thruster's flushing sectors disappear. The [3.11.4] notch (step 8b) is narrower than the [3.11.3] sector it replaces, so this can in principle free directions for the others. For the test vessel every failure number is ≤ intact anyway.

## 4. Worked example: split feed

An open azimuth, D = 2 m, P_B = 1000 kW, fed 50% from S1 and 50% from S2. S1 is lost.

| | P_B [kW] | Table A-5 row | T_Nominal [kN] | T_eff = 0.9 · T_Nominal [kN] |
|---|---|---|---|---|
| Intact | 1000 | S1 50%, S2 50% | 120.99 | 108.89 |
| After loss of S1 | 500 | S2 100% | 120.99 · 0.5^(2/3) = 76.22 | 68.60 |

At its new full thrust (76.22 kN) it uses 500 kW. The intact thruster also needs 1000 · 0.630^1.5 = 500 kW for 76.22 kN, so the power curve is unchanged.

## 5. Checks and result

**Hand check** (tested): two azimuths on the centreline 40 m apart, head-on.
- Intact: 2T = 217.79 kN. BF 9 needs 168.63 kN and BF 10 needs 221.40 kN, so the number is **9**.
- Either one lost: T = 108.89 kN. BF 7 needs 82.34 kN and BF 8 needs 117.31 kN, so the number is **7**.

**Table A-1 of the standard** (tested): the combined column of the example is 9, 8, 6, 5 at 0–30°, and the sector values A = 9 and C = 5 match its Figure A-2 (decision 4).

### The test vessel (`config.py`)

`REDUNDANCY_GROUPS`:
- **SWBD 1**: SWBD 1, AZ1 and BT1;
- **SWBD 2**: SWBD 2, AZ2 and BT2.

The bus-tie is open and every thruster is 100% on one switchboard, so no split feeds.

**Result: DP capability-L1(8, 6, 5, 3).**

Since step 8b the runs include §3.11.4 (flushing a *dead* thruster, `dead_flushing.md`); it changes none of these numbers, see below.

| Heading [°] | Intact | Loss of SWBD 1 (AZ2 + BT2) | Loss of SWBD 2 (AZ1 + BT1) | Combined (WCSF) |
|---|---|---|---|---|
| 0 | 11 | 10 | 10 | 10 |
| 10 | 11 | 8 | 9 | 8 |
| 20 | 9 | 6 | 6 | 6 |
| 30 | 8 | 5 | 5 | 5 |
| 40 | 7 | 4 | 5 | 4 |
| 50 | 7 | 4 | 4 | 4 |
| 60 | 6 | 3 | 4 | 3 |
| 70 | 6 | 3 | 4 | 3 |
| 80 | 6 | 3 | 4 | 3 |
| 90 | 6 | 4 | 4 | 4 |
| 100 | 6 | 4 | 4 | 4 |
| 110 | 7 | 4 | 4 | 4 |
| 120 | 7 | 5 | 5 | 5 |
| 130 | 8 | 5 | 5 | 5 |
| 140 | 8 | 6 | 6 | 6 |
| 150 | 9 | 7 | 7 | 7 |
| 160 | 10 | 8 | 8 | 8 |
| 170 | 11 | 8 | 10 | 8 |
| 180 | 11 | 10 | 10 | 10 |
| 190 | 11 | 10 | 8 | 8 |
| 200 | 10 | 7 | 8 | 7 |
| 210 | 9 | 6 | 7 | 6 |
| 220 | 8 | 6 | 6 | 6 |
| 230 | 8 | 5 | 5 | 5 |
| 240 | 7 | 4 | 5 | 4 |
| 250 | 7 | 4 | 4 | 4 |
| 260 | 6 | 4 | 4 | 4 |
| 270 | 6 | 4 | 4 | 4 |
| 280 | 6 | 3 | 4 | 3 |
| 290 | 6 | 3 | 4 | 3 |
| 300 | 6 | 3 | 4 | 3 |
| 310 | 7 | 4 | 4 | 4 |
| 320 | 7 | 4 | 4 | 4 |
| 330 | 8 | 5 | 5 | 5 |
| 340 | 9 | 6 | 6 | 6 |
| 350 | 11 | 9 | 8 | 8 |

- **A = 8** (intact, 30° and 330°) and **B = 6** (intact, 60–100° and 260–300°), as before step 8.
- **C = 5**, at 30° and 330°. **D = 3**, at 60–80° and 280–300°, all from the loss of SWBD 1.
- **The loss of SWBD 1 is the WCSF at most headings.** It leaves BT2, whose broken inlet gives 126.89 kN against BT1's 135.77 kN (Table 3-2). The two cases are therefore close to mirror images, but not exact ones: e.g. 60° is 3 after losing SWBD 1, while 300° is 4 after losing SWBD 2. The loss of SWBD 2 is lower only at 190° and 350°.
- **The remaining tunnel is the limit** almost everywhere: its thrust fraction r equals u at the capability number. Only near head and stern seas (0° and 160–200°) does the azimuth limit.
  - Example, the loss of SWBD 1 at 90°: BF 4 holds with u = 0.981 (AZ2 r = 0.23, BT2 r = 0.98), and BF 5 fails with u = 1.379.
- **Close calls:** the loss of SWBD 1 fails BF 9 at 170° with u = 1.0011, and BF 4 at 300° with u = 1.005. The loss of SWBD 2 fails BF 7 at 20° with u = 1.0013. The 36-, 72- and 360-corner polygons all give the same u, so the polygon does not decide them.
- **Power** does not bind. Each remaining switchboard feeds only its own 2900 kW of thrusters (3240 kW usable).
- **Run time:** the two failure runs take about 2.4 s together, and `main.py` about 11 s in all (the intact run varies between 4 and 12 s with the machine's load).

**Flushing the dead azimuth (step 8b).**
- In the loss of SWBD 1, AZ2 pushes at 265–285° for loads from starboard (60–110°). That is inside the sector 249.6–290.4° which the working AZ1 used to block ([3.11.3]). Its race now goes onto the dead AZ1, 11 m away.
- §3.11.4 gives AZ2 (ducted, within 4D = 12 m of AZ1) a notch of ±5.45° around 270° with β = 0.581 at the centre. The loss of SWBD 2 mirrors this with AZ1 at 90°.
- At those headings the tunnel limits, so **no u and no number changes**. AZ2's own thrust fraction rises, e.g. from 0.227 to 0.355 at 90° BF 4 (`dead_flushing.md` §5).
- Until step 8b these numbers were computed without the notch. `failure_numbers_level1(..., dead_flushing=False)` still gives that version.

## 6. In the code

- `dp_capability/standard.py`: `BOW_SECTOR_DEG = 30.0` ([2.5.1]).
- `dp_capability/vessel.py`: `RedundancyGroup(name, thrusters=(), power_sources=())`, with names as in `Thruster.name` and `PowerSource.name`.
- `dp_capability/models/redundancy.py`: `failure_case(thrusters, group, power_sources=None) -> (thrusters, power_sources)`.
  - It keeps the original order and derates split-fed thrusters with `dataclasses.replace`.
  - With `power_sources=None` it still derates by the `power_supply` names and returns None for the sources.
- `dp_capability/models/capability.py`:
  - `failure_numbers_level1(hull, thrusters, headings_deg, groups, power_sources=None, dead_flushing=True, **options) -> {group name: numbers}`, in the order of the groups.
    - The group's thrusters are passed on as `dead_thrusters` for [3.11.4].
    - `options` takes `ventilation`, `forbidden_zones` and `skeg_loss`.
  - `worst_case_numbers(numbers)`: the lowest per heading over an iterable of arrays.
  - `information_elements_level1(headings_deg, intact, worst=None) -> (A, B, C, D)`: raises `ValueError` if no heading is within ±30°.
  - `capability_notation(a, b, c=None, d=None, level=1)`, e.g. `"DP capability-L1(8, 6, 5, 3)"`.
- `dp_capability/plotting/capability_plot.py`: `plot_envelopes(headings_deg, curves, title=None, r_max=None)`, where `curves` is `{label: values}`. It draws with a legend and the same axes as `plot_envelope`.
- `config.REDUNDANCY_GROUPS`; `main.py` runs intact → failures → combined and prints the notation. It then draws three plots:
  - intact + WCSF in numbers (Figure A-1, with the notation in the title);
  - the same in m/s;
  - every loss case in numbers (Figure A-2).
- **Not done yet:**
  - the report tables A-1 and A-7 to A-10 (8c);
  - saving the per-group plots (appendices, [2.4.8]) to files.
