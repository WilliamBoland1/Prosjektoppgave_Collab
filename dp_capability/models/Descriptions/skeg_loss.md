# Skeg loss — DP capability Level 1

This document explains `skeg_loss.py` and how `allocate_thrust(...)` applies
the skeg loss. It maps DNV-ST-0111 (Edition December 2021) [3.11.5] and
[3.11.6] to the code. The formulas and Tables 3-7/3-8 (PDF pages 37–38) are
images. They were transcribed from 300 dpi crops and checked with William
before any code was written.

## 1. Background

A thruster whose race hits the hull loses thrust. [3.11.5] says:
- "For mono-hull it is reasonable to assume that the skeg or gondola is the only part of the hull which any thruster may flush."
- The loss applies to "all thruster placed above the base line, except tunnel thrusters".
- It applies "when the shortest distance between the thruster and a vertical plane going forward along the x-axis from the aft most point on the skeg or gondola is less than 15D for open propellers and 8D for ducted propellers, and the propeller is not directly behind the skeg".
- It is a factor that depends on the **thrust direction**, given as breakpoints in Table 3-7 (port thrusters) and Table 3-8 (starboard thrusters), with "linear interpolation in polar coordinates" in between. Figure 3-7 shows an example.
- The change log (p. 90) says this formula "replaces the requirement for thrust forbidden zones toward skegs". So the skeg is a loss, not a zone.

[3.11.6] gives the total:
```
β_T = β_misc · β_vent · β_T,flushing dead · β_T,flushing skeg
```
and "if β_T,flushing dead or β_T,flushing skeg are not applicable, [they] can be taken as 1".

## 2. Formulas

All angles are [3.8.2] thrust angles (0 pushes forward, counter-clockwise).
(x_thr, y_thr) is the thruster, (x_skeg, y_skeg) the aft most point of the skeg,
and D the thruster's diameter.

```
s       = √((x_skeg − x_thr)² + (y_skeg − y_thr)²)    if x_skeg > x_thr   (thruster aft of the skeg end)
          |y_skeg − y_thr|                           if x_skeg ≤ x_thr   (beside the skeg)
α_jet   = arctan(0.6·D / s)
```

**Port thrusters, Table 3-7:**
```
α_flush   = π/2 − arctan((x_skeg − x_thr) / (y_skeg − y_thr))
α_maxloss = min(max(α_flush + α_jet, π/2), π)
```

| Thrust direction | Factor |
|---|---|
| 0 to max(α_flush − α_jet, 0) | 1 |
| α_maxloss | 2·α_maxloss/π − 1 |
| min(α_maxloss + 4α_jet, π) to 2π | 1 |

**Starboard thrusters, Table 3-8:**
```
α_flush   = 3π/2 − arctan((x_skeg − x_thr) / (y_skeg − y_thr))
α_maxloss = max(min(α_flush − α_jet, 3π/2), π)
```

| Thrust direction | Factor |
|---|---|
| π to max(α_maxloss − 4α_jet, π) | 1 |
| α_maxloss | 3 − 2·α_maxloss/π |
| min(α_flush + α_jet, 2π) to 2π | 1 |

Between the listed points the factor is linear in the angle. Figure 3-7 plots
it as straight lines against the thrust direction. Table 3-8 doesn't list
0 to π, but interpolating between the points at 2π (= 0) and π, both 1,
gives 1.

**What α_flush is.** The race goes opposite to the thrust. α_flush is the
thrust angle that sends the race straight at the skeg end, so it points
*away* from the skeg. For AZ1 at (−40, 5.5):
- the vector to the skeg end (−36, 0) is (4, −5.5), at −53.97°;
- the opposite direction is 126.03°;
- the formula gives 90° − arctan(4/−5.5) = 90° + 36.03° = 126.03° ✓.

**Port and starboard are exact mirrors.** θ → 2π − θ turns every row of
Table 3-7 into the matching row of Table 3-8. α_maxloss goes from α_flush + α_jet
to α_flush − α_jet, and 2α/π − 1 becomes 3 − 2α/π. So a symmetric layout
gives symmetric capability numbers.

**Figure 3-7** is consistent with this. There the factor is 1 up to about 100°,
0.5 at 135° (= 2·135/180 − 1) and 1 again from 180°. That is α_maxloss = 135°
and α_maxloss + 4α_jet capped at π.

## 3. Decisions (agreed with William, 2026-09-28)

1. **Several skegs take the minimum** factor per direction. Their loss regions normally point in different directions, where the minimum equals the product, and the minimum doesn't double-count where they overlap.
2. **Port/starboard is relative to the skeg:** y_thr > y_skeg uses Table 3-7. The formulas use y_skeg − y_thr, which only makes sense that way on a twin-skeg hull.
3. **"Directly behind the skeg" is y_thr = y_skeg** (with x_thr < x_skeg): no loss. A thruster level with the skeg is on neither side, so neither table applies.
4. **"Above the base line" is z > 0** (the keel is at z = 0).
5. **Shaft lines** use the factor at 0° and 180° on their forward and reverse limits. Tunnels are exempt.
6. **The polar interpolation is drawn with polygon corners every 1°** (`RAMP_STEP_DEG`) where the factor changes. Between two corners the true boundary r(θ) = T·β(θ) is linear in θ. Such a curve is curved like a circle around the origin (convex as seen from it, since r² + 2r'² − r·r'' > 0 with r'' = 0), so the chord lies inside it and the polygon stays conservative.

## 4. Checks

- **Round case** (tested): skeg end (−36, 0), an open D = 10 thruster at (−30, 6).
  - s = 6 and α_jet = arctan(1) = 45°.
  - α_flush = 90° − arctan(−6/−6) = 45°, so α_maxloss = 90° with factor 0.
  - The factor is 1 at 0°, 0.5 at 45°, 0 at 90°, 0.5 at 135°, and 1 from 180°.
  - Its mirror at (−30, −6) has the dip at 270°.
- **Not applicable:** a tunnel, z = 0, a thruster directly behind, or out of range. The range depends on the duct: D = 0.8 at s = 6.80 is out of range ducted (8D = 6.4) but in range open (15D = 12).
- **Allocation:** in the round case, 0.25 T at 45° gives u = 0.5 (0.25/cos 5° without the skeg). Pushing at 90° is impossible (u = ∞).

## 5. The test vessel

Only the aft azimuths are affected. The tunnels are exempt.

| Thruster | s [m] | α_jet | α_flush | Loss region | Minimum |
|---|---|---|---|---|---|
| AZ1 (−40, +5.5), ducted D 3 | √46.25 = 6.80 (< 8D = 24) | 14.83° | 126.03° | 111.20° → 140.85° → 180° | 0.565 at 140.85° |
| AZ2 (−40, −5.5) | 6.80 | 14.83° | 233.97° | 180° → 219.15° → 248.80° | 0.565 at 219.15° |

- The minimum is 2·140.852/180 − 1 = 0.56503.
- The return to 1 is capped at 180° (α_maxloss + 4α_jet = 200.2° > π).

**Capacity polygon and convex pieces.**
- AZ1 already had a forbidden zone of 69.56–110.44° (`forbidden_zones.md`), and the skeg dip starts right after it.
- Its polygon over the allowed arc 110.44–429.56° has 103 corners. It splits into 3 convex fans: 110.44–140.85° (up to the bottom of the dip, a right turn), 140.85–320° (the 180° limit) and 320–429.56°.
- AZ2 is the mirror.
- That gives 3 × 3 = 9 combinations per allocation, and the envelope takes about 3.8 s.

**Effect on the DP capability numbers:** only **100° and 260° drop, from BF 7 to 6** (`capability.md` §3).
- There AZ2 pushes at about 193°, inside its loss ramp (β_skeg = 0.857), and the allocation moves load to AZ1. At 100°, u at BF 7 goes from 0.995 to 1.011.
- At beam (90°), u rises from 0.747 to 0.759 at BF 6 and from 1.055 to 1.071 at BF 7. The number stays 6.
- The largest relative rise is near astern, where both azimuths push aft into their ramps: +12% at 170° (BF 6, u ≈ 0.12), and from 0.692 to 0.747 at BF 11. There is enough margin there, so the number stays 11.
- The lowest numbers over 360° and within ±30° of the bow stay at 6 and 8.

## 6. In the code

- `dp_capability/models/skeg_loss.py`:
  - `SKEG_DISTANCE_D_OPEN = 15.0`, `SKEG_DISTANCE_D_DUCTED = 8.0`;
  - `skeg_loss_breakpoints(thruster, skeg)`: the Table 3-7/3-8 points (angles in degrees and factors), or `None` if the loss doesn't apply;
  - `skeg_loss_factor(thruster, skegs, angle_deg)`: `np.interp` over the breakpoints, the minimum over the skegs, vectorised over the angle.
- `allocate_thrust(..., skegs=())` in `thruster_allocation.py`:
  - An azimuth's capacity is a star polygon with radius T·β_skeg(θ). `_polygon_angles` gives the corners: every 360°/n_sides, the zone edges, the breakpoints and every 1° in the ramps.
  - `_convex_fans` splits it into convex pieces, and `_fan_rows` turns each into LP rows (see `thruster_allocation.md`).
  - Shaft line limits are multiplied by β_skeg at 0°/180°.
- `capability_numbers_level1(..., skeg_loss=True)` passes `hull.skegs`. `False` leaves the loss out.
- `thrust_loss_factor_level1` stays β_misc · β_vent: the direction-independent part of [3.11.6].
