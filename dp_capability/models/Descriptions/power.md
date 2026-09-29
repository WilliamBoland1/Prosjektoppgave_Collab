# Power — DP capability Level 1

This document explains `power.py` and how `allocate_thrust(...)` keeps the
thrusters within the power the switchboards and prime movers can give. It
maps DNV-ST-0111 (Edition December 2021) [3.12], [2.4.9] and Tables A-5, A-8
to A-10 to the code. All of this is text in the PDF (pages 17, 39–40 and
73–77), so no crops were needed (`SOURCES.md`).

## 1. Background

- [2.4.9]: "The capability plots shall be based upon available power and the thrust output that is under control and available to the DP system, in the specified operating mode."
- [3.12.1]: the operating mode shall be specified: switchboard set-up, open/closed bus-ties, running and stand-by gen-sets and other prime movers, dual supplies to thrusters, other major consumers.
- [3.12.2]: battery power is based on 80% to 20% state of charge (at beginning of life), and the maximum discharge rate at 20% state of charge. The source must supply that power for at least 30 minutes. Reductions from battery control or safety functions shall be accounted for.
- [3.12.3]: "For each redundancy group, 10% of electrical generated power shall be reserved for hotel and consumers not part of the thruster system."
- [3.12.4]: electrical losses from generated power to the actuators are included in those 10% and "shall not be added separately".
- [3.12.5] and A.3.5: the thrust utilisation, thrust loss factor and power utilisation at switchboard level are documented per condition. Tables A-8, A-9 and A-10 are the templates. Table A-5 gives each thruster's share of power per switchboard (SWBD) and prime mover (PM).

What the standard does **not** give is how much power a thruster uses at part thrust.

## 2. Formulas

**Power at part thrust** (decided with William, §3):
```
T_Nominal = η1 · η2 · (D · P_B · η_M)^(2/3)       [3.9.2]
⇒  P = P_B · r^(3/2),   r = T / T_Nominal
```
- Full nominal thrust (r = 1) uses exactly P_B. Half thrust uses 0.354 P_B, and a quarter uses 0.125 P_B.
- r is the thrust **before losses** as a fraction of the nominal thrust in that direction. In the allocation it is the force as a fraction of the effective capacity (after β_T and β_skeg) in the direction the thruster pushes. That is also the "Utilization %" of Table A-8.
- Reverse thrust uses the reversed nominal thrust, so r = 1 in reverse also uses P_B. For a shaft line with a rudder, r = propeller thrust / T.

**Battery** ([3.12.2]):
```
P_battery = min( (0.8 − 0.2) · E / 0.5 h ,  P_discharge,max at 20% SOC )
```
Guidance note 1: 1000 kWh gives 600 kWh, so 1200 kW for 30 min, unless the discharge rate is lower.

**Usable power per source** ([3.12.3]–[3.12.4]):
```
P_usable = 0.9 · P_available     (switchboard)
P_usable = P_available           (prime mover driving a propeller directly)
```

**Source balance** (Table A-5 shares s_ji):
```
Σ_i s_ji · P_i  ≤  P_usable,j      for every source j
```

## 3. Decisions (agreed with William, 2026-09-29)

1. **P = P_B · r^1.5**, from turning [3.9.2] around. A linear P = P_B · r would be simpler and more conservative, but it doesn't match the standard's own thrust–power relation.
2. **Batteries count toward the switchboard's available power**, and the 10% applies to the whole bus. Hotel loads draw from the bus whatever feeds it.
3. **Only electrical sources reserve 10%.** [3.12.3] speaks of "electrical generated power". A prime mover driving a propeller directly (Table A-5's PM columns) has none.
4. **Table A-5 shares are fixed fractions.** A thruster split 50/50 draws half its power from each source.
5. **Bus-ties are modelled by how the sources are defined.** Switchboards joined by a closed bus-tie are one `PowerSource` with their gen-sets together.
6. **The 10% is taken per source.** Table A-10 reports reserved power per SWBD. A redundancy group (step 8) is one or more sources, and 10% of each is 10% of the group.
7. **Power is optional:** `power_sources=None` gives exactly the results of before step 7e.

## 4. In the allocation

Before step 7e the LP had one shared utilisation u (every force inside
u × its capacity). Now each thruster has its own fraction r_i, and power
enters through three kinds of rows:

```
a · f_i ≤ limit · r_i                        capacity piece, scaled by r_i
r_i ≤ U
q_i ≥ P_B,i · (r_k^1.5 + s_k · (r_i − r_k))   every chord k of r^1.5, r_k = 0, 0.05, …, 1
Σ_i share_ji · q_i ≤ U · P_usable,j           every source j
```

- **Pass 1** minimises U. It is the higher of the largest r_i and the largest source power as a fraction of its usable power, so the load balances iff **U ≤ 1**. U stays finite and shows how short the power is.
- **Pass 2** fixes U (+ `TOLERANCE`) and minimises total thrust as before, with all rows kept.
- **Why chords:** r^1.5 is convex, so the chords between neighbouring points lie *above* the curve, and the largest of them equals the piecewise-linear interpolant. The LP therefore overestimates the power, which is conservative. The worst case is 0.002 P_B, between r = 0 and 0.05.
- Above r = 1 the last chord is extended and underestimates. That only happens when U > 1, where the load fails anyway, so U values above 1 are indicative.
- **Without power sources** there are no q rows, and U = max r_i: the same optimum as the old u. All tests from before step 7e pass unchanged.
- **Reported** (`Allocation`):
  - `thrust_fraction` (r_i, recomputed from the final forces);
  - `power_kw` = P_B · r_i^1.5 (exact, not the chord);
  - `source_power_kw` = shares @ `power_kw`, empty without sources.

## 5. Checks and worked examples

**Round cases** (tested): one azimuth, P_B = 1000 kW, on a 1000 kW switchboard (900 kW usable).
- A load of 0.5 T gives r = 0.5 and 353.55 kW, which is 0.393 of 900 kW. So U = 0.5: thrust limits.
- A load of 0.95 T gives 0.95^1.5 · 1000 = 925.95 kW > 900 kW, so U = 1.0288: power limits. Without power U = 0.95.
- Two azimuths sharing a surge load, one on a 250 kW bus: the other one takes more of the load, and U stays below 1.

**The psv layout of the tests** (two ducted azimuths aft at 2000 kW, two tunnels forward at 900 kW; no skeg):
- **SWBD 1** = port azimuth + first tunnel, **SWBD 2** = the other two. That is 2900 kW of thrusters on each.
- **3600 kW each** (3240 kW usable): the numbers are the same as without power.
- **3000 kW each** (2700 kW usable): only **100° and 260° drop, from BF 7 to 6**. At 100°:

| | BF 6 | BF 7 |
|---|---|---|
| Without power: U, r per thruster | 0.700, all 0.700 | 0.993, all 0.993 |
| Without power: power per SWBD | 1699 kW | 1979 + 891 = 2870 kW > 2700 |
| With 3000 kW SWBDs: U | 0.700 | **1.006** |
| With 3000 kW SWBDs: r (AZ / BT) | 0.700 / 0.700 | 0.935 / 1.006 |
| With 3000 kW SWBDs: power per SWBD | 1699 kW | 2717 kW = 1.006 · 2700 |

At BF 7 the power limit moves load from the azimuths to the tunnels, which
then run out of thrust.

**The test vessel** (`config.POWER_SOURCES`): the same 2-split with 2 × 1800 kW per switchboard. 3240 kW usable > 2900 kW, so the envelope is unchanged (`capability.md` §3). The run takes about 4.2 s instead of 3.5 s.

## 6. In the code

- `dp_capability/standard.py`: `POWER_RESERVE_FRACTION = 0.10`, `BATTERY_SOC_HIGH = 0.8`, `BATTERY_SOC_LOW = 0.2`, `BATTERY_MIN_HOURS = 0.5`.
- `dp_capability/vessel.py`:
  - `PowerSource(name, available_kw, electrical=True)`, one Table A-5 column;
  - `Thruster.power_supply = ((source name, share), ...)`, the thruster's Table A-5 row.
- `dp_capability/models/power.py`:
  - `thruster_power_kw(thruster, thrust_fraction)` = P_B · r^1.5, vectorised;
  - `battery_power_kw(energy_kwh, max_discharge_kw)`;
  - `usable_power_kw(source)`;
  - `supply_matrix(thrusters, sources)`: the (sources × thrusters) shares. It raises `ValueError` for a missing supply, an unknown or duplicate source name, a negative share, or shares not summing to 1.
- `allocate_thrust(..., power_sources=None)` in `thruster_allocation.py`:
  - `_Power` holds P_B, shares and usable power in units of the largest P_B;
  - `_power_chords()` gives the chords (`POWER_STEP = 0.05`);
  - `_inequalities()` builds the rows shared by both passes;
  - `_thrust_fractions()` recomputes r from the forces.
- `capability_numbers_level1(..., power_sources=None)` passes it through. `main.py` uses `config.POWER_SOURCES`.
- **Not done yet (step 8):** failures. A failed redundancy group will be the same run with its sources and their thrusters removed. Tables A-8 to A-10 can be filled from `thrust_fraction`, `power_kw` and `source_power_kw`.
