# Project Structure

This document describes the file structure and what each file is
responsible for.

## Overview

```
main.py                                 Entry point. Reads config/data, calls
                                         functions from dp_capability/, and
                                         triggers plotting. Contains no
                                         calculation or plotting logic itself.

dp_capability/                          The Python package containing all
                                         reusable logic. Both main.py and any
                                         notebooks should import from here.
├── __init__.py                         Marks the folder as a Python package.
├── config.py                           Vessel parameters, thruster limits,
                                         environmental assumptions, file paths,
                                         and other constants. Values that
                                         change between runs/vessels live here,
                                         not hardcoded inside functions.
├── io_utils.py                         All reading and writing of files:
                                         loading raw data from data/raw/,
                                         saving cleaned data to
                                         data/cleaned/, and saving results
                                         (plots, tables) to output/. Nothing
                                         outside this file should open a file
                                         directly.
├── standard.py                         Everything DNV-ST-0111 fixes for all
                                         vessels: coordinate conventions,
                                         densities, g, Tp/Tz ratio, dynamic
                                         factor, the Table 2-1 Beaufort
                                         environment, the thrust efficiency
                                         Tables 3-1 to 3-4 and beta_misc.
├── vessel.py                           Data containers for vessel input
                                         (Hull = Table A-2, Thruster =
                                         Table A-3). The values for a vessel
                                         live in config.py.
│
├── processing/                         Data cleaning and preparation.
│   ├── __init__.py
│   └── clean.py                        Functions that turn raw input data
│                                        into a cleaned, analysis-ready
│                                        format (e.g. filtering, unit
│                                        conversion, handling missing values).
│
├── models/                             The actual DP capability
│   │                                    calculations (physics/math).
│   ├── __init__.py
│   ├── windloads.py                    Functions computing wind forces/
│   │                                    moments on the vessel: Level 1
│   │                                    ([3.5]) and Blendermann's method
│   │                                    (Level 2/3).
│   ├── currentloads.py                 Functions computing current forces/
│   │                                    moments on the vessel (Level 1,
│   │                                    [3.6]).
│   ├── waveloads.py                    Functions computing wave drift
│   │                                    forces/moments on the vessel
│   │                                    (Level 1, [3.7]).
│   ├── environmental_loads.py          Total Level 1 environmental load for
│   │                                    a DP capability number: wind +
│   │                                    current + waves from Table 2-1,
│   │                                    times the dynamic factor 1.25.
│   ├── thrust.py                       Nominal and effective thrust of one
│   │                                    actuator ([3.9]): Tables 3-1 to 3-4
│   │                                    and beta_misc.
│   ├── thruster_allocation.py          Thrust allocation ([2.4.4],
│   │                                    [3.11.1]): thruster forces that
│   │                                    balance one environmental load in
│   │                                    surge, sway and yaw (two linear
│   │                                    programs), and the utilisation.
│   ├── capability.py                   DP capability number per heading
│   │                                    ([2.2.2], [2.4.4]): steps up
│   │                                    through Table 2-1 until the first
│   │                                    condition the thrusters cannot
│   │                                    balance. Also the limiting wind
│   │                                    speed [m/s] for the plots.
│   └── Descriptions/                   Markdown write-ups explaining the
│       ├── windloads.md                 theory behind each model and how it
│       ├── currentloads.md              maps to the code.
│       ├── waveloads.md
│       ├── thrust.md
│       ├── thruster_allocation.md
│       └── capability.md
│
└── plotting/                           Turning results into figures.
    ├── __init__.py
    └── capability_plot.py              Functions that take a capability
                                         result and produce the DP capability
                                         plot(s).

data/                                   Input data, kept out of the code
                                         package so data and logic stay
                                         separate.
├── raw/                                Original, unmodified input data.
└── cleaned/                            Data after processing/clean.py has
                                         been applied.

output/                                 Generated results: figures, tables,
                                         exported files. Not raw or cleaned
                                         input data.

tests/                                  Automated tests, mirroring the
                                         structure of dp_capability/, so
                                         calculations can be verified
                                         independently of running the full
                                         program.
├── __init__.py
├── test_io_utils.py
├── test_standard.py
├── processing/
│   └── test_clean.py
├── models/
│   ├── test_environmental_loads.py     Tests for windloads.py,
│   │                                    currentloads.py, waveloads.py and
│   │                                    environmental_loads.py.
│   ├── test_thrust.py                  Tests for thrust.py.
│   ├── test_thruster_allocation.py     Tests for thruster_allocation.py.
│   └── test_capability.py
└── plotting/
    └── test_capability_plot.py

theory/                                 Local reference material (standards,
                                         papers). Ignored by git, so each of
                                         us keeps our own copy.
```

## Guiding principles

- **main.py stays thin.** It should only orchestrate: load config/data, call
  functions, save/show results. No calculations or plotting code directly in
  this file.
- **One responsibility per module.** io_utils.py never contains calculations;
  models/ never reads or writes files directly; plotting/ never does physics.
- **Config is separate from logic.** Numbers that might change between runs
  (vessel data, environmental assumptions, file paths) live in config.py, not
  scattered inside functions.
- **tests/ mirrors dp_capability/.** Every module is covered by a matching
  test file, making it easy to see what is and isn't covered.
- **Notebooks (if used) import from dp_capability/** instead of duplicating
  logic, so exploratory work and the reproducible main.py run stay in sync.
