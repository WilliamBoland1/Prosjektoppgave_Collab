# CLAUDE.md

Python implementation of **DNV-ST-0111 (Edition December 2021), DP capability
Level 1**. A student project by William and Olve.

## Start here

- **Read `HANDOVER.md` first.** It is the project's memory between sessions: the status table, conventions, the next step, and decisions made or still open.
- Work on **one step** from the HANDOVER.md §2 table at a time. A step is done when:
  - the tests pass;
  - `HANDOVER.md` is updated (status, test count, decisions, next step);
  - `STRUCTURE.md` is updated, if files were added.

## Running things

- Always use the project venv explicitly. It has exactly the pinned versions from `requirements.txt`:
  ```
  .\.venv\Scripts\python.exe -m pytest tests -q
  .\.venv\Scripts\python.exe main.py
  ```
  Other Pythons on this machine (plain `py`, `python` outside the venv, conda base) have older numpy/scipy or no matplotlib. In PowerShell, typing `main.py` alone opens it with the `py` launcher, not the venv.
- Don't install packages into `.venv` without asking; `requirements.txt` is pinned.

## The standard

- The PDF is not in git. Look in `theory/` (git-ignored) first. On William's machine it is at `../DNV-ST-0111.pdf`, one level above the repo.
- **Formulas and most tables are images**, so `pdftotext` drops them. Render the page instead:
  - install PyMuPDF into a scratch folder (not `.venv`);
  - use `page.get_pixmap(dpi=300, clip=...)`;
  - the page numbers printed in the PDF match its page indices.
- Level 1 is prescriptive: the formulas "shall be strictly followed without any deviations" (§3.2.1). So:
  - read every formula, coefficient and table value from the PDF, not from notes or memory;
  - before using a transcribed table, show the user the rendered crop next to your transcription.

## Conventions

Full details are in the docstring of `dp_capability/standard.py` and in HANDOVER.md §3.

- **Frame (§2.8.2):** x forward, y to **port**, z up, origin at Lpp/2 on the centreline at the keel. Forces are positive forward and to port; the yaw moment is positive counter-clockwise.
- **Environment direction:** where it comes **from**, clockwise. 0° = head-on, 90° = from starboard.
- **Angles:** public functions take degrees and convert to radians inside.
- **Where values live:** constants fixed by the standard go in `standard.py`, vessel data in `config.py` (using the dataclasses in `vessel.py`). Functions never hard-code either.
- **Shape of functions:** numpy-vectorized over direction. Load functions return a plain `(fx, fy, mz)` tuple.
- **Dynamic factor:** the individual load functions are unfactored. The 1.25 is applied only in `environmental_loads_level1`.
- **Blendermann** (in `windloads.py`) is a Level 2/3 method. Keep it out of the Level 1 chain.

## Code and tests

- Match the existing models. `wind_loads_level1` in `windloads.py` is the template:
  - a docstring that cites the section, e.g. `[3.9]`;
  - comments only where a formula needs explaining.
- Every formula gets tests with round-number inputs that can be checked by hand. Test comments show the arithmetic.
- Tests build their own vessel in a fixture and never depend on `config.HULL`.
- Theory write-ups go in `dp_capability/models/Descriptions/<module>.md`: formulas, sign checks, worked example, and how they map to the code.

## Git

- Work on the `william` or `olve` branch and merge into `main` when ready (see `README.md`).
- Commit messages are in Norwegian.
- Commit only when asked.
