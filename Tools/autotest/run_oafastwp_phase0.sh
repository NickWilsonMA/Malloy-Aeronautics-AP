#!/usr/bin/env bash
# Phase 0: firmware-update regression gate (copter, unattended).
#
# Curated upstream ArduPilot autotests (P0-01..22) + Malloy Dijkstra baseline.
# Run this before OAfastWP Phase 1..3 on every new firmware build.
#
# Upstream source mapping:
#   P0-01..03  common.py base (Parameters, ArmFeatures, Logging)
#   P0-04..10  CopterTests1a/1c/1d (modes, mission, guided)
#   P0-11..13  CopterTests1b/1d (fence, failsafe)
#   P0-14..17  CopterTests2b (RTL, WPNAV, DataFlash)
#   P0-18      CopterTests1e (ParameterChecks)
#   P0-19..22  CopterTestsMA (Dijkstra fence recovery + RTL braking)
#
# Full upstream CI parity (1a+1b+1c+1d+1e+2a+2b+MA, ~1-2 hours):
#   ./Tools/autotest/run_oafastwp_phase0_upstream.sh
#
# Usage:
#   ./Tools/autotest/run_oafastwp_phase0.sh
#   ./Tools/autotest/run_oafastwp_phase0.sh --skip-build

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
cd "${REPO_ROOT}"

SKIP_BUILD=0
for arg in "$@"; do
    case "${arg}" in
        --skip-build) SKIP_BUILD=1 ;;
        -h|--help)
            echo "Usage: $0 [--skip-build]"
            exit 0
            ;;
        *)
            echo "Unknown argument: ${arg}" >&2
            exit 1
            ;;
    esac
done

if [[ "${SKIP_BUILD}" -eq 0 ]]; then
    echo "=== Building ArduCopter SITL ==="
    ./Tools/autotest/autotest.py build.Copter
fi

echo "=== Running Phase 0 firmware regression (P0-01..22) ==="
./Tools/autotest/autotest.py test.CopterTestsOAfastWPPhase0

echo "=== Generating Phase 0 visual validation dashboard ==="
python3 "${SCRIPT_DIR}/generate_oafastwp_visual_evidence.py" --phase 0

echo "=== Updating spreadsheet (Phase 0) ==="
python3 "${SCRIPT_DIR}/update_fence_escape_spreadsheet.py" --phase 0

echo "=== Phase 0: ALL PASSED ==="
