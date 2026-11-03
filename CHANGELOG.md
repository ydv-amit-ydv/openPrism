# Changelog

## 1.5.0 — own repository, server data folder of your choice

* OpenPrism now lives in its own repository: `git clone https://github.com/ydv-amit-ydv/openprism.git`.
* Server commands: `--new --new --new --newserveruserdata USERPATH` (new empty server, data in USERPATH),
  `--continue --continue --continue` (daily restart with the remembered folder), `--exportdata BACKUPPATH` (backup
  .zip), `--reset --reset --reset --loadolddata BACKUP --newserveruserdata USERPATH` (start in USERPATH from a backup).
* The data folder is checked before use (writable and readable by the server's account, 200 MB free, empty or created
  by OpenPrism — folders with other files are never deleted), made private (0700) and remembered in `openprism.conf`.
  Replacing an existing server with `--new` also asks for CONFIRM three times. Backups are verified before anything
  is deleted. `--selfpurge` and the earlier `--reset` forms were removed.

## 1.4.0 — three simple server commands

* `python3 start.py` starts the server; `--reset --reset --reset` deletes all data and starts fresh;
  `--reset --reset --reset --loadolddata BACKUP` deletes all data, loads an old backup and starts (the backup is checked
  — readable, intact, a data format this version understands — before anything is deleted);
  `--selfpurge --selfpurge --selfpurge --output FOLDER` backs everything up to FOLDER, checks the backup and removes the
  installation completely. Repeating a flag three times is the confirmation.
* Removed `--export`, `--import` and the server's `--data` option (the data always live in `projects/` next to
  `start.py`; Docker and the systemd service still set the folder through `OPENPRISM_DATA`).

## 1.3.0 — simple server management

* `start.py` is the single entry point: `--export --output FILE.zip`, `--import --input FILE.zip` (zip export, a bare
  `openprism.db` or a folder; current data backed up first), `--reset --reset --reset` (three times = confirmation) and
  `--selfpurge --export FILE.zip` (export, verify, then remove this installation). The git-based `--update` /
  `--preserve` were removed.
* Exports are consistent SQLite snapshots with a manifest (format, version, data schema), checked for integrity, and
  readable only by the owner. `--import` shows what will be replaced and asks you to type `IMPORT`; it accepts only
  exports this version can read (same or older data schema) and refuses newer or unknown formats without changing
  anything. `--selfpurge` removes everything that belongs to the server, including a data folder kept elsewhere.
* The server writes a marker while it runs; every management command refuses to run while the server is up (a stale
  marker from a crash is detected and ignored).
* The start-up banner lists the management commands under the IP addresses.

## 1.2.0

* **Safe updates**: `python3 start.py --update --preserve` downloads the latest version and keeps every account and
  project (a consistent backup of the database is written to `projects/backups/` first); `--update --reset` downloads
  it and starts with no data (after typing `RESET`). `--update` on its own refuses to run, so data are never kept or
  deleted by accident. The launcher continues with the freshly downloaded version of itself.
* **Announcements**: the administrator can publish a message to all users (information, warning or urgent) in
  Server settings. It is shown on the sign-in screen and as a banner at the top of the app (open apps pick it up within
  three minutes). Users can hide information/warning messages until the text changes; urgent ones stay visible.

## 1.1.0 — made for newcomers

* **Smart import**: Import (or drag a CSV/Excel file onto the window) recognises how the data are arranged and proposes the
  right table, explaining why in plain words with a preview; alternatives are one click away. Long-format files (a group
  column and a value column) are rearranged automatically into Column, Grouped, Contingency or Survival tables; mean/SD/n
  columns become summary data; decimal-comma files get a clear explanation instead of an empty table.
* **Recommended analyses** for the data at the top of the Analyze dialog; only the analyses that fit the table are listed
  (advanced methods behind a switch); an **In plain words** box for all 75 analyses (the question it answers, an example,
  and whether it suits the data, e.g. "tick exactly two data sets").
* **Graph types explained** in one sentence each; tip on adding P values and curve fits.
* **New data table** shows each table type as a picture of example data with an everyday name.
* **Start page** with three clear starting points (I have a file / type or paste / tour) and four ready-made examples.
* **Guided tour** (one minute, on an example that can be removed afterwards): offered automatically to new accounts,
  replayable from Help or My account.

## 1.0.0

First stable release.

### Fluid interaction (no blocking pop-ups)
* Deleting a table, result, graph or layout happens at once; a small notice offers **Undo** (8 s) instead of an
  "Are you sure?" dialog.
* Renaming and other quick text inputs open as a small field next to where you clicked (Enter accepts, Esc cancels,
  clicking elsewhere accepts) instead of a dimmed full-screen dialog.
* When the server is momentarily busy, calculations wait and retry quietly instead of showing an error; the default
  per-user allowance was raised from 120 to 600 calculations per minute and from 2 to 4 at once.
* Confirmations remain only for actions that cannot be undone (deleting a project from the server, discarding unsaved
  work, resetting encryption keys).

### Robustness (found by systematic testing)
* Every analysis was run on every table type in 11 data variants (empty, one row, two rows, identical values, missing
  values, 1e±150 magnitudes, negatives, zeros, an empty column) — 2,453 runs — and with every dialog option.
* Fixed: results containing "not a number" (e.g. a t test on identical values) were sent as invalid JSON, so the
  browser could not show them at all. All server responses are now valid JSON (not-a-number values are shown blank).
* Fixed: the frequency distribution failed whenever *Bin width* or *First bin* was left blank (the default). Blank
  optional fields now mean "automatic" in every analysis.
* Degenerate data (all values identical, too few rows, a variable that is a combination of others) now give a clear
  explanation instead of "the analysis failed"; the mixed-model message explains when rows do not behave like
  matched subjects.
* A second sweep fed every analysis invalid option values (empty, null, text, negative, huge, wrong type; 1,903
  cases). Fixed: an empty option could crash the server; an unknown option value (e.g. from an old project file) gave
  "the analysis failed"; a negative column number silently analysed the *last* column instead of being refused
  (column choices are now checked centrally); absurd permutation or lag counts could run for minutes (now capped).
* A polynomial order too high for the number of different X values is explained instead of failing.
* Opening the app with `http://` on the HTTPS port now redirects instead of silently dropping the connection; a
  port that is already in use (macOS AirPlay uses 5000) is reported with the fix.

## 0.9.0
* Gray's test for cumulative incidence curves and Fine-Gray competing-risks regression (validated against cmprsk).

## 0.8.0
* Strict number format, Satterthwaite mixed models, summary-data tables, encrypted sharing, images on layouts,
  calculated columns, more power analyses, competing-risks cumulative incidence, continuous integration.

## 0.7.0
* Random-slope mixed models, GraphPad Prism .pzfx import/export, EPS and EMF export, shapes and templates, activity
  log, client-side graph summaries and faster start-up.
