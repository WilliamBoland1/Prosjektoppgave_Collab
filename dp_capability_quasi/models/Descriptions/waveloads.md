# Wave drift loads — DP capability Level 1

This document explains `wave_loads_level1(...)` in `waveloads.py` and maps
the formulas of DNV-ST-0111 (Edition December 2021) [3.7] to the code. The
formulas below were checked against the PDF of the standard.

## 1. Background

Level 1 is prescriptive: the formulas "shall be strictly followed without
any deviations" ([3.2.1]). The wave drift formulas are an empirical fit of
the mean second-order drift force in a Pierson-Moskowitz sea with `cos²`
spreading ([3.3.3]). They depend on the sea state through two numbers:

- `Hs` — the force scales with `Hs²`;
- `Tp` — through `Tz = Tp / 1.4049` ([3.3.3]) and the period factor `f(T')`,
  which reduces the force in long waves that the vessel "rides" instead of
  reflecting.

The waves come from the same direction as wind and current ([3.3.1]).

### Coordinate system

DNV-ST-0111 [2.8.2]: `x` forward, `y` to **port**, `z` up, origin at `Lpp/2`
on the centreline at the keel. Forces are positive pushing the vessel
forward / to port, and the yaw moment is positive counter-clockwise (bow to
port). The wave direction is where the waves are coming **from**,
clockwise: `0°` = head seas, `90°` = from starboard.

## 2. Formulas

```
FX = ½ · ρ_water · g · Hs² · B   · 0.09 · h1 · h2           · f(T'surge)
FY = ½ · ρ_water · g · Hs² · Los · 0.09 · sin(direction)     · f(T'sway)
MZ = FY · (x_Los + (0.05 − 0.14 · dir/π) · Los)

h1  = h1A + (dir/π) · (h1B − h1A)
h1A = 0.8 · bow_angle^0.45
h1B = 0.7 · C_WLaft²
h2  = 0.05 + 0.95 · arctan(1.45 · (dir − 1.75))

C_WLaft = A_WLaft / (Lpp/2 · B),  clipped to [0.85, 1.15]

f(T') = 1                          if T' < 1
        T'^−3 · e^(1 − T'^−3)      if T' ≥ 1

T'surge = Tz / (0.9  · Lpp^0.33)
T'sway  = Tz / (0.75 · B^0.5)
Tz      = Tp / 1.4049

dir = direction          for 0 ≤ direction ≤ π
      2π − direction     for π ≤ direction ≤ 2π

ρ_water = 1026 kg/m³,  g = 9.81 m/s² (our choice, see below)
```

All angles are in radians, including `bow_angle` and the `dir − 1.75` in
`h2` (note under [2.8.3]).

- **`h1`** interpolates linearly in `dir` between the bow shape (`h1A`, from
  the bow angle, Figure 3-2) in head seas and the stern shape (`h1B`, from
  the aft waterplane fullness) in following seas.
- **`h2`** gives the direction dependence of the surge drift. It is `−1.086`
  in head seas and `+1.105` in following seas, and changes sign at
  `dir = 1.75 + tan(−0.05/0.95)/1.45 = 1.7137 rad = 98.2°`.
- **`f(T')`** is continuous: both branches give exactly `1` at `T' = 1`.
  Short waves (`T' < 1`) give the full drift force; above that it falls off.

### `g` is not given by the standard

[3.7] uses `g` but DNV-ST-0111 does not fix a value. We use `G = 9.81 m/s²`
in `dp_capability/standard.py`. This is recorded as a project decision in
`HANDOVER.md`.

### BF 0: calm sea

Table 2-1 gives `Hs = 0` and `Tp = NA` (stored as `nan`) for BF 0. With
`Hs = 0` the force is physically zero, but `0 · nan = nan` in floating point.
The function therefore sets all three outputs to exactly `0` wherever
`hs == 0`, with `np.where` so it stays vectorized. The `nan` in the branch
that is not selected is discarded without warnings.

## 3. Checking the signs

- Head seas (`0°`) give `h2 < 0` and so `FX < 0`: the vessel is pushed aft.
  Following seas give `FX > 0`. Beam seas (`90°`) still give a small
  `FX < 0`, since the sign change is at `98.2°`, abaft the beam.
- Waves from starboard (`0° < direction < 180°`) give `FY > 0`: the vessel
  is pushed to port. `FY` uses `sin(direction)`, **not** `dir`; that is what
  flips its sign for waves from port.
- The centre of pressure `x_Los + (0.05 − 0.14·dir/π)·Los` moves from
  `0.05·Los` forward of `x_Los` in head seas to `0.09·Los` aft of it in
  following seas. For the test hull, waves on the starboard bow turn the bow
  to port (`MZ > 0`) and waves on the starboard quarter turn it to starboard
  (`MZ < 0`).
- `dir` folds port-side directions onto the starboard side, so `h1`, `h2`
  and the lever arm are the same on both sides.

### Worked example (the test hull)

`B = 18 m`, `Lpp = 80 m`, `Los = 86 m`, `x_Los = −1 m`, `bow_angle = 0.4 rad`,
`A_WLaft = 648 m²` (`C_WLaft = 0.90`), `Hs = 2 m`, `Tp = 3.5 s`.

Then `Tz = 2.4913 s`, `T'surge = 0.6519` and `T'sway = 0.7829`. Both are below
1, so `f = 1` and the values can be checked by hand:

- `½ρg·Hs²·B·0.09 = 32 610.7944 N`
- `½ρg·Hs²·Los·0.09 = 155 807.1288 N`
- `h1A = 0.52968416`, `h1B = 0.567`

| direction | h1 | h2 | FX [N] | FY [N] | lever [m] | MZ [Nm] |
|---|---|---|---|---|---|---|
| 0° | 0.52968416 | −1.08562647 | −18 752.4833 | 0 | +3.30 | 0 |
| 90° | 0.54834208 | −0.19151201 | −3424.5931 | 155 807.1288 | −2.72 | −423 795.3903 |
| 135° | 0.55767104 | +0.73502681 | +13 367.2678 | 110 172.2773 | −5.73 | −631 287.1491 |
| 180° | 0.56700000 | +1.10515111 | +20 434.5981 | 0 | −8.74 | 0 |
| 270° | 0.54834208 | −0.19151201 | −3424.5931 | −155 807.1288 | −2.72 | +423 795.3903 |

At a longer period, `Hs = 4 m` and `Tp = 10 s`, the `T' ≥ 1` branch is used:
`T'surge = 1.8625` gives `f = 0.360409`, and `T'sway = 2.2370` gives
`f = 0.222088`. This gives `FX = −27 034.2779 N` at `0°` and
`FY = 138 411.5230 N`, `MZ = −376 479.3425 Nm` at `90°`.

These are the values in `tests/models/test_environmental_loads.py`.

## 4. In the code

The inputs come from the `Hull` dataclass in `dp_capability/vessel.py`
(`breadth`, `lpp`, `los`, `x_los`, `bow_angle`, `aw_laft`), and `ρ_water`,
`g`, the `Tp/Tz` ratio and the `dir` fold come from
`dp_capability/standard.py` (`RHO_WATER`, `G`, `TZ_FROM_TP`,
`fold_direction`). `f(T')` is the private helper `_period_factor(...)`.

Unlike wind and current, the function takes two sea-state parameters:
`wave_loads_level1(hull, hs, tp, direction_deg)`. It returns the unfactored
forces [N] and moment [Nm]. The dynamic factor of 1.25 ([3.2.2]) is applied
once, to the sum of wind, current and waves, in
`environmental_loads_level1(...)` in `environmental_loads.py`.
