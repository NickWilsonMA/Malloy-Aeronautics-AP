#!/usr/bin/env bash
# Full upstream ArduPilot copter SITL regression (CI parity).
#
# Runs the same suites as .github/workflows/test_sitl_copter.yml:
#   CopterTests1a, 1b, 1c, 1d, 1e, 2a, 2b, testsMA
#
# Expect ~1-2 hours. Use run_oafastwp_phase0.sh for the faster P0-01..22 gate.
#
# Usage:
#   ./Tools/autotest/run_oafastwp_phase0_upstream.sh
#   ./Tools/autotest/run_oafastwp_phase0_upstream.sh --skip-build

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
    SKIP_BUILD=1
fi

UPSTREAM_SUITES=(
    test.CopterTests1a
    test.CopterTests1b
    test.CopterTests1c
    test.CopterTests1d
    test.CopterTests1e
    test.CopterTests2a
    test.CopterTests2b
    test.CopterTestsMA
)

for suite in "${UPSTREAM_SUITES[@]}"; do
    echo "=== Upstream regression: ${suite} ==="
    ./Tools/autotest/autotest.py "${suite}" --skip-build
done

echo "=== Full upstream copter regression: ALL PASSED ==="
