# Project Structure

This document describes the new file structure and what each file is
responsible for. The old structure has been kept in `Old_structure/` for
reference and has not been deleted.

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
│   ├── environmental_loads.py          Functions computing wind, wave and
│   │                                    current forces/moments acting on the
│   │                                    vessel.
│   ├── thruster_allocation.py          Functions computing available
│   │                                    thrust/force from the thrusters,
│   │                                    including any allocation logic.
│   └── capability.py                   Combines environmental loads and
│                                        thruster capacity into the DP
│                                        capability result (e.g. the
│                                        capability polygon) for a given
│                                        heading/condition.
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
                                         structure of dp_capability/. Each
                                         module in dp_capability/ has a
                                         corresponding test file, so
                                         calculations can be verified
                                         independently of running the full
                                         program.
├── __init__.py
├── test_io_utils.py
├── processing/
│   └── test_clean.py
├── models/
│   ├── test_environmental_loads.py
│   ├── test_thruster_allocation.py
│   └── test_capability.py
└── plotting/
    └── test_capability_plot.py

Old_structure/                          Previous project layout, kept for
                                         reference only. Not part of the new
                                         structure and should not be imported
                                         from.
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
- **tests/ mirrors dp_capability/.** Every module gets a matching test file,
  making it easy to see what is and isn't covered.
- **Notebooks (if used) import from dp_capability/** instead of duplicating
  logic, so exploratory work and the reproducible main.py run stay in sync.
