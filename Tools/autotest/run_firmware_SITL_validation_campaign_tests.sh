#!/usr/bin/env bash
# Run autotests for one phase (or a single test); logs -> campaign phase<N>/logs/
#
# Usage:
#   ./Tools/autotest/run_firmware_SITL_validation_campaign_tests.sh 0
#   ./Tools/autotest/run_firmware_SITL_validation_campaign_tests.sh 0 P0_22_RTL_BrakingDistance --skip-build
#   ./Tools/autotest/run_firmware_SITL_validation_campaign_tests.sh 0 test.CopterTestsOAfastWPPhase0.P0_22_RTL_BrakingDistance --skip-build
#
# Then always:
#   ./Tools/autotest/generate_firmware_SITL_validation_campaign_artifacts.sh 0

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
cd "${REPO_ROOT}"

PHASE="${1:-}"
if [[ ! "${PHASE}" =~ ^[0-3]$ ]]; then
    echo "Usage: $0 <0|1|2|3> [TestMethodOrFullPath] [--skip-build]" >&2
    exit 1
fi
shift || true

TEST=""
SKIP_BUILD=0
for arg in "$@"; do
    case "${arg}" in
        --skip-build) SKIP_BUILD=1 ;;
        *)
            if [[ -z "${TEST}" ]]; then
                TEST="${arg}"
            else
                echo "Unknown argument: ${arg}" >&2
                exit 1
            fi
            ;;
    esac
done

CAMPAIGN_PY="${SCRIPT_DIR}/firmware_SITL_validation_campaign.py"
XLSX="$(python3 "${CAMPAIGN_PY}" spreadsheet)"
if [[ ! -f "${XLSX}" ]]; then
    echo "Campaign not initialized. Run ./Tools/autotest/reset_firmware_SITL_validation_campaign.sh first." >&2
    exit 1
fi

BUILDLOGS="$(python3 "${CAMPAIGN_PY}" buildlogs "${PHASE}")"
mkdir -p "${BUILDLOGS}"
export BUILDLOGS

declare -A SUITES=(
    [0]='test.CopterTestsOAfastWPPhase0'
    [1]='test.CopterTestsOAfastWPPhase1'
    [2]='test.CopterTestsOAfastWPPhase2'
    [3]='test.CopterTestsOAfastWPPhase3'
)

if [[ "${SKIP_BUILD}" -eq 0 ]]; then
    echo "=== Building ArduCopter SITL ==="
    ./Tools/autotest/autotest.py build.Copter
fi

if [[ -n "${TEST}" ]]; then
    if [[ "${TEST}" == test.* ]]; then
        TARGET="${TEST}"
    else
        TARGET="${SUITES[${PHASE}]}.${TEST}"
    fi
    echo "=== Phase ${PHASE}: re-running ${TARGET} ==="
else
    TARGET="${SUITES[${PHASE}]}"
    echo "=== Phase ${PHASE}: running full suite ${TARGET} ==="
fi

echo "=== Logs: ${BUILDLOGS} ==="
set +e
./Tools/autotest/autotest.py "${TARGET}"
AUTOTEST_RC=$?
set -e

python3 "${CAMPAIGN_PY}" summarize "${PHASE}" || true

echo ""
if [[ "${AUTOTEST_RC}" -eq 0 ]]; then
    echo "=== Autotest complete (all tests in this run passed) ==="
else
    echo "=== Autotest complete (one or more tests failed — see summary above) ==="
fi
echo "Next: ./Tools/autotest/generate_firmware_SITL_validation_campaign_artifacts.sh ${PHASE}"
exit "${AUTOTEST_RC}"
