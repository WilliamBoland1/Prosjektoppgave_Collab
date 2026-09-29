# DP capability numbers and plots — DP capability Level 1

This document explains `capability_numbers_level1(...)` and
`limiting_wind_speed_level1(...)` in `capability.py`, and the polar plot
`plot_envelope(...)` in `plotting/capability_plot.py`. They turn the loads
(`environmental_loads.py`) and the per-heading balance (`thruster_allocation.py`)
into the DP capability plot of DNV-ST-0111 (Edition December 2021) [2.2.2]
and [2.4].

## 1. Background

What the standard requires (text read from PDF pages 16, 24, 73 and 74):
- **[2.2.2]:** "The DP capability number indicates that a vessel's position keeping ability can be maintained in the corresponding DP capability number condition and all conditions below, but not in the conditions specified for the next DP capability number."
- **[2.4.4]:** forces and moments must balance at the same time. "The calculations shall start by balancing the lowest environmental conditions and continue by balancing increasing weather conditions until the first limiting condition is reached."
- **[3.2.2]:** the wind, current and wave forces, times 1.25, must be balanced by the effective actuator forces, and so must "the wind, current and wave forces for all lower DP capability numbers".
- **[2.4.1], [2.4.2]:** results as DP capability numbers and/or polar capability plots. For Level 1 both plots are required: one in DP capability numbers and one in **limiting wind speed, in m/s**.
- **[2.4.6]:** "a minimum resolution of 10 degrees for the full 360 degree envelope. For visualization purposes linear interpolation between these points is acceptable."
- **App. A.3.5:** each run documents "wind envelope polar plots with DP capability number scale and m/s scale", and a results table (Table A-7) with heading, DP capability number, wind speed [m/s] and the wind, current and wave forces.

The conditions are the rows of Table 2-1 (`standard.ENVIRONMENT_TABLE`), BF 0 to 11.
"Heading" in the plot is the direction the environment comes **from**, clockwise
([2.8.2]): 0° = head-on, 90° = from starboard.

## 2. Method

### DP capability number per heading

For each heading θ:

```
for BF = 1, 2, … 11:
    load   = environmental_loads_level1(hull, BF, θ)                     # × 1.25 included
    beta_t = β_misc · β_vent(thruster, Hs, Tp, θ) per thruster, fwd/rev   # [3.9.5]
    if not allocate_thrust(thrusters, load, beta_t=beta_t).feasible:      # u > 1
        number(θ) = BF − 1;  stop
number(θ) = 11 if no BF failed
```

- **Thrust losses depend on the condition.** The ventilation loss ([3.9.4], `thrust.md` §6) depends on Hs, Tp and the wave direction, so each (BF, heading) has its own effective thrust per thruster.
  - The private helper `_loss_factors` computes them once per BF for all headings.
  - `ventilation=False` leaves them at β_misc, which reproduces the envelope from before step 7a.
- **Forbidden zones** ([3.11.2], [3.11.3], `forbidden_zones.md`) and the **skeg loss** ([3.11.5], `skeg_loss.md`, from `hull.skegs`) are applied inside `allocate_thrust`. `forbidden_zones=False` and `skeg_loss=False` switch them off.

- **BF 0 is never tried.** Table 2-1 gives calm (no wind, current or waves), so the load is exactly zero and always balances. A heading where BF 1 already fails gets number 0.
- **11 is the cap.** BF 12 has no DP capability number (Table 2-1).
- **Stop at the first failure.** The number is defined by the first condition that fails, not by the highest one that balances. u usually grows with BF, but nothing here assumes it does; a BF above the first failure can never raise the number. That is [2.2.2] by construction.
- **Unreachable loads fail too.** A load the thrusters cannot give in any amount has u = ∞ (`thruster_allocation.md` §2) and counts as a failure like any other.

The loads are vectorized over direction: one `environmental_loads_level1` call
per BF gives all headings. `allocate_thrust` is one LP pair per heading, and
only headings that still hold are tried. For the test vessel (36 headings) that
is 318 calls. With the forbidden zones and the skeg loss, each aft azimuth has 3 convex pieces, so each call solves 9 LPs for pass 1. That takes about 3.8 s in all.

### Limiting wind speed

**Decided with William (2026-09-22):** the limiting wind speed is the **Table 2-1
wind speed of the DP capability number**, e.g. BF 7 → 17.1 m/s.
- Level 1 only defines the environment (wind, current, Hs, Tp together) at the Table 2-1 rows. A wind speed between two rows would need current and waves between rows too, which Level 1 does not specify ([3.2.1]: "strictly followed without any deviations").
- So the m/s plot has the same shape as the number plot, in steps between the Table 2-1 wind speeds. Table 2-1 gives each row's wind speed as the upper limit of its range, so this is the highest wind speed the vessel is shown to hold.

### The plot

`plot_envelope` draws one value per heading as the radius, with 0° at the top,
increasing clockwise (so 90° from starboard is on the right). The last point is
joined back to the first. Between points the line is linear in (angle, radius),
which [2.4.6] allows.

## 3. Checks and result

- **Port/starboard mirror:** for a layout that is symmetric about the centreline, `number(360° − θ) = number(θ)`. The loads mirror (HANDOVER §4), and so does each azimuth's capacity polygon: the 36-gon has corners every 10° from 0°, and the zones and skeg loss of a mirrored layout are mirrored too.
- **[2.2.2] directly:** at each heading, every BF ≤ number balances and BF number + 1 does not (test with `allocate_thrust` called directly).
- **Pure surge by hand:** head-on, two azimuths at y = ±5 m share |Fx| equally. The number is the last BF with |Fx| ≤ 2T. With the round test hull and T = 108.9 kN: BF 9 needs 168.6 kN and BF 10 needs 221.4 kN, both against 217.8 kN, so the number is 9.

### Result for the test vessel (`config.HULL`, `config.THRUSTERS`)

With all Level 1 losses so far: ventilation (step 7a), forbidden zones (7b) and
the skeg loss (7c). u(n) is the utilisation at the capability number, u(n+1)
at the next BF (the first to fail). 190–350° mirror 170–10°. The last column
is the number without the skeg loss (`skeg_loss=False`).

| Heading [°] | DP capability number | Limiting wind [m/s] | u(n) | u(n+1) | Without skeg loss |
|---|---|---|---|---|---|
| 0 | 11 | 32.6 | 0.628 | – | 11 |
| 10 | 11 | 32.6 | 0.892 | – | 11 |
| 20 | 9 | 24.4 | 0.885 | 1.150 | 9 |
| 30 | 8 | 20.7 | 0.904 | 1.242 | 8 |
| 40 | 7 | 17.1 | 0.839 | 1.119 | 7 |
| 50 | 7 | 17.1 | 0.962 | 1.285 | 7 |
| 60 | 6 | 13.8 | 0.750 | 1.045 | 6 |
| 70 | 6 | 13.8 | 0.779 | 1.091 | 6 |
| 80 | 6 | 13.8 | 0.782 | 1.099 | 6 |
| 90 | 6 | 13.8 | 0.759 | 1.071 | 6 |
| 100 | **6** | 13.8 | 0.714 | 1.011 | 7 |
| 110 | 7 | 17.1 | 0.924 | 1.250 | 7 |
| 120 | 7 | 17.1 | 0.815 | 1.105 | 7 |
| 130 | 8 | 20.7 | 0.937 | 1.320 | 8 |
| 140 | 8 | 20.7 | 0.760 | 1.070 | 8 |
| 150 | 9 | 24.4 | 0.813 | 1.064 | 9 |
| 160 | 10 | 28.4 | 0.723 | 1.048 | 10 |
| 170 | 11 | 32.6 | 0.747 | – | 11 |
| 180 | 11 | 32.6 | 0.650 | – | 11 |

- **Effect of ventilation (7a):** 160° and 200° drop from 11 to 10. u at BF 11 rises there from 0.948 to 1.039, because β_vent at BF 11 is 0.72–0.95 (`thrust.md` §6). Below BF 7 the loss is at most about 1.5%, so the low beam numbers don't move.
- **Effect of the forbidden zones (7b):** none. AZ1 and AZ2 may not push within 20.44° of 90° and 270° respectively, but they balance the yaw moment by pushing in opposite surge directions, well clear of those zones. Over all BF and headings, u only changes at 10° and 350° at BF 6–7, by at most 0.0015 at u ≈ 0.19 (`forbidden_zones.md` §5).
- **Effect of the skeg loss (7c):** 100° and 260° drop from 7 to 6.
  - For loads from starboard, AZ2 pushes at about 190–200°, inside its skeg loss ramp of 180–248.8° (β_skeg ≈ 0.86 at 193°), and the allocation moves load to AZ1.
  - At 100°, u at BF 7 goes from 0.995 to 1.011.
  - The largest relative rise is near astern, where both azimuths push aft into their ramps: +12% at 170° (BF 6, at u ≈ 0.12), and from 0.692 to 0.747 at BF 11. These headings have margin enough, so no other number changes (`skeg_loss.md` §5).
- **Beam:** BF 6 (u = 0.759 at BF 6, 1.071 at BF 7). The whole sector 60–100° is BF 6.
- **Head and stern seas:** BF 11 within ±10° of the bow and ±10° of the stern. BF 11 head-on needs u = 0.628.
- **Lowest number over 360°:** 6. **Lowest within ±30° of the bow:** 8. These are B and A of `DP capability-L1(A, B, C, D)` ([2.5.1]). With the two redundancy groups of step 8a the result is **DP capability-L1(8, 6, 5, 3)**; the failure runs and C, D are in `redundancy.md` §5.
- **Close calls:**
  - At 50° BF 7 is balanced with u = 0.962.
  - At 100° BF 7 fails with u = 1.011.
  - The polygon is not the deciding factor. With 72 or 360 corners, u is 0.9612 or 0.9611 at 50° and 1.0108 at 100°, so the numbers stay 7 and 6.
- **Thruster set:** since 2026-09-28 `config.THRUSTERS` has four actuators (AZ1, AZ2, BT1, BT2; HANDOVER §4). With the earlier fifth one, a retractable azimuth at x = +22 m, the beam sector was BF 7 and the lowest numbers were 7 and 9.

## 4. In the code

- `capability_numbers_level1(hull, thrusters, headings_deg, ventilation=True, forbidden_zones=True, skeg_loss=True)` in `dp_capability/models/capability.py`:
  - `headings_deg` is a scalar or an array. It returns an `int` array of the same shape, 0–11.
  - The loop over `ENVIRONMENT_TABLE[1:]` is the stepping of §2. Each heading still holding gets one `allocate_thrust` call per BF, and a heading drops out at its first `not feasible`.
- `limiting_wind_speed_level1(numbers)` in the same file: the Table 2-1 `wind_speed` of each number, via `standard.environment()`, so numbers outside 0–11 raise `ValueError`.
- `plot_envelope(headings_deg, values, title=None, r_max=None)` in `dp_capability/plotting/capability_plot.py`: returns `(fig, ax)`. `r_max` fixes the outer ring (11 for numbers, 32.6 m/s for wind), so plots of different vessels can be compared.
- `config.HEADINGS_DEG` holds 0–350° in 10° steps ([2.4.6]).
- `main.py`: config → intact and failure numbers → the notation and three plots (`redundancy.md` §6).
- Rudders (7d, `rudders.md`) and power (7e, `power.md`) are included through `allocate_thrust`. Failure runs, the combined worst case and (A, B, C, D) are in `redundancy.md` (step 8a).
- Flushing a dead thruster (§3.11.4, step 8b, `dead_flushing.md`) only applies in failure runs, through `dead_thrusters`.
- Not included yet: the Table A-1 and A-7 to A-10 result tables (step 8c).
