#!/usr/bin/env python3
"""Paths and layout for a firmware SITL validation campaign under docs/."""

from __future__ import print_function

import json
import os
import re
import subprocess
from datetime import datetime

# Workbook cover / campaign intro (Phase 0 is generic firmware regression on every update).
CAMPAIGN_TITLE = 'Firmware Update — SITL Test Report'
PHASE0_WORKSHEET_NAME = 'Firmware regression (P0-01..22)'
FIRMWARE_REGRESSION_REPORT_TITLE = 'Firmware Update Regression — SITL Evidence Report'
FIRMWARE_REGRESSION_RTF_NAME = 'Firmware_Regression_Report.rtf'
FIRMWARE_REGRESSION_DASHBOARD_TITLE = 'Firmware update regression (P0-01..22)'

RESET_SCRIPT = './Tools/autotest/reset_firmware_SITL_validation_campaign.sh'
RUN_TESTS_SCRIPT = './Tools/autotest/run_firmware_SITL_validation_campaign_tests.sh'
GENERATE_ARTIFACTS_SCRIPT = './Tools/autotest/generate_firmware_SITL_validation_campaign_artifacts.sh'
ADD_PHASE_SCRIPT = './Tools/autotest/add_firmware_SITL_validation_phase.sh'

PHASE_SUBDIRS = ('logs', 'visual_evidence', 'report')

_CONFIG_FILENAME = 'firmware_SITL_validation_campaign_config.json'
_DEFAULT_BRANCHES = frozenset(['main', 'master', 'develop', 'devel', 'trunk'])

# Populated from config written by reset_firmware_SITL_validation_campaign.sh
CAMPAIGN_ID = None
FIRMWARE_VERSION = None
CAMPAIGN_FEATURE = None
GIT_BRANCH = None


def _repo_root():
    return os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))


def _config_path():
    return os.path.join(os.path.dirname(__file__), _CONFIG_FILENAME)


def _version_h_path():
    return os.path.join(_repo_root(), 'ArduCopter', 'version.h')


def parse_arducopter_firmware_version(version_h_path=None):
    '''Parse firmware version string from ArduCopter/version.h (THISFIRMWARE or FW_*).'''
    version_h_path = version_h_path or _version_h_path()
    with open(version_h_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # THISFIRMWARE line may use straight or Unicode quotes, e.g.
    # MA_COPTER-V4.3.0.16-DEV-OAfastWP
    line_m = re.search(r'#define\s+THISFIRMWARE\s+(.+)$', content, re.MULTILINE)
    if line_m:
        line = line_m.group(1)
        for pattern in (
            r'V(\d+\.\d+\.\d+\.\d+)',  # 4-part Malloy build (preferred)
            r'V(\d+\.\d+\.\d+)',
            r'V(\d+\.\d+)',
        ):
            m = re.search(pattern, line)
            if m:
                return m.group(1)

    major = _macro_int(content, 'FW_MAJOR')
    minor = _macro_int(content, 'FW_MINOR')
    patch = _macro_int(content, 'FW_PATCH')
    if major is not None and minor is not None and patch is not None:
        return '%d.%d.%d' % (major, minor, patch)
    return None


def _macro_int(content, name):
    m = re.search(r'#define\s+%s\s+(\d+)' % re.escape(name), content)
    return int(m.group(1)) if m else None


def get_git_branch():
    try:
        out = subprocess.check_output(
            ['git', 'rev-parse', '--abbrev-ref', 'HEAD'],
            cwd=_repo_root(),
            stderr=subprocess.STDOUT,
            universal_newlines=True,
        ).strip()
    except (subprocess.CalledProcessError, OSError):
        return None
    if not out or out == 'HEAD':
        return None
    return out


def sanitize_branch_for_campaign_id(branch):
    branch = branch.strip().replace('/', '-')
    branch = re.sub(r'[^\w.\-]+', '-', branch)
    branch = re.sub(r'-+', '-', branch).strip('-')
    return branch


def build_campaign_id(firmware_version, branch):
    return '%s-%s' % (firmware_version, sanitize_branch_for_campaign_id(branch))


def validate_repo_for_campaign(strict_branch=True):
    errors = []
    version_h = _version_h_path()
    firmware_version = None

    if not os.path.isfile(version_h):
        errors.append('ArduCopter/version.h not found at %s.' % version_h)
    else:
        firmware_version = parse_arducopter_firmware_version(version_h)
        if not firmware_version:
            errors.append(
                'Could not parse firmware version from ArduCopter/version.h. '
                'Set THISFIRMWARE (e.g. MA_COPTER-V4.3.0.16-...) or FW_MAJOR/MINOR/PATCH.',
            )

    branch = get_git_branch()
    if branch is None:
        errors.append(
            'Not on a named git branch (detached HEAD?). '
            'Check out the feature branch under test: git checkout <branch>',
        )
    elif strict_branch and branch in _DEFAULT_BRANCHES:
        errors.append(
            'Currently on default branch "%s". '
            'Check out the feature branch under test: git checkout <branch>' % branch,
        )

    return firmware_version, branch, errors


def write_campaign_config(firmware_version, branch):
    campaign_id = build_campaign_id(firmware_version, branch)
    data = {
        'campaign_id': campaign_id,
        'firmware_version': firmware_version,
        'git_branch': branch,
        'version_h': os.path.relpath(_version_h_path(), _repo_root()),
        'prepared_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
    }
    with open(_config_path(), 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2)
        f.write('\n')
    _apply_config(data)
    return data


def load_campaign_config(require=True):
    path = _config_path()
    if not os.path.isfile(path):
        if require:
            _campaign_not_initialized_message()
        return None
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def _apply_config(cfg):
    global CAMPAIGN_ID, FIRMWARE_VERSION, CAMPAIGN_FEATURE, GIT_BRANCH
    if not cfg:
        CAMPAIGN_ID = None
        FIRMWARE_VERSION = None
        CAMPAIGN_FEATURE = None
        GIT_BRANCH = None
        return
    CAMPAIGN_ID = cfg['campaign_id']
    FIRMWARE_VERSION = cfg['firmware_version']
    GIT_BRANCH = cfg.get('git_branch', '')
    CAMPAIGN_FEATURE = GIT_BRANCH


def _campaign_not_initialized_message():
    print('Firmware SITL validation campaign is not initialized.', file=__import__('sys').stderr)
    print('', file=__import__('sys').stderr)
    print('From repo root, run:', file=__import__('sys').stderr)
    print('  %s' % RESET_SCRIPT, file=__import__('sys').stderr)
    print('', file=__import__('sys').stderr)
    print('That script reads ArduCopter/version.h and the current git branch, then creates', file=__import__('sys').stderr)
    print('docs/<version>-<branch>/ with the spreadsheet template.', file=__import__('sys').stderr)


def require_campaign_config():
    cfg = load_campaign_config(require=True)
    if cfg is None:
        raise SystemExit(1)
    return cfg


def prepare_campaign_from_repo(force=False):
    firmware_version, branch, errors = validate_repo_for_campaign(strict_branch=not force)
    if errors:
        print('Cannot prepare firmware SITL validation campaign:', file=__import__('sys').stderr)
        for err in errors:
            print('  - %s' % err, file=__import__('sys').stderr)
        print('', file=__import__('sys').stderr)
        print('Before running %s:' % RESET_SCRIPT, file=__import__('sys').stderr)
        print('  1. Check out the feature branch under test (git checkout <branch>).', file=__import__('sys').stderr)
        print('  2. Update ArduCopter/version.h (THISFIRMWARE / FW_* version).', file=__import__('sys').stderr)
        return 1

    cfg = write_campaign_config(firmware_version, branch)
    print('Campaign ID:      %s' % cfg['campaign_id'])
    print('Firmware version: %s  (from %s)' % (cfg['firmware_version'], cfg['version_h']))
    print('Git branch:       %s' % cfg['git_branch'])
    print('Evidence folder:  docs/%s/' % cfg['campaign_id'])
    return 0


def campaign_root():
    require_campaign_config()
    return os.path.join(_repo_root(), 'docs', CAMPAIGN_ID)


def spreadsheet_path():
    require_campaign_config()
    return os.path.join(campaign_root(), '%s.xlsx' % CAMPAIGN_ID)


def phase_dir(phase):
    return os.path.join(campaign_root(), 'phase%d' % int(phase))


def phase_buildlogs(phase):
    return os.path.join(phase_dir(phase), 'logs')


def phase_visual_evidence(phase):
    return os.path.join(phase_dir(phase), 'visual_evidence')


def phase_report(phase):
    return os.path.join(phase_dir(phase), 'report')


def log_ref_relative(phase, filename):
    return 'phase%d/logs/%s' % (int(phase), filename)


def ensure_phase_dirs(phase):
    phase = int(phase)
    os.makedirs(phase_buildlogs(phase), exist_ok=True)
    os.makedirs(phase_visual_evidence(phase), exist_ok=True)
    os.makedirs(phase_report(phase), exist_ok=True)
    return phase_dir(phase)


def ensure_campaign_dirs(phases=(0,)):
    os.makedirs(campaign_root(), exist_ok=True)
    for phase in phases:
        ensure_phase_dirs(phase)
    return campaign_root()


def export_buildlogs_env(phase):
    '''Return shell export snippet for BUILDLOGS.'''
    return 'export BUILDLOGS=%s' % phase_buildlogs(phase)


_apply_config(load_campaign_config(require=False))


if __name__ == '__main__':
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == 'prepare':
        force = '--force' in sys.argv[2:]
        sys.exit(prepare_campaign_from_repo(force=force))
    elif len(sys.argv) > 1 and sys.argv[1] == 'buildlogs':
        phase = int(sys.argv[2]) if len(sys.argv) > 2 else 0
        print(phase_buildlogs(phase))
    elif len(sys.argv) > 1 and sys.argv[1] == 'spreadsheet':
        print(spreadsheet_path())
    elif len(sys.argv) > 1 and sys.argv[1] == 'root':
        print(campaign_root())
    elif len(sys.argv) > 1 and sys.argv[1] == 'campaign_id':
        print(require_campaign_config()['campaign_id'])
    elif len(sys.argv) > 1 and sys.argv[1] == 'validate':
        _, _, errors = validate_repo_for_campaign()
        if errors:
            for err in errors:
                print(err, file=sys.stderr)
            sys.exit(1)
        fw = parse_arducopter_firmware_version()
        branch = get_git_branch()
        print('OK  firmware=%s  branch=%s  campaign=%s' % (
            fw, branch, build_campaign_id(fw, branch)))
        sys.exit(0)
    else:
        cfg = load_campaign_config(require=False)
        if not cfg:
            _campaign_not_initialized_message()
            sys.exit(1)
        print('Campaign: %s' % campaign_root())
        print('Spreadsheet: %s' % spreadsheet_path())
        for p in (0, 1, 2, 3):
            print('Phase %d logs: %s' % (p, phase_buildlogs(p)))
