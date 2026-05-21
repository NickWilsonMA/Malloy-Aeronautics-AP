# Malloy Aeronautics — ArduPilot Fork

Custom ArduPilot firmware for Malloy Aeronautics vehicles. This repository tracks Malloy-specific changes on top of upstream ArduPilot **4.3.0**. The integration branch is **`MA-4.3.0.X`** (not upstream `master`).

**Repository:** [github.com/Malloy-Aeronautics/Malloy-Aeronautics-AP](https://github.com/Malloy-Aeronautics/Malloy-Aeronautics-AP)

### What we changed (high level)

- **Obstacle avoidance (OA) / Dijkstra path planner** — fence-aware routing for AUTO, GUIDED, and RTL.
- **OA fast waypoints** — smoother mission legs through Dijkstra path points when enabled.
- **Fence breach escape vector** — shortest escape from exclusion breach, automatic RTL hand-off, repeated breach cycles (see branch `OA-fastWP-fenceEscapeVector`).
- **SITL validation harness** — phased unattended autotests (Phase 0 firmware regression → feature phases) with spreadsheet, HTML/RTF reports, and visual evidence under `docs/`.

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

### 4. Start the SITL validation campaign

When ready to test, reset the campaign template (reads `THISFIRMWARE`, creates `docs/` tree + spreadsheet):

```bash
./Tools/autotest/reset_firmware_SITL_validation_campaign.sh
```

Creates:

```
docs/MA_COPTER-V4.3.0.16-OA-fastWP-fenceEscapeVector/
├── MA_COPTER-V4.3.0.16-OA-fastWP-fenceEscapeVector.xlsx   # Intro + Phase 0 tab
├── README.txt
└── phase0/{logs,visual_evidence,report}/
```

### 5. Run Phase 0 autotests (firmware regression)

```bash
./Tools/autotest/run_firmware_SITL_validation_campaign_tests.sh 0
```

- Builds ArduCopter SITL (first run), runs P0-01..P0-22
- Logs → `phase0/logs/` (`.txt`, `.tlog`, `.BIN`)
- Prints **PASS/FAIL** per test and **re-run commands** for failures

Re-run a single failed test:

```bash
./Tools/autotest/run_firmware_SITL_validation_campaign_tests.sh 0 P0_07_Landing --skip-build
```

### 6. Generate reports and visual evidence

After a test run (full or partial), generate artifacts:

```bash
./Tools/autotest/generate_firmware_SITL_validation_campaign_artifacts.sh 0
```

- Updates spreadsheet columns E–F (Pass/Fail, log ref)
- Creates **timestamped** folders under `phase0/visual_evidence/` and `phase0/report/`
- `latest/` symlink → newest run (re-running individual tests then re-generating creates a **new** timestamp folder so a second trial is visible)
- Phase 0: RTF + HTML firmware regression report + visual dashboard

Open:

- `docs/<THISFIRMWARE>/phase0/visual_evidence/latest/index.html`
- `docs/<THISFIRMWARE>/phase0/report/latest/`

Repeat **run → fix → re-run → generate artifacts** until Phase 0 is all PASS.

### 7. Later phases (feature-specific)

When Phase 0 passes:

```bash
./Tools/autotest/add_firmware_SITL_validation_phase.sh 1   # fence regression SITL-01..23
./Tools/autotest/run_firmware_SITL_validation_campaign_tests.sh 1
./Tools/autotest/generate_firmware_SITL_validation_campaign_artifacts.sh 1
```

Same pattern for phases 2 and 3 (fast-WP integration, breach escape).

### 8. Pull request to `MA-4.3.0.X`

When all required phases pass:

1. Push the feature branch
2. Open a PR **into `MA-4.3.0.X`**
3. In the PR description include:
   - `THISFIRMWARE` string and summary of changes
   - Link to `docs/<THISFIRMWARE>/` evidence (spreadsheet, Phase 0 report, dashboards)
   - Pass/fail summary per phase
4. Wait for review and merge

### Command cheat sheet

| Step | Command |
|------|---------|
| Validate version + branch | `python3 Tools/autotest/firmware_SITL_validation_campaign.py validate` |
| Init campaign template | `./Tools/autotest/reset_firmware_SITL_validation_campaign.sh` |
| Run autotests | `./Tools/autotest/run_firmware_SITL_validation_campaign_tests.sh <0\|1\|2\|3> [TestName] [--skip-build]` |
| Reports + spreadsheet | `./Tools/autotest/generate_firmware_SITL_validation_campaign_artifacts.sh <phase>` |
| Add phase worksheet | `./Tools/autotest/add_firmware_SITL_validation_phase.sh <1\|2\|3>` |

---

# ArduPilot Project

<a href="https://ardupilot.org/discord"><img src="https://img.shields.io/discord/674039678562861068.svg" alt="Discord">

[![Test Copter](https://github.com/ArduPilot/ardupilot/workflows/test%20copter/badge.svg?branch=master)](https://github.com/ArduPilot/ardupilot/actions/workflows/test_sitl_copter.yml) [![Test Plane](https://github.com/ArduPilot/ardupilot/workflows/test%20plane/badge.svg?branch=master)](https://github.com/ArduPilot/ardupilot/actions/workflows/test_sitl_plane.yml) [![Test Rover](https://github.com/ArduPilot/ardupilot/workflows/test%20rover/badge.svg?branch=master)](https://github.com/ArduPilot/ardupilot/actions/workflows/test_sitl_rover.yml) [![Test Sub](https://github.com/ArduPilot/ardupilot/workflows/test%20sub/badge.svg?branch=master)](https://github.com/ArduPilot/ardupilot/actions/workflows/test_sitl_sub.yml) [![Test Tracker](https://github.com/ArduPilot/ardupilot/workflows/test%20tracker/badge.svg?branch=master)](https://github.com/ArduPilot/ardupilot/actions/workflows/test_sitl_tracker.yml)

[![Test AP_Periph](https://github.com/ArduPilot/ardupilot/workflows/test%20ap_periph/badge.svg?branch=master)](https://github.com/ArduPilot/ardupilot/actions/workflows/test_sitl_periph.yml) [![Test Chibios](https://github.com/ArduPilot/ardupilot/workflows/test%20chibios/badge.svg?branch=master)](https://github.com/ArduPilot/ardupilot/actions/workflows/test_chibios.yml) [![Test Linux SBC](https://github.com/ArduPilot/ardupilot/workflows/test%20Linux%20SBC/badge.svg?branch=master)](https://github.com/ArduPilot/ardupilot/actions/workflows/test_linux_sbc.yml) [![Test Replay](https://github.com/ArduPilot/ardupilot/workflows/test%20replay/badge.svg?branch=master)](https://github.com/ArduPilot/ardupilot/actions/workflows/test_replay.yml)

[![Test Unit Tests](https://github.com/ArduPilot/ardupilot/workflows/test%20unit%20tests/badge.svg?branch=master)](https://github.com/ArduPilot/ardupilot/actions/workflows/test_unit_tests.yml) [![test size](https://github.com/ArduPilot/ardupilot/actions/workflows/test_size.yml/badge.svg)](https://github.com/ArduPilot/ardupilot/actions/workflows/test_size.yml)

[![Test Environment Setup](https://github.com/ArduPilot/ardupilot/actions/workflows/test_environment.yml/badge.svg?branch=master)](https://github.com/ArduPilot/ardupilot/actions/workflows/test_environment.yml)

[![Cygwin Build](https://github.com/ArduPilot/ardupilot/actions/workflows/cygwin_build.yml/badge.svg)](https://github.com/ArduPilot/ardupilot/actions/workflows/cygwin_build.yml) [![Macos Build](https://github.com/ArduPilot/ardupilot/actions/workflows/macos_build.yml/badge.svg)](https://github.com/ArduPilot/ardupilot/actions/workflows/macos_build.yml)

[![Coverity Scan Build Status](https://scan.coverity.com/projects/5331/badge.svg)](https://scan.coverity.com/projects/ardupilot-ardupilot)

[![Test Coverage](https://github.com/ArduPilot/ardupilot/actions/workflows/test_coverage.yml/badge.svg?branch=master)](https://github.com/ArduPilot/ardupilot/actions/workflows/test_coverage.yml)

[![Autotest Status](https://autotest.ardupilot.org/autotest-badge.svg)](https://autotest.ardupilot.org/)

ArduPilot is the most advanced, full-featured, and reliable open source autopilot software available.
It has been under development since 2010 by a diverse team of professional engineers, computer scientists, and community contributors.
Our autopilot software is capable of controlling almost any vehicle system imaginable, from conventional airplanes, quad planes, multi-rotors, and helicopters to rovers, boats, balance bots, and even submarines.
It is continually being expanded to provide support for new emerging vehicle types.

## The ArduPilot project is made up of: ##

- ArduCopter: [code](https://github.com/ArduPilot/ardupilot/tree/master/ArduCopter), [wiki](https://ardupilot.org/copter/index.html)

- ArduPlane: [code](https://github.com/ArduPilot/ardupilot/tree/master/ArduPlane), [wiki](https://ardupilot.org/plane/index.html)

- Rover: [code](https://github.com/ArduPilot/ardupilot/tree/master/Rover), [wiki](https://ardupilot.org/rover/index.html)

- ArduSub : [code](https://github.com/ArduPilot/ardupilot/tree/master/ArduSub), [wiki](http://ardusub.com/)

- Antenna Tracker : [code](https://github.com/ArduPilot/ardupilot/tree/master/AntennaTracker), [wiki](https://ardupilot.org/antennatracker/index.html)

## User Support & Discussion Forums ##

- Support Forum: <https://discuss.ardupilot.org/>

- Community Site: <https://ardupilot.org>

## Developer Information ##

- Github repository: <https://github.com/ArduPilot/ardupilot>

- Main developer wiki: <https://ardupilot.org/dev/>

- Developer discussion: <https://discuss.ardupilot.org>

- Developer chat: <https://discord.com/channels/ardupilot>

## Top Contributors ##

- [Flight code contributors](https://github.com/ArduPilot/ardupilot/graphs/contributors)
- [Wiki contributors](https://github.com/ArduPilot/ardupilot_wiki/graphs/contributors)
- [Most active support forum users](https://discuss.ardupilot.org/u?order=post_count&period=quarterly)
- [Partners who contribute financially](https://ardupilot.org/about/Partners)

## How To Get Involved ##

- The ArduPilot project is open source and we encourage participation and code contributions: [guidelines for contributors to the ardupilot codebase](https://ardupilot.org/dev/docs/contributing.html)

- We have an active group of Beta Testers to help us improve our code: [release procedures](https://ardupilot.org/dev/docs/release-procedures.html)

- Desired Enhancements and Bugs can be posted to the [issues list](https://github.com/ArduPilot/ardupilot/issues).

- Help other users with log analysis in the [support forums](https://discuss.ardupilot.org/)

- Improve the wiki and chat with other [wiki editors on Discord #documentation](https://discord.com/channels/ardupilot)

- Contact the developers on one of the [communication channels](https://ardupilot.org/copter/docs/common-contact-us.html)

## License ##

The ArduPilot project is licensed under the GNU General Public
License, version 3.

- [Overview of license](https://dev.ardupilot.com/wiki/license-gplv3)

- [Full Text](https://github.com/ArduPilot/ardupilot/blob/master/COPYING.txt)

## Maintainers ##

ArduPilot is comprised of several parts, vehicles and boards. The list below
contains the people that regularly contribute to the project and are responsible
for reviewing patches on their specific area.

- [Andrew Tridgell](https://github.com/tridge):
  - ***Vehicle***: Plane, AntennaTracker
  - ***Board***: Pixhawk, Pixhawk2, PixRacer
- [Francisco Ferreira](https://github.com/oxinarf):
  - ***Bug Master***
- [Grant Morphett](https://github.com/gmorph):
  - ***Vehicle***: Rover
- [Willian Galvani](https://github.com/williangalvani):
  - ***Vehicle***: Sub
- [Lucas De Marchi](https://github.com/lucasdemarchi):
  - ***Subsystem***: Linux
- [Michael du Breuil](https://github.com/WickedShell):
  - ***Subsystem***: Batteries
  - ***Subsystem***: GPS
  - ***Subsystem***: Scripting
- [Peter Barker](https://github.com/peterbarker):
  - ***Subsystem***: DataFlash, Tools
- [Randy Mackay](https://github.com/rmackay9):
  - ***Vehicle***: Copter, Rover, AntennaTracker
- [Siddharth Purohit](https://github.com/bugobliterator):
  - ***Subsystem***: CAN, Compass
  - ***Board***: Cube*
- [Tom Pittenger](https://github.com/magicrub):
  - ***Vehicle***: Plane
- [Bill Geyer](https://github.com/bnsgeyer):
  - ***Vehicle***: TradHeli
- [Emile Castelnuovo](https://github.com/emilecastelnuovo):
  - ***Board***: VRBrain
- [Georgii Staroselskii](https://github.com/staroselskii):
  - ***Board***: NavIO
- [Gustavo José de Sousa](https://github.com/guludo):
  - ***Subsystem***: Build system
- [Julien Beraud](https://github.com/jberaud):
  - ***Board***: Bebop & Bebop 2
- [Leonard Hall](https://github.com/lthall):
  - ***Subsystem***: Copter attitude control and navigation
- [Matt Lawrence](https://github.com/Pedals2Paddles):
  - ***Vehicle***: 3DR Solo & Solo based vehicles
- [Matthias Badaire](https://github.com/badzz):
  - ***Subsystem***: FRSky
- [Mirko Denecke](https://github.com/mirkix):
  - ***Board***: BBBmini, BeagleBone Blue, PocketPilot
- [Paul Riseborough](https://github.com/priseborough):
  - ***Subsystem***: AP_NavEKF2
  - ***Subsystem***: AP_NavEKF3
- [Víctor Mayoral Vilches](https://github.com/vmayoral):
  - ***Board***: PXF, Erle-Brain 2, PXFmini
- [Amilcar Lucas](https://github.com/amilcarlucas):
  - ***Subsystem***: Marvelmind
- [Samuel Tabor](https://github.com/samuelctabor):
  - ***Subsystem***: Soaring/Gliding
- [Henry Wurzburg](https://github.com/Hwurzburg):
  - ***Subsystem***: OSD
  - ***Site***: Wiki
- [Peter Hall](https://github.com/IamPete1):
  - ***Vehicle***: Tailsitters
  - ***Vehicle***: Sailboat
  - ***Subsystem***: Scripting
- [Andy Piper](https://github.com/andyp1per):
  - ***Subsystem***: Crossfire
  - ***Subsystem***: ESC
  - ***Subsystem***: OSD
  - ***Subsystem***: SmartAudio
- [Alessandro Apostoli ](https://github.com/yaapu):
  - ***Subsystem***: Telemetry
  - ***Subsystem***: OSD
- [Rishabh Singh ](https://github.com/rishabsingh3003):
  - ***Subsystem***: Avoidance/Proximity
- [David Bussenschutt ](https://github.com/davidbuzz):
  - ***Subsystem***: ESP32,AP_HAL_ESP32
- [Charles Villard ](https://github.com/Silvanosky):
  - ***Subsystem***: ESP32,AP_HAL_ESP32
