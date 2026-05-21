#!/usr/bin/env bash
# Smart campaign artifacts (detects reruns, updates spreadsheet, prints paths).
#
# Usage:
#   ./Tools/autotest/generate_firmware_SITL_validation_campaign_artifacts.sh 0
#
# Workflow:
#   1. ./Tools/autotest/run_firmware_SITL_validation_campaign_tests.sh 0
#   2. ./Tools/autotest/run_firmware_SITL_validation_campaign_tests.sh 0 P0_07_Landing --skip-build
#   3. ./Tools/autotest/generate_firmware_SITL_validation_campaign_artifacts.sh 0

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
cd "${REPO_ROOT}"

PHASE="${1:-}"
if [[ ! "${PHASE}" =~ ^[0-3]$ ]]; then
    echo "Usage: $0 <0|1|2|3>" >&2
    exit 1
fi

exec python3 "${SCRIPT_DIR}/firmware_SITL_validation_campaign_artifacts.py" "${PHASE}"
