# Current loads — DP capability Level 1

This document explains `current_loads_level1(...)` in `currentloads.py` and
maps the formulas of DNV-ST-0111 (Edition December 2021) [3.6] to the code.
The formulas below were checked against the PDF of the standard.

## 1. Background

Level 1 is prescriptive: the formulas "shall be strictly followed without
any deviations" ([3.2.1]). Like wind ([3.5], see `windloads.md` §5), the
current load is a quadratic drag with fixed coefficients. The current speed
is taken as uniform over depth ([3.3.2]) and coming from the same direction
as wind and waves ([3.3.1]).

### Coordinate system

DNV-ST-0111 [2.8.2]: `x` forward, `y` to **port**, `z` up, origin at `Lpp/2`
on the centreline at the keel. Forces are positive pushing the vessel
forward / to port, and the yaw moment is positive counter-clockwise (bow to
port). The current direction is where the current is coming **from**,
clockwise: `0°` = head-on, `90°` = from starboard.

## 2. Formulas

```
FX = ½ · ρ_water · V² · B · draft  · (−0.07 · cos(direction))
FY = ½ · ρ_water · V² · A_L,current · ( 0.6 · sin(direction))
MZ = FY · (x_L,current + max(min(0.4 · (1 − 2·dir/π), 0.25), −0.2) · Lpp)

dir = direction          for 0 ≤ direction ≤ π
      2π − direction     for π ≤ direction ≤ 2π

ρ_water = 1026 kg/m³
```

Two details that are easy to get wrong:

- **FX uses `B · draft`**, the midship section, not the frontal projected
  area `A_F,current`. Level 1 does not use `A_F,current` at all; it is kept
  in `Hull` only because Table A-2 lists it.
- **The lever factor is clipped asymmetrically**, to `[−0.2, 0.25]`. The
  unclipped factor `0.4·(1 − 2·dir/π)` runs from `+0.4` in head current to
  `−0.4` in stern current. The upper clip binds below `33.75°`, the lower one
  above `135°`, and in between the factor is linear.

The guidance note in [3.6] limits the formulas to moderate current speeds
(`V < 0.1·√(g·B)`). That mainly matters for Level X-site with non-standard
speeds: for `B = 18 m` the limit is 1.33 m/s, well above the Table 2-1
maximum of 0.75 m/s.

## 3. Checking the signs

- Head current (`0°`) gives `FX < 0`: the vessel is pushed aft.
- Current from starboard (`0° < direction < 180°`) gives `FY > 0`: the
  vessel is pushed to port.
- The centre of pressure `x_L,current + factor·Lpp` lies `0.25·Lpp` forward
  of the area centre in head and bow-quarter current and `0.2·Lpp` aft of it
  in stern-quarter and stern current. Current on the starboard bow therefore
  turns the bow to port (`MZ > 0`), and current on the starboard quarter
  turns it to starboard (`MZ < 0`). In beam current the lever is exactly
  `x_L,current`.
- `dir` folds port-side directions onto the starboard side, so the lever arm
  is the same on both sides, while `sin(direction)` flips the sign of `FY`
  and therefore of `MZ`.

### Worked example (the test hull)

`B = 18 m`, `draft = 6 m`, `A_L,current = 490 m²`, `x_L,current = −1.5 m`,
`Lpp = 80 m`, `V = 1 m/s`, so `q = ½·1026·1² = 513 Pa`:

| direction | FX [N] | FY [N] | lever [m] | MZ [Nm] |
|---|---|---|---|---|
| 0° | −3878.28 | 0 | — | 0 |
| 30° | −3358.689 | 75 411 | 18.5 (upper clip) | 1 395 103.5 |
| 45° | −2742.358 | 106 647.259 | 14.5 (no clip) | 1 546 385.255 |
| 90° | 0 | 150 822 | −1.5 (= x_L,current) | −226 233 |
| 150° | +3358.689 | 75 411 | −17.5 (lower clip) | −1 319 692.5 |
| 180° | +3878.28 | 0 | — | 0 |

These are the values in `tests/models/test_environmental_loads.py`.

## 4. In the code

The inputs come from the `Hull` dataclass in `dp_capability/vessel.py`
(`breadth`, `draft`, `al_current`, `xl_current`, `lpp`), and `ρ_water` and
the `dir` fold come from `dp_capability/standard.py` (`RHO_WATER`,
`fold_direction`). The clip is `np.clip(..., −0.2, 0.25)`, which is the same
as the standard's `max(min(..., 0.25), −0.2)`.

The function returns the unfactored forces [N] and moment [Nm]. The dynamic
factor of 1.25 ([3.2.2]) is applied once, to the sum of wind, current and
waves, in `environmental_loads_level1(...)` in `environmental_loads.py`.
