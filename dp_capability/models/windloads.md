# Wind loads — Blendermann's method

This document explains the theory behind `windloads.py` and maps each part of
Blendermann's (1994) method to the exact code that implements it.

Reference: W. Blendermann, "Parameter identification of wind loads on ships",
*J. Wind Eng. Ind. Aerodyn.* 51 (1994) 339-351.

## 1. Background

Blendermann's method is a semi-empirical model for estimating the wind
forces and moments on a ship, built from regression analysis of 28 wind
tunnel tests. Instead of running a wind tunnel test or a CFD simulation for
every new vessel, the method estimates the wind loads from:

1. A small set of **shape parameters** that describe how "wind-exposed" the
   vessel is (fitted per ship type from the wind tunnel data), and
2. The vessel's **main dimensions** (length, lateral area, frontal area, and
   the position of the lateral-plane centroid).

### Coordinate system and definitions

- Origin at the main section, in the waterline. `x` faces the bow, `y` is
  horizontal to starboard.
- `X` = longitudinal force, `Y` = side force, `N` = yawing moment, `K` =
  rolling moment.
- `ε` (epsilon) = angle of attack of the apparent wind: `ε = 0°` is wind from
  dead ahead (bow wind), `ε = 180°` is wind from dead astern (stern wind).
- `q = 0.5 · ρ_air · V²` is the dynamic pressure of the apparent wind, with
  `ρ_air ≈ 1.23 kg/m³` and `V` the apparent wind speed.
- `A_L` = lateral-plane (side) projected area, `A_F` = frontal projected
  area, `Loa` = length overall.
- `s_L` = longitudinal distance of the lateral-plane centroid from the main
  section (positive toward the bow), `s_H` = height of the lateral-plane
  centroid above the waterline.
- `H_M = A_L / Loa` ("mean height") is used as the reference length for the
  rolling moment.

Non-dimensional load coefficients are defined as:

```
CX_AF = X / (q · A_F)              CY   = Y / (q · A_L)
CN    = N / (q · A_L · Loa)        CK   = K / (q · A_L · H_M)
```

### The four reference parameters

Blendermann found that the wind loading of (almost) any ship can be
described with just four parameters, fitted per ship type from the wind
tunnel data (his Table 1):

| Symbol | Meaning |
| --- | --- |
| `CD_t` | Coefficient of lateral resistance, i.e. `CY` at beam wind (`ε = 90°`) |
| `CD_l` | Coefficient of longitudinal resistance, at bow wind (`ε = 0°`) and stern wind (`ε = 180°`) separately, since a ship is not fore-aft symmetric |
| `δ` (delta) | Cross-force parameter — controls how "peaked" vs. "flat" the side-force curve is between bow and beam wind |
| `κ` (kappa) | Rolling-moment factor — scales the rolling-moment lever arm |

These four parameters are what's stored in `BLENDERMANN_COEFFICIENTS` in the
code (see §3).

### The loading functions

Given the four reference parameters and the vessel's geometry, Blendermann
proposes the following closed-form functions of `ε` (his Eqs. 13-16):

```
CX_AF(ε) = -CD_lAF · cos(ε) / [1 - (δ/2)(1 - CD_l/CD_t)·sin²(2ε)]

CY(ε)    =  CD_t · sin(ε)   / [1 - (δ/2)(1 - CD_l/CD_t)·sin²(2ε)]

CN(ε)    = [s_L/Loa - 0.18·(ε - π/2)] · CY(ε)

CK(ε)    = κ · (s_H/H_M) · CY(ε)
```

`CD_lAF` is `CD_l` expressed on a frontal-area basis
(`CD_lAF = CD_l · A_L/A_F`), which is the form Table 1 tabulates it in.

## 2. What the code computes

The module implements this in two steps: an internal function that evaluates
the *non-dimensional* coefficients from the equations above, and a public
function that turns them into coefficients you can multiply directly by
wind speed squared to get an actual force/moment (the same form a model test
coefficient table is usually given in).

### `_blendermann_coefficients(...)` — internal, non-dimensional coefficients

This function evaluates `CX_AF`, `CY`, `CN`, `CK` exactly as in Eqs. 13-16
above, for one or many `relative_angle_deg` values at once (it is
vectorized with numpy). Concretely, it:

1. **Looks up** `CD_t`, `CD_lAF_bow`, `CD_lAF_stern`, `δ`, `κ` for the given
   `vessel_type` in `BLENDERMANN_COEFFICIENTS`.
2. **Folds angles above 180°** back into `[0°, 180°]` (`folded_angle = 360 -
   angle`), because the wind tunnel data — and therefore the model — assumes
   the vessel is symmetric port/starboard. The side force, yaw moment and
   roll moment for a folded (port-side) angle are computed with the same
   magnitude as the equivalent starboard angle, then sign-flipped, since
   wind hitting the port side pushes/turns the vessel the opposite way.
3. **Picks bow or stern `CD_lAF`**: because a ship is *not* symmetric
   fore/aft, Table 1 gives two different longitudinal-resistance values —
   one for bow wind (`ε = 0°`) and one for stern wind (`ε = 180°`). The code
   uses `CD_lAF_bow` when the folded angle is `≤ 90°` and `CD_lAF_stern`
   when it is `> 90°`. This produces the asymmetric bow/stern shape seen in
   Blendermann's Fig. 3.
4. **Converts `CD_lAF` to `CD_l`** (`cd_l = cd_lAF · A_F / A_L`), since Eqs.
   13-14 need the longitudinal resistance on the same area basis (`A_L`) as
   `CD_t`, while Table 1 reports it on an `A_F` basis (see the note below
   Eq. 16 in the paper).
5. **Evaluates Eqs. 13-16** directly to get `CX_AF`, `CY`, `CN`, `CK`.

This function is not meant to be called from outside `windloads.py` — it is
the internal fallback used whenever no measured wind coefficients exist for
a vessel.

### `blendermann_wind_coefficients(...)` — public, dimensional coefficients

Non-dimensional coefficients are inconvenient to use directly (you would
have to remember to multiply by `q` and the right area every time). This
function folds `q` and the area into the coefficient itself, so it behaves
like a normal model-test wind coefficient:

```
X = cx · V²      Y = cy · V²      N = cn · V²      K = ck · V²
```

It does this by:

1. Calling `_blendermann_coefficients(...)` to get the non-dimensional
   `CX_AF`, `CY`, `CN`, `CK` for the requested vessel and heading(s).
2. Computing `q_per_v2 = 0.5 · air_density` (dynamic pressure per unit
   `V²` — i.e. `q` with the `V²` factor left out, since that's supplied
   later by whoever calls this function with an actual wind speed).
3. Multiplying each coefficient by `q_per_v2` and its reference area
   (`A_F` for `cx`, `A_L` for `cy`, `A_L·Loa` for `cn`, `A_L·H_M` for `ck`),
   which is exactly the definition of each coefficient inverted
   (e.g. `CX_AF = X/(q·A_F) ⟹ X = CX_AF · q · A_F = (CX_AF · q_per_v2 ·
   A_F) · V²`).

## 3. `BLENDERMANN_COEFFICIENTS` — the reference data

This dictionary is a direct transcription of Blendermann's Table 1, one
entry per vessel type, with fields `cd_t`, `cd_lAF_bow`, `cd_lAF_stern`,
`delta`, `kappa` as described in §1.

Two deviations from the raw table, both noted in the code:

- Rows the paper lists with two alternative values (e.g. "cargo vessel,
  loaded/container on deck", "tanker, loaded/in ballast") are split into two
  separate vessel-type entries, one per alternative.
- `drilling_vessel` is given as a *range* in the paper (`CD_lAF` = 0.70–1.00
  at the bow, 0.75–1.10 at the stern) rather than two alternatives; the
  midpoint of each range is used.

## 4. Known assumptions/approximations

- **Port/starboard symmetry** is assumed for all vessel types (angles are
  folded at 180°). This matches how the reference data itself was measured
  (Table 1 has no separate port-side values).
- **Bow/stern selection is a hard switch at `ε = 90°`**, rather than a smooth
  blend. This is a common simplification of Blendermann's method and matches
  how the two `CD_lAF` values are meant to be used, but it does mean `CX_AF`
  has a kink exactly at beam wind.
- **`ε` is used in radians** in the `CN` formula's `(ε − π/2)` term, since
  `π/2` only makes sense as 90° in radians. If your course material states
  Eq. 15 with `ε` in degrees, this needs revisiting.
- **`drilling_vessel`** uses the midpoint of the given ranges rather than a
  more detailed model — acceptable for a first estimate, but worth
  overriding with vessel-specific data if a drilling vessel's capability is
  the focus of the analysis.
