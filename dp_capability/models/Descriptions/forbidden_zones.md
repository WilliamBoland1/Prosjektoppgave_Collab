# Forbidden zones — DP capability Level 1

This document explains `forbidden_zones.py` and how `allocate_thrust(...)`
handles forbidden zones. It maps DNV-ST-0111 (Edition December 2021) [3.11.2]
and [3.11.3] to the code. The rules are text on PDF pages 35–36, except the
sector formula, which is an image. It was transcribed from a 300 dpi crop
and checked with William.

## 1. Background

What the standard requires:
- **[3.11.2]:** "Forbidden zones and other possible limitations in the thrust allocation shall be specified in the report in the form of a figure and in a table, and the effects of these forbidden zones shall be included in the calculations."
  - Guidance note: such zones may be caused by e.g. an azimuth thrusting into rudders or working actuators.
  - App. A (p. 74) shows the format: Figure A-4 and **Table A-6**, with start and end angle per thruster. The zones "refer to the thrust-vector".
- **[3.11.3]:** a thruster flushing a *working* thruster.
  - Thruster i flushes thruster j "if the angle between the thrust direction … and the vector from the flushed thruster to the flushing thruster is less than arctan(0.1 + 1.0D/s) [deg]".
  - D is the diameter of the flushing thruster and s the horizontal distance between them. All angles and lengths are in the horizontal plane.
  - "A thruster is not allowed to flush a working thruster closer than 15D, unless the flushed thruster is a tunnel thruster."

Not here:
- **Flushing a dead thruster ([3.11.4])** is a thrust loss, not a zone, and dead thrusters only exist in failure cases (step 8).
- **The skeg ([3.11.5])** is also a loss. The change log (p. 90) says its formula "replaces the requirement for thrust forbidden zones toward skegs". That is step 7c.

## 2. Formulas

All angles are thrust angles in the [3.8.2] convention: 0° pushes forward,
increasing counter-clockwise, so 90° pushes to port.

For each pair (i flushing, j flushed) of working thrusters, where j is not a
tunnel:

```
s = √((x_i − x_j)² + (y_i − y_j)²)
if s < 15 · D_i:
    centre = atan2(y_i − y_j, x_i − x_j)        direction of the vector from j to i
    half   = arctan(0.1 + D_i / s)
    zone   = (centre − half, centre + half)
```

**Why the vector points from j to i.** The thrust force is opposite to the
propeller race. A thruster pushing *away* from j sends its race *towards* j.
Figure A-4 / Table A-6 confirm the sign. There the port aft azimuth (THR 4)
has 80–100° (pushing to port throws its race onto THR 5 on starboard), and
THR 5 has −100 to −80°.

User zones (`Thruster.forbidden_zones`) are added to these. They are
normalised to start in [0, 360) and merged where they overlap. A zone through
0° keeps an end above 360, e.g. (350, 370).

**Boundaries are allowed.** [3.11.3] forbids angles "less than" the half-angle,
so the zone is open. That fits the closed constraints of the LP.

## 3. Checks

- **Half-angle:** D = 2, s = 10 gives arctan(0.3) = 16.70°. D = 3, s = 11 gives arctan(0.3727) = 20.44°.
- **Side by side** at y = ±5: the port thruster may not push around 90°, the starboard one around 270° (Figure A-4).
- **In line** at x = −10 and 0: the aft thruster may not push around 180° (pushing aft sends the race forward onto the other), and the forward one not around 0°.
- **15D:** just below 15D gives a zone, exactly 15D doesn't. D is the flushing thruster's, so a large thruster can flush a small one that can't flush it back.
- **Tunnels** may be flushed, so they cause no zones. They can still flush others and get zones themselves.

## 4. Non-convex capacity: convex pieces

An azimuth's capacity without zones is a disc (as a 36-gon, see
`thruster_allocation.md`), which is convex. Taking out a sector leaves a
"pac-man", which is **not** convex: two allowed forces either side of the
zone add up to one inside it. So one LP can no longer describe it.

**Decided with William (2026-09-28): split into convex pieces and enumerate.**
- `allowed_arcs(zones)` gives the allowed arcs between the zones: `[None]` with no zones (the whole disc) and `[]` with everything forbidden.
- `allocate_thrust` draws each arc's capacity as a polygon and splits it into convex fans of at most 180° (`_convex_fans`). A circular sector of at most 180° is convex. Each fan's force must lie inside its edges *and* between the two boundary rays:
  ```
  sin a · fx − cos a · fy ≤ 0        (left of the ray at a)
  −sin b · fx + cos b · fy ≤ 0       (right of the ray at b)
  ```
  - These rows have limit 0, so they don't scale with u. For a fan of at most 180° the two half-planes intersect in exactly the sector.
- Pass 1 (minimum u) runs for **every combination** of pieces, one per azimuth, and the lowest u is kept. Pass 2 (least total thrust) runs in the first combination that reaches it.
  - Every combination is exact, so the minimum over them is the exact non-convex optimum. No big-M or MILP is needed.
- **Tunnels and shaft lines** have only two directions. A direction strictly inside a zone gets limit 0, so no enumeration is needed.
- **Since step 7c** the same polygons also carry the skeg loss (`skeg_loss.md`), and the split into fans handles both. With the skeg dip each aft azimuth of the test vessel has 3 pieces (9 combinations).
  - In step 7b the pieces were the 36-gon plus cone rows. The polygon now has a corner exactly at each zone edge, and the results are the same to 1e-14.

## 5. The test vessel (`config.THRUSTERS`)

Table A-6 for the test vessel, from `forbidden_zones_level1(config.THRUSTERS)`:

| Thruster | Zone [deg] | Why |
|---|---|---|
| AZ1 (−40, +5.5) | 69.56 – 110.44 | flushing AZ2: s = 11 m < 15D = 45 m, half-angle 20.44° around 90° |
| AZ2 (−40, −5.5) | 249.56 – 290.44 | flushing AZ1, around 270° |
| BT1, BT2 | – | tunnels only flush AZ1/AZ2 from ~70 m > 15D = 30 m; AZ → BT is exempt |

AZ1's allowed directions become the pieces 110.44–270° and 270–429.56°, and
AZ2's 290.44–450° and 450–609.56°.

**Effect: none on the DP capability numbers.** Over all BF and headings, the
zones only change u at BF 6–7 at 10° and 350°. There u is about 0.19, far
from the limit.
- For loads from starboard, the aft azimuths make the yaw moment by pushing in opposite surge directions: AZ1 at about 340°, AZ2 at about 200°. Neither is near its zone. Port loads mirror this.
- **Worked example, BF 6 at 10°:** the load is (−60.7 kN, 62.2 kN, 945.9 kNm).
  - Without zones, AZ2 pushes at 263°, inside its zone 249.56–290.44°.
  - With zones it moves to 296.6° and AZ1 from 360° to 343.8°.
  - u rises from 0.1871 to 0.1886.
- In failure cases (step 8), e.g. with a tunnel lost, the azimuths have to give more sway, and the zones can matter more.

## 6. In the code

- `Thruster.forbidden_zones` in `dp_capability/vessel.py`: user zones (Table A-6), as a tuple of `(start, end)` in degrees. The default is none.
- `dp_capability/models/forbidden_zones.py`:
  - `FLUSHING_DISTANCE_D = 15.0` (the 15D of [3.11.3]);
  - `flushing_sectors(thrusters)`: the [3.11.3] zones per thruster; two thrusters at the same position raise `ValueError`;
  - `merge_zones(zones)`: normalise and merge;
  - `forbidden_zones_level1(thrusters)`: user zones + flushing sectors, merged. This is the Table A-6 content for the report;
  - `allowed_arcs(zones)`: the allowed arcs between the zones (split into convex pieces by `allocate_thrust`).
- `allocate_thrust(..., forbidden_zones=True)` in `thruster_allocation.py`:
  - it finds the zones among the thrusters it is given, i.e. the working ones;
  - it enumerates the convex pieces of every azimuthing thruster (`itertools.product`);
  - `_thruster_pieces` builds them, or zeroes a tunnel or shaft line direction;
  - `False` ignores all zones.
- `capability_numbers_level1(..., forbidden_zones=True)` passes the switch on.
