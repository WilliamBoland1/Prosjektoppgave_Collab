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
    load = environmental_loads_level1(hull, BF, θ)        # × 1.25 included
    if not allocate_thrust(thrusters, load).feasible:     # u > 1
        number(θ) = BF − 1;  stop
number(θ) = 11 if no BF failed
```

- **BF 0 is never tried.** Table 2-1 gives calm (no wind, current or waves), so the load is exactly zero and always balances. A heading where BF 1 already fails gets number 0.
- **11 is the cap.** BF 12 has no DP capability number (Table 2-1).
- **Stop at the first failure.** The number is defined by the first condition that fails, not by the highest one that balances. u usually grows with BF, but nothing here assumes it does; a BF above the first failure can never raise the number. That is [2.2.2] by construction.
- **Unreachable loads fail too.** A load the thrusters cannot give in any amount has u = ∞ (`thruster_allocation.md` §2) and counts as a failure like any other.

The loads are vectorized over direction: one `environmental_loads_level1` call
per BF gives all headings. `allocate_thrust` is one LP pair per heading, and
only headings that still hold are tried. For the test vessel (36 headings) that
is 342 calls in about 0.7 s.

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

- **Port/starboard mirror:** for a layout that is symmetric about the centreline, `number(360° − θ) = number(θ)`. The loads mirror (HANDOVER §4), and so does the 36-gon of each azimuth, which has corners at every 10° from 0°.
- **[2.2.2] directly:** at each heading, every BF ≤ number balances and BF number + 1 does not (test with `allocate_thrust` called directly).
- **Pure surge by hand:** head-on, two azimuths at y = ±5 m share |Fx| equally. The number is the last BF with |Fx| ≤ 2T. With the round test hull and T = 108.9 kN: BF 9 needs 168.6 kN and BF 10 needs 221.4 kN, both against 217.8 kN, so the number is 9.

### Result for the test vessel (`config.HULL`, `config.THRUSTERS`)

u(n) is the utilisation at the capability number, u(n+1) at the next BF (the
first to fail). 190–350° mirror 170–10°.

| Heading [°] | DP capability number | Limiting wind [m/s] | u(n) | u(n+1) |
|---|---|---|---|---|
| 0 | 11 | 32.6 | 0.467 | – |
| 10 | 11 | 32.6 | 0.647 | – |
| 20 | 10 | 28.4 | 0.873 | 1.172 |
| 30 | 9 | 24.4 | 0.957 | 1.221 |
| 40 | 8 | 20.7 | 0.871 | 1.183 |
| 50 | 8 | 20.7 | 0.996 | 1.355 |
| 60 | 7 | 17.1 | 0.811 | 1.080 |
| 70 | 7 | 17.1 | 0.844 | 1.126 |
| 80 | 7 | 17.1 | 0.848 | 1.133 |
| 90 | 7 | 17.1 | 0.826 | 1.106 |
| 100 | 7 | 17.1 | 0.780 | 1.046 |
| 110 | 8 | 20.7 | 0.959 | 1.323 |
| 120 | 8 | 20.7 | 0.849 | 1.175 |
| 130 | 8 | 20.7 | 0.721 | 1.002 |
| 140 | 9 | 24.4 | 0.817 | 1.049 |
| 150 | 10 | 28.4 | 0.801 | 1.094 |
| 160 | 11 | 32.6 | 0.750 | – |
| 170 | 11 | 32.6 | 0.513 | – |
| 180 | 11 | 32.6 | 0.483 | – |

- **Beam:** BF 7, as in the worked example of `thruster_allocation.md` §3 (u = 0.826 at BF 7, 1.106 at BF 8). The whole sector 60–100° is BF 7.
- **Head and stern seas:** BF 11 within ±10° of the bow and ±20° of the stern. Even BF 11 head-on only needs u = 0.467.
- **Lowest number over 360°:** 7. **Lowest within ±30° of the bow:** 9. These will become B and A of `DP capability-L1(A, B, C, D)` in step 8 ([2.5.1]).
- **Close calls:**
  - At 50° BF 8 is balanced with u = 0.996.
  - At 130° BF 9 fails with u = 1.002.
  - At 130° the 36-gon is not the deciding factor. With 72 or 360 sides, u at BF 9 is 1.0017 or 1.0015, still > 1, so the number stays 8.
  - Step 7's thrust losses will lower the thrust. Numbers near these margins are the first to drop.

## 4. In the code

- `capability_numbers_level1(hull, thrusters, headings_deg)` in `dp_capability/models/capability.py`:
  - `headings_deg` is a scalar or an array. It returns an `int` array of the same shape, 0–11.
  - The loop over `ENVIRONMENT_TABLE[1:]` is the stepping of §2. Each heading still holding gets one `allocate_thrust` call per BF, and a heading drops out at its first `not feasible`.
- `limiting_wind_speed_level1(numbers)` in the same file: the Table 2-1 `wind_speed` of each number, via `standard.environment()`, so numbers outside 0–11 raise `ValueError`.
- `plot_envelope(headings_deg, values, title=None, r_max=None)` in `dp_capability/plotting/capability_plot.py`: returns `(fig, ax)`. `r_max` fixes the outer ring (11 for numbers, 32.6 m/s for wind), so plots of different vessels can be compared.
- `config.HEADINGS_DEG` holds 0–350° in 10° steps ([2.4.6]).
- `main.py`: config → numbers → both plots.
- Not included yet:
  - thrust losses, rudders and power (step 7);
  - failure cases and the (A, B, C, D) numbers (step 8);
  - the Table A-7 / A-8 result tables (step 8).
