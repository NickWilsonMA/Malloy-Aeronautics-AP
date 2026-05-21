#!/usr/bin/env bash
# Phase 2: SITL-14, 17, 23, 29, 32 (copter, unattended).
#
#   OAfastWP_GuidedInsideExclusion              SITL-29
#   OAfastWP_BreachEscape_ModeChangeAtStandoff  SITL-32
#   OAfastWP_RTL_BlockedPath                    SITL-14
#   OAfastWP_FastWaypoints_Mission              SITL-17
#   OAfastWP_ThreePointDogleg                   SITL-23
#
# Usage (from repo root):
#   ./Tools/autotest/run_oafastwp_phase2.sh
#   ./Tools/autotest/run_oafastwp_phase2.sh --skip-build

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

echo "=== Running OAfastWP Phase 2 autotests (SITL-14, 17, 23, 29, 32) ==="
./Tools/autotest/autotest.py test.CopterTestsOAfastWPPhase2

echo "=== Generating Phase 2 evidence report ==="
python3 "${SCRIPT_DIR}/generate_oafastwp_phase2_report.py"

echo "=== Generating Phase 2 visual validation dashboard ==="
python3 "${SCRIPT_DIR}/generate_oafastwp_visual_evidence.py" --phase 2

echo "=== Updating spreadsheet (Phase 2) ==="
python3 "${SCRIPT_DIR}/update_fence_escape_spreadsheet.py" --phase 2

echo "=== OAfastWP Phase 2: ALL PASSED ==="
