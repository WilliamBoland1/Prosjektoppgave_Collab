# Flushing a dead thruster — DP capability Level 1

This document explains `dead_flushing.py` and how `allocate_thrust(..., dead_thrusters=...)` uses it. It maps DNV-ST-0111 (Edition December 2021) [3.11.4], Figure 3-6 and the β_T,flushing dead term of [3.11.6] to the code.
- The formulas on p. 36 and p. 39 are drawings. They were rendered at 300 dpi (`dead_sector.png`, `dead_loss.png`, `fig_3-6.png`, `total_beta_p39.png`, session `758e4d8c…`).
- William checked the transcription on those crops on 2026-09-29 (`SOURCES.md`).

## 1. Background

- [3.11.4]: "A thruster is flushing a dead thruster if the angle between the thrust direction and the vector from the flushed thruster to the flushing thruster is less than" a sector half-width φ. D is the diameter of the flushing thruster:
  ```
  φ = arctan(0.6 · D / s)     open flushing propeller
  φ = arctan(0.35 · D / s)    ducted flushing propeller
  ```
- "A thruster is allowed to flush a dead tunnel thruster."
- A thruster flushing a dead thruster that is not a tunnel, "closer than 8D for open propellers and 4D for ducted propellers", gets an additional loss when pointing directly towards the other thruster:
  ```
  β_T,flushing dead = 1 − 1 / (0.02 · (s/D)² + 0.25 · s/D + 1.2)
  ```
- "This effect shall be linearly interpolated in Cartesian coordinates between pointing directly towards the other thruster and the sector limits as seen in Figure 3-6." The figure shows a full circle with a straight-sided notch inside the sector.
- [3.11.6]: β_T = β_misc × β_vent × β_T,flushing dead × β_T,flushing skeg. Either flushing factor is 1 where it doesn't apply (guidance note).

Dead thrusters only exist in failure runs (step 8a, `redundancy.md`): they are the thrusters of the lost redundancy group.

## 2. Formulas

For a working thruster at (x, y) and a dead one at (x_d, y_d):
```
s      = √((x − x_d)² + (y − y_d)²)
centre = atan2(y − y_d, x − x_d)              thrust that sends the race onto the dead thruster
φ      = arctan(0.6 D / s)  or  arctan(0.35 D / s)
β      = 1 − 1 / (0.02 (s/D)² + 0.25 s/D + 1.2)
```

**Figure 3-6 as a formula.**
- The capacity runs in a straight line from A = β·(cos c, sin c) at the centre c to B = (cos(c ± φ), sin(c ± φ)) on the circle at the sector edge.
- In a frame with c = 0, the ray at angle δ meets that line at
  ```
  β_dead(δ) = β · sin φ / (sin(φ − |δ|) + β · sin|δ|)      |δ| < φ
  β_dead(δ) = 1                                            otherwise
  ```
- Check: δ = 0 gives β, and δ = φ gives β sin φ / (β sin φ) = 1.

The sector is narrow and the loss is large:

| s/D | β at the centre | φ open | φ ducted |
|---|---|---|---|
| 1 | 0.320 | 31.0° | 19.3° |
| 2 | 0.438 | 16.7° | 9.9° |
| 3 | 0.531 | 11.3° | 6.7° |
| 4 | 0.603 | 8.5° | – (not closer than 4D) |
| 6 | 0.708 | 5.7° | – |
| 8 | – (not closer than 8D) | – | – |

The loss jumps from 0.777 to none at exactly 8D (open), and from 0.603 to none at 4D (ducted). That is how the standard defines it.

## 3. Decisions (agreed with William, 2026-09-29)

1. **The sector is centred on the vector from the dead thruster to the flushing one.** Thrust that way sends the race onto the dead thruster, the same reading as [3.11.3] in step 7b. "Pointing directly towards the other thruster" refers to the race.
2. **Several dead thrusters take the lowest factor per direction**, as for several skegs, so overlapping sectors don't double count.
3. **Every kind of flushing thruster gets it.**
   - Tunnels and shaft lines take the factor of their fixed directions, in the same way the 7b zones and the skeg loss of shaft lines work.
   - A shaft line with a rudder uses the shaft direction (0°/180°).
   - "Open" and "ducted" come from the flushing thruster's `ducted` flag, so a tunnel counts as open.
4. **Dead = the thrusters of the lost redundancy group.** A thruster that only lost part of its power supply (`failure_case`) is still working.
5. **The dead flushing factor multiplies the skeg factor** in the capacity polygon, as [3.11.6] says.

## 4. In the allocation

The star polygon of step 7c (`thruster_allocation.md`, `skeg_loss.md`) already draws an azimuth's capacity as radius T · β(θ) with corners at breakpoints.
- The radius is now T · β_skeg(θ) · β_dead(θ).
- `dead_flushing_breakpoints` gives the sector edges and centre as extra corners, with corners every `RAMP_STEP_DEG` = 1° between them.
- Every corner lies on the straight line of Figure 3-6, so the chords between them *are* that line. Without an overlapping skeg ramp the notch is exact, not just conservative.
- The notch makes the polygon non-convex, so `_convex_fans` splits it further, as for the skeg dip. A notch in the middle of the full circle adds one reflex corner.

**Tunnels and shaft lines:** the limits in their fixed directions are multiplied by β_dead of that direction.

`failure_numbers_level1(..., dead_flushing=True)` passes the group's thrusters to `capability_numbers_level1(..., dead_thrusters=...)` and on to `allocate_thrust`. `dead_flushing=False` leaves the loss out, which gives step 8a's results.

## 5. Checks and worked examples

**Round cases** (tested, open D = 2 m, T = 108.89 kN):
- **Dead thruster 10 m aft:** s/D = 5, φ = arctan(0.12) = 6.843°, β = 1 − 1/2.95 = 0.661.
  - 0.5 T forward needs u = 0.5 / 0.661 = 0.756, against 0.5 without the loss.
- **Straight in Cartesian coordinates:** the midpoint of the line from 0.661·(1, 0) to (cos 6.843°, sin 6.843°) is (0.8270, 0.0596), at 4.120° and radius 0.829.
  - The factor there is 0.829; linear in the angle it would be 0.865.
  - A force of T times that point needs exactly u = 1.
- **A tunnel with a dead azimuth 5 m to starboard:** s/D = 2.5 and β = 0.487 when it pushes to port, so 0.25 T needs u = 0.513. Pushing to starboard is unaffected (u = 0.25).
- **Head-on, two azimuths 6 m apart on the centreline, the aft one dead:**
  - The forward one's capacity is 0.531 × 108.89 = 57.77 kN.
  - BF 6 (53.14 kN) holds and BF 7 (82.34 kN) fails, so the number is **6**; it was 7 without the loss.
  - With the forward one dead, the aft one's race goes away from it, so it stays at 7.

### The test vessel

- **Which pairs qualify:**
  - AZ2 flushes the dead AZ1 in the loss of SWBD 1, and AZ1 flushes AZ2 in the loss of SWBD 2: s = 11 m < 4D = 12 m (ducted), s/D = 3.667.
    - φ = arctan(0.35 · 3 / 11) = 5.45°, β = 1 − 1/2.386 = 0.581, centred on 270° (AZ2) or 90° (AZ1).
  - The tunnels are 68–71 m from the dead azimuths, beyond 8D = 16 m.
  - A dead tunnel may be flushed freely.
- **The numbers do not change: DP capability-L1(8, 6, 5, 3)**, the same per-heading table as in `redundancy.md` §5.
  - The surviving azimuth does push inside its notch for beam loads: at 90° it pushes at 271°, where its capacity drops to about 0.64 T.
  - Its thrust fraction rises accordingly: 0.227 → 0.355 at BF 4.
  - But the remaining tunnel is the limit there (r = 0.98), so u is exactly the same at every heading and BF (largest |Δu| 1e-17).
- The failure runs take about the same time as before (2.9 s for both).

## 6. In the code

- `dp_capability/models/dead_flushing.py`:
  - `DEAD_FLUSHING_DISTANCE_D_OPEN = 8`, `DEAD_FLUSHING_DISTANCE_D_DUCTED = 4`;
  - `dead_flushing_loss(thruster, dead) -> (centre_deg, phi_deg, beta)` or None (dead tunnel, or too far). Two thrusters at the same horizontal position raise `ValueError`;
  - `dead_flushing_factor(thruster, dead_thrusters, angle_deg)`: β_dead(θ), vectorised, lowest over the dead thrusters;
  - `dead_flushing_breakpoints(thruster, dead)`: (angles, factors) of the sector edges and centre, for the polygon corners.
- `thruster_allocation.py`:
  - `allocate_thrust(..., dead_thrusters=())`;
  - `_thruster_pieces` builds `loss(θ) = β_skeg(θ) · β_dead(θ)` and uses it for azimuths, tunnels, shaft lines and `_rudder_pieces`;
  - `_polygon_angles` takes both kinds of breakpoints.
- `capability.py`: `capability_numbers_level1(..., dead_thrusters=())` and `failure_numbers_level1(..., dead_flushing=True)`.
- Table 2-3 (Z030) asks for the forbidden zones "before and after WCSF" in the report. The notch is a reduced-thrust zone rather than a forbidden one, so it belongs in that table (Table A-6, step 8c) as well.
