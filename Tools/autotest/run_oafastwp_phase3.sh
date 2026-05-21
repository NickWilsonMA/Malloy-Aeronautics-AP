#!/usr/bin/env bash
# Phase 3: SITL-25..31 fence escape vector (copter, unattended).
#
# Covers spreadsheet items SITL-25, 26, 27, 28, 30, 31 via autotest:
#   OAfastWP_BreachEscape_RTL_Home
#   OAfastWP_MissionWP_InsideExclusion
#   OAfastWP_BreachEscape_RepeatedCycles
#
# Usage (from repo root):
#   ./Tools/autotest/run_oafastwp_phase3.sh
#   ./Tools/autotest/run_oafastwp_phase3.sh --skip-build
#
# Run a single subtest:
#   ./Tools/autotest/autotest.py test.CopterTestsOAfastWPPhase3.OAfastWP_BreachEscape_RTL_Home

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

echo "=== Running OAfastWP Phase 3 autotests (SITL-25..31) ==="
./Tools/autotest/autotest.py test.CopterTestsOAfastWPPhase3

echo "=== Generating Phase 3 evidence report ==="
python3 "${SCRIPT_DIR}/generate_oafastwp_phase3_report.py"

echo "=== Generating Phase 3 visual validation dashboard ==="
python3 "${SCRIPT_DIR}/generate_oafastwp_visual_evidence.py" --phase 3

echo "=== Updating spreadsheet (Phase 3) ==="
python3 "${SCRIPT_DIR}/update_fence_escape_spreadsheet.py" --phase 3

echo "=== OAfastWP Phase 3: ALL PASSED ==="
