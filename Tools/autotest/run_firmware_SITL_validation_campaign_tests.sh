#!/usr/bin/env bash
# Run autotests for one phase (or a single test).
#
# Logs layout under Phase<N>/logs/:
#   full_<timestamp>/<TestName>/              — full phase run
#   rerun_<timestamp>-<TestName>/<TestName>/ — individual re-run (+ run_results.json)
#   run_results.json                         — all reruns aggregate (run_kind: reruns)
#
# Usage:
#   ./Tools/autotest/run_firmware_SITL_validation_campaign_tests.sh 0
#   ./Tools/autotest/run_firmware_SITL_validation_campaign_tests.sh 0 P0_22_RTL_BrakingDistance --skip-build

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

PRIMARY_TEST=""
if [[ -n "${TEST}" ]]; then
    RUN_KIND="rerun"
    if [[ "${TEST}" == test.* ]]; then
        PRIMARY_TEST="${TEST##*.}"
    else
        PRIMARY_TEST="${TEST}"
    fi
else
    RUN_KIND="full"
fi

STAGING="$(python3 "${CAMPAIGN_PY}" begin-run "${PHASE}" "${RUN_KIND}" "${PRIMARY_TEST}")"
export BUILDLOGS="${STAGING}"

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
    echo "=== Phase ${PHASE}: re-running ${TARGET} (${RUN_KIND} -> rerun_*-${PRIMARY_TEST}) ==="
else
    TARGET="${SUITES[${PHASE}]}"
    echo "=== Phase ${PHASE}: running full suite ${TARGET} (${RUN_KIND} run) ==="
fi

echo "=== Staging logs: ${BUILDLOGS} ==="
set +e
./Tools/autotest/autotest.py "${TARGET}"
AUTOTEST_RC=$?
set -e

echo ""
echo "=== Organizing logs ==="
python3 "${CAMPAIGN_PY}" finalize-run "${PHASE}" "${STAGING}" "${RUN_KIND}" "${PRIMARY_TEST}"

python3 "${CAMPAIGN_PY}" summarize "${PHASE}" || true

echo ""
if [[ "${AUTOTEST_RC}" -eq 0 ]]; then
    echo "=== Autotest complete (all tests in this run passed) ==="
else
    echo "=== Autotest complete (one or more tests failed — see run_results.json) ==="
fi
echo "Next: ./Tools/autotest/generate_firmware_SITL_validation_campaign_artifacts.sh ${PHASE}"
exit "${AUTOTEST_RC}"
