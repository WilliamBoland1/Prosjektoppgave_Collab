# Where each part of DNV-ST-0111 was read from

_Started 2026-09-29. Add a row whenever a new part of the standard is used in code._

CLAUDE.md asks for every formula, coefficient and table value to be read from
the PDF, and for transcribed tables to be checked against a rendered crop.
This file records, per part of the standard, how that was done:

- **Text layer**: the value can be extracted as text from the PDF (PyMuPDF
  `page.get_text()`, or `pdftotext`). It can be re-checked by searching for it.
  (The PDF uses non-breaking spaces, so search for "Table 2-1" with them
  normalised to plain spaces.)
- **Rendered**: the content is a vector drawing, not text, so it had to be
  rendered to an image (PyMuPDF, 300 dpi) in a Claude scratchpad folder and read
  from there. The PDF has almost no raster images: the formulas, Tables 3-7/3-8
  and the figures are drawn.
- **Checked with William**: the transcription was shown next to the crop and
  William confirmed it before code was written. "No record" means the
  handover/write-ups only say it was checked against the PDF, not that William
  signed it off.

Page numbers are the printed ones, which equal the PDF page numbers.

## Record

| Part | Page | Text layer? | Read from | Checked with William | Used in |
|---|---|---|---|---|---|
| §2.8.2 coordinate system, Figure 2-1 | 21 | Text yes; figure no | Text | No record | `standard.py` docstring |
| Table 2-1 (BF, wind, Hs, Tp, current) | 15 | **Yes**, every value | Text | No record | `standard.ENVIRONMENT_TABLE` |
| §3.2.2 dynamic factor 1.25 | 24 | Yes | Text | No record | `DYNAMIC_FACTOR_LEVEL1` |
| §3.3.3 Tp = 1.4049 Tz | 25 | Yes | Text | No record | `TZ_FROM_TP` |
| §3.5 wind formulas (ρ_air = 1.226 is text) | 25–26 | Formulas no | Rendered 2026-09-22 (`page24–28.png`, `wind_formulas.png`) | No record (checked against the PDF) | `windloads.wind_loads_level1` |
| §3.6 current formulas (ρ_water = 1026 is text) | 26 | Formulas no | Rendered 2026-09-22 (`cur_formulas.png`) | No record (checked against the PDF) | `currentloads.py` |
| §3.7 wave drift formulas, Figure 3-2 | 26–27 | Formulas no | Rendered 2026-09-22 (`wave_formulas_a/b.png`) | No record (checked against the PDF) | `waveloads.py` |
| §3.8.2 thruster angle, §3.8.3 positions | 29 | Yes | Text | – (no transcription needed) | Conventions, `Thruster` fields |
| §3.9.1 effective thrust, §3.9.2 nominal thrust formulas | 29–30 | Formulas no | Rendered 2026-09-22 (`crops/formula_3-9-1.png`, `formula_3-9-2.png`) | No record for the formulas (checked against the renders) | `thrust.py` |
| Tables 3-1 to 3-4 (η1, η2, η_M) | 31–32 | **Yes**, every value | Rendered 2026-09-22 (`crops/table_3-1…3-4.png`) | **Yes**, 2026-09-22 | `ETA1`, `ETA2_*`, `ETA_M` |
| §3.9.3 β_misc = 0.9 | 32 | Yes | Rendered with Table 3-4 | **Yes**, 2026-09-22 | `BETA_MISC` |
| §3.9.4 ventilation formulas (k_V1…k_V5 are text) | 32–33 | Formulas no | Rendered 2026-09-28 (`vent_p32.png`, `vent_p33.png`) | **Yes**, 2026-09-28 | `thrust.ventilation_loss_factor`, `K_V1…K_V5` |
| §3.9.5 total β_T | 33 | Formula no | Rendered 2026-09-28 (`vent_p33_total.png`) | **Yes**, 2026-09-28 | `thrust.thrust_loss_factor_level1` |
| §3.10.1 rudder formulas (F_surge, F_sway, C_x, C_Y) | 34 | Formulas no | Rendered 2026-09-28 (`p34.png`) | **Yes**, 2026-09-29 | `rudders.py` (step 7d) |
| Tables 3-5 (k1) and 3-6 (k2) | 34 | **Yes**, every value | Rendered (`p34.png`) and text | **Yes**, 2026-09-29 | `K1_RUDDER`, `K2_RUDDER` |
| §3.10.2 no rudder with negative thrust | 35 | Yes | Text and `p35.png` | **Yes**, 2026-09-29 | `thruster_allocation.py` |
| §3.11.2 forbidden zones | 35 | Yes | Text | – | `Thruster.forbidden_zones` |
| §3.11.3 flushing sector arctan(0.1 + D/s), 15D | 35–36 | Formula no; 15D is text | Rendered 2026-09-28 (`flush_p36.png`) | **Yes**, 2026-09-28 | `forbidden_zones.py` |
| Table A-6 / Figure A-4 (sign check of [3.11.3]) | 74 | Figure no | Rendered 2026-09-28 (`p74_top.png`) | **Yes**, 2026-09-28 | Sign reading in HANDOVER §7 |
| §3.11.4 flushing a dead thruster, Figure 3-6 | 36 | Formulas no | Rendered 2026-09-28 (`p36.png`), **not transcribed yet** | Not yet | Step 8 |
| §3.11.5 skeg loss text (15D / 8D, base line) | 37 | Yes | Text | – | `skeg_loss.py` |
| Tables 3-7 / 3-8 skeg loss factor, s, α_jet, α_flush | 37–38 | **No** (only headings are text) | Rendered 2026-09-28 (`skeg_port.png`, `skeg_stbd.png`, `skeg_p38.png`) | **Yes**, 2026-09-28 | `skeg_loss.py` |
| §3.11.6 total β_T with skeg | 39 | Formula no | Rendered 2026-09-28 (`p39.png`) | **Yes**, 2026-09-28 | `thruster_allocation.py` |
| §2.4.6 guidance note (thrust and power utilisation), §2.4.9 (available power) | 17 | Yes | Text, 2026-09-29 | – (definitions) | `Allocation.thrust_fraction`, `power_kw` |
| §3.12.1–§3.12.5 power (10% reserve, battery 80–20% SOC / 30 min) | 39–40 | Yes, every value | Text, 2026-09-29 | – (text; decisions agreed 2026-09-29) | `power.py`, `POWER_RESERVE_FRACTION`, `BATTERY_*` |
| Table A-2 hull data | 71 | Yes | Text and `pages/p71.png` | – (field list) | `vessel.Hull` |
| Table A-3 actuator data | 72 | Yes | Text and `crops/table_A-3.png` | – (field list) | `vessel.Thruster` |
| Table A-4 rudder data | 72 | Yes | Text, 2026-09-29 | – (field list) | `vessel.Rudder` |
| Table A-5 thruster power configuration, A.3.5 run documentation | 73 | Yes | Text, 2026-09-29 | – (field list) | `vessel.PowerSource`, `Thruster.power_supply` |
| Tables A-8, A-9, A-10 (thruster, power and switchboard results) | 75–77 | Yes | Text, 2026-09-29 | – (column lists) | `Allocation` fields; the tables themselves are step 8 |

## Gaps worth closing

- **§3.5–3.7 and the §3.9.1/§3.9.2 formulas have no record of William's
  sign-off.** They were checked against the renders, and the tests use the
  same reading, so a mis-read would not be caught by the tests. Either
  re-check them against the crops together, or rely on the Veracity comparison
  (HANDOVER §8).
- **Table 2-1** is in the text layer, so it can be re-checked mechanically
  against `ENVIRONMENT_TABLE` in a few seconds.
- **The renders live in temporary scratchpad folders** under
  `%TEMP%\claude\c--Users-willi-Desktop-5-Prosjektoppgave-Prosjektoppgave-Collab\<session>\scratchpad\`
  (sessions `b59274f0…` for §3.5–3.7, `daf96bd4…` for §3.9 and Table A-3,
  `93230558…` for §3.9.4–§3.11.6 and p. 74). Windows may clear them. To keep
  them, copy them into `theory/` (git-ignored, like the PDF).
