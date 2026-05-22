# Malloy Aeronautics — ArduPilot Fork

Custom ArduPilot firmware for Malloy Aeronautics vehicles. This repository tracks Malloy-specific changes on top of upstream ArduPilot **4.3.0**. The integration branch is **`MA-4.3.0.X`** (not upstream `master`).

**Repository:** [github.com/Malloy-Aeronautics/Malloy-Aeronautics-AP](https://github.com/Malloy-Aeronautics/Malloy-Aeronautics-AP)

### What we changed (high level)

- **Obstacle avoidance (OA) / Dijkstra path planner** — fence-aware routing for AUTO, GUIDED (with `GUID_OPTIONS`), and RTL.
- **OA fast waypoints** — smoother mission legs through Dijkstra path points when `OA_OPTIONS` fast-WP bit is set.
- **Fence breach escape vector** — shortest escape from exclusion breach, automatic RTL hand-off, repeated breach cycles (see branch `OA-fastWP-fenceEscapeVector`).
- **SITL validation harness** — phased unattended autotests (Phase 0 firmware regression → feature phases) with logs under `docs/<THISFIRMWARE>/` and a campaign spreadsheet.

Upstream ArduPilot documentation still applies for general build/dev topics: [ardupilot.org/dev](https://ardupilot.org/dev/).

---

## Firmware update workflow

Every feature firmware update follows the same process. Example: **`OA-fastWP-fenceEscapeVector`** with `THISFIRMWARE` **`MA_COPTER-V4.3.0.16-OA-fastWP-fenceEscapeVector`**.

### 1. Create a feature branch

On GitHub (or locally):

1. Go to **Branches → New branch**
2. **Source branch:** `MA-4.3.0.X`
3. **Branch name:** short feature name, e.g. `OA-fastWP-fenceEscapeVector` (must match the suffix you will use in `version.h`)

```bash
git fetch origin
git checkout -b OA-fastWP-fenceEscapeVector origin/MA-4.3.0.X
```

### 2. Bump `ArduCopter/version.h` (first commit on the branch)

Edit `THISFIRMWARE` **before** starting code changes. Format:

```c
#define THISFIRMWARE "MA_COPTER-V4.3.0.16-OA-fastWP-fenceEscapeVector"
```

- Increment the **build number** (`.16`, `.17`, …) for each new firmware update.
- The part **after** the build number must **exactly match** the git branch name.

Validate:

```bash
python3 Tools/autotest/firmware_SITL_validation_campaign.py validate
```

### 3. Develop firmware changes

Implement and review code on the feature branch as usual.

### 4. SITL validation campaign

When ready to test, initialize the campaign (reads `THISFIRMWARE`, creates `docs/` tree + spreadsheet template):

```bash
./Tools/autotest/reset_firmware_SITL_validation_campaign.sh
```

Creates:

```
docs/<THISFIRMWARE>/
  Phase0/logs/
    full_<timestamp>/<TestName>/     (.txt, .tlog, .BIN, run_results.json)
    rerun_<timestamp>-<TestName>/    (single-test re-runs)
    run_results.json                 (aggregate of all reruns)
  Phase1/logs/ … Phase3/logs/      (when those phases are added)
  <THISFIRMWARE>.xlsx              (Intro + phase tabs; columns E–G = Pass/Fail, Re-runs, Log ref)
  README.txt
```

**Run tests** (builds SITL on first full phase run; use `--skip-build` for reruns):

```bash
./Tools/autotest/run_firmware_SITL_validation_campaign_tests.sh 0
./Tools/autotest/run_firmware_SITL_validation_campaign_tests.sh 0 P0_07_Landing --skip-build
```

**When a test fails — triage with the `.tlog`**

Each test folder under `Phase<N>/logs/` should contain an autotest `.txt` log and, when the harness captured it, a `.tlog`. Open the `.tlog` in Mission Planner (or similar) and check whether the vehicle behaved correctly:

- **Autotest issue** — bad mission geometry, wrong parameters in the test, timeout too short, fence disabled when the scenario needs it enabled, etc. Fix the test under `Tools/autotest/` and re-run.
- **Firmware bug** — correct test setup but wrong OA/fence/RTL behaviour. Fix firmware, rebuild, re-run.

Do not treat a red autotest as a firmware failure (or vice versa) without looking at the flight track and STATUSTEXT/OADJ messages in the `.tlog`.

**Update the spreadsheet** after each full run or batch of reruns:

```bash
./Tools/autotest/generate_firmware_SITL_validation_campaign_artifacts.sh 0
```

This refreshes **all phase tabs** that have logs on disk (columns **E** Pass/Fail, **F** Re-runs to pass, **G** Log ref). It does **not** generate HTML reports or visual evidence folders — logs + spreadsheet are the deliverables.

Repeat **run → triage → fix → re-run → update spreadsheet** until the required phases are all PASS.

#### Phase overview (this branch)

| Phase | Scope | Autotest module | Count |
|-------|--------|-----------------|-------|
| 0 | Firmware regression (P0-01..22) | `Tools/autotest/oafastwp_phase0.py` | 22 |
| 1 | Dijkstra fence regression (SITL-01..23) | `Tools/autotest/oafastwp_phase1.py` | 23 |
| 2 | Fast-WP integration (SITL-14,17,23,29,32) | tests in `Tools/autotest/arducopter.py` (`OAfastWP_*`) | 5 |
| 3 | Breach escape gate (SITL-25..31 excl. 29) | tests in `Tools/autotest/arducopter.py` | 6 |

Add Phase 1–3 tabs to the workbook when Phase 0 passes:

```bash
./Tools/autotest/add_firmware_SITL_validation_phase.sh 1
./Tools/autotest/run_firmware_SITL_validation_campaign_tests.sh 1
./Tools/autotest/generate_firmware_SITL_validation_campaign_artifacts.sh 1
```

Same pattern for phases 2 and 3.

#### Adding new tests in a later phase

1. **Implement the autotest**
   - Phase 0: add a method to `Tools/autotest/oafastwp_phase0.py` (often delegating to an upstream test in `arducopter.py`).
   - Phase 1: add a method to `Tools/autotest/oafastwp_phase1.py` and any mission/fence assets under `Tools/autotest/ArduCopter_Tests/OAfastWP_Regression_Assets/`.
   - Phases 2–3: add `OAfastWP_*` methods on `AutoTestCopter` in `Tools/autotest/arducopter.py` and register them in the phase runner / `autotest.py` if needed.

2. **Register the test ID** in `Tools/autotest/oafastwp_spreadsheet_data.py`:
   - Row data (`P0_ROWS`, `PHASE1_ROWS`, …)
   - `PHASE_AUTOTEST` mapping (spreadsheet Test ID → autotest method name)
   - Phase test list in `Tools/autotest/generate_oafastwp_visual_evidence.py` (`PHASE0_TESTS`, …) used for log collection

3. **Add a worksheet row** by re-running `add_firmware_SITL_validation_phase.sh` for a new phase tab, or edit the generated `.xlsx` template via `oafastwp_spreadsheet_data.py` and reset the campaign if the Intro template must change.

4. **Run and record** — execute via `run_firmware_SITL_validation_campaign_tests.sh`, then refresh the spreadsheet so the new row gets Pass/Fail and log ref.

Mission/fence assets live beside the tests; keep waypoints **outside** exclusion/inclusion boundaries (with OA margin) unless the scenario deliberately tests breach or rejection.

### 5. Pull request to `MA-4.3.0.X`

When all required phases pass:

1. Push the feature branch
2. Open a PR **into `MA-4.3.0.X`**
3. In the PR description include:
   - `THISFIRMWARE` string and summary of changes
   - Path to `docs/<THISFIRMWARE>/<THISFIRMWARE>.xlsx` (Pass/Fail per phase)
   - Note any known autotest-only fixes vs firmware fixes
4. Wait for review and merge

### Command cheat sheet

| Step | Command |
|------|---------|
| Validate version + branch | `python3 Tools/autotest/firmware_SITL_validation_campaign.py validate` |
| Init / reset campaign | `./Tools/autotest/reset_firmware_SITL_validation_campaign.sh` |
| Run autotests | `./Tools/autotest/run_firmware_SITL_validation_campaign_tests.sh <0\|1\|2\|3> [TestName] [--skip-build]` |
| Update spreadsheet | `./Tools/autotest/generate_firmware_SITL_validation_campaign_artifacts.sh <phase>` |
| Add phase worksheet | `./Tools/autotest/add_firmware_SITL_validation_phase.sh <1\|2\|3>` |
