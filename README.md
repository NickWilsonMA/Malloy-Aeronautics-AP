# Malloy Aeronautics — ArduPilot Fork

Custom ArduPilot firmware for Malloy Aeronautics vehicles. This repository tracks Malloy-specific changes on top of upstream ArduPilot **4.3.0**. The integration branch is **`MA-4.3.0.X`** (not upstream `master`).

**Repository:** [github.com/Malloy-Aeronautics/Malloy-Aeronautics-AP](https://github.com/Malloy-Aeronautics/Malloy-Aeronautics-AP)

### What we changed (high level)

- **Obstacle avoidance (OA) / Dijkstra path planner** — fence-aware routing for AUTO, GUIDED (with `GUID_OPTIONS`), and RTL.
- **SITL validation harness** — phased unattended autotests with logs under `docs/<THISFIRMWARE>/` and a campaign spreadsheet.

Upstream ArduPilot documentation still applies for general build/dev topics: [ardupilot.org/dev](https://ardupilot.org/dev/).

---

## Firmware update workflow

Every feature firmware update follows the same process on **`MA-4.3.0.X`**.

### 1. Create a feature branch

On GitHub (or locally):

1. Go to **Branches → New branch**
2. **Source branch:** `MA-4.3.0.X`
3. **Branch name:** short feature name (must match the suffix you will use in `version.h`), e.g. `my-feature-name`

```bash
git fetch origin
git checkout -b my-feature-name origin/MA-4.3.0.X
```

### 2. Bump `ArduCopter/version.h` (first commit on the branch)

Edit `THISFIRMWARE` **before** starting code changes. Format:

```c
#define THISFIRMWARE "MA_COPTER-V4.3.0.16-my-feature-name"
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
  Phase1/logs/ …                     (when additional phases are added)
  <THISFIRMWARE>.xlsx              (Intro + phase tabs; columns E–G = Pass/Fail, Re-runs, Log ref)
  README.txt
```

#### Register tests in the spreadsheet first

**Before** implementing autotest code, register each new test in `Tools/autotest/oafastwp_spreadsheet_data.py`:

1. **Test ID** — `P0-xx` (Phase 0 regression) or `SITL-xx` (feature SITL)
2. **Test case** — short title
3. **Setup / Action** — what the scenario does
4. **Expected result** — pass criteria

Add the row to `P0_ROWS` (Phase 0) or `SITL_ROWS` (feature tests). Re-run campaign init or `add_firmware_SITL_validation_phase.sh` so the worksheet shows columns A–D populated (Pass/Fail columns E–G stay empty until you run tests).

#### Then add the autotest in the repo

| Phase | Purpose | Where to implement |
|-------|---------|-------------------|
| **0** | Generic firmware regression on every update (`P0-01`..`P0-22`) | `Tools/autotest/oafastwp_phase0.py` (often delegates to upstream tests in `arducopter.py`) |
| **1** | Feature SITL regression (`SITL-xx`) | `Tools/autotest/oafastwp_phase1.py` and mission/fence assets under `Tools/autotest/ArduCopter_Tests/OAfastWP_Regression_Assets/` |
| **2–3** | **Optional** — only if you need to **split** autotests into separate run gates | `Tools/autotest/arducopter.py` (`OAfastWP_*` methods) and register in the phase runner |

Use **Phase 2 and Phase 3 only when you deliberately want separate test runs** (for example a broad Phase 1 matrix, then a smaller acceptance gate). If all feature tests can run together, keep them in **Phase 1** — extra phases are not required.

After the autotest exists, also update in `oafastwp_spreadsheet_data.py`:

- `PHASE_AUTOTEST` mapping (Test ID → autotest method name)
- Phase test list used for log collection (`Tools/autotest/generate_oafastwp_visual_evidence.py`)

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

This refreshes phase tabs that have logs on disk (columns **E** Pass/Fail, **F** Re-runs to pass, **G** Log ref). Deliverables are **logs + spreadsheet only**.

Repeat **register → implement → run → triage → fix → re-run → update spreadsheet** until required phases are all PASS.

Add feature phase tabs when Phase 0 passes:

```bash
./Tools/autotest/add_firmware_SITL_validation_phase.sh 1
./Tools/autotest/run_firmware_SITL_validation_campaign_tests.sh 1
./Tools/autotest/generate_firmware_SITL_validation_campaign_artifacts.sh 1
```

Add Phase 2 or 3 only when you need a separate gate; same commands with phase `2` or `3`.

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
| Add phase worksheet | `./Tools/autotest/add_firmware_SITL_validation_phase.sh <1\|2\|3>` |
| Run autotests | `./Tools/autotest/run_firmware_SITL_validation_campaign_tests.sh <0\|1\|2\|3> [TestName] [--skip-build]` |
| Update spreadsheet | `./Tools/autotest/generate_firmware_SITL_validation_campaign_artifacts.sh <phase>` |
