#!/usr/bin/env python3
"""Paths and layout for a firmware SITL validation campaign under docs/."""

from __future__ import print_function

import json
import os
import re
import subprocess
import sys
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
_DEFAULT_BRANCHES = frozenset(['main', 'master', 'develop', 'devel', 'trunk', 'MA-4.3.0.X'])
_THISFIRMWARE_RE = re.compile(
    r'^MA_COPTER-V(\d+\.\d+\.\d+\.\d+)-(.+)$',
)

# Populated from config written by reset_firmware_SITL_validation_campaign.sh
CAMPAIGN_ID = None
FIRMWARE_VERSION = None
THISFIRMWARE = None
CAMPAIGN_FEATURE = None
GIT_BRANCH = None


def _repo_root():
    return os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))


def _config_path():
    return os.path.join(os.path.dirname(__file__), _CONFIG_FILENAME)


def _version_h_path():
    return os.path.join(_repo_root(), 'ArduCopter', 'version.h')


def _quote_strip(value):
    return value.strip().strip('"').strip('\u201c').strip('\u201d').strip()


def parse_thisfirmware(version_h_path=None):
    '''
    Parse ArduCopter/version.h THISFIRMWARE, e.g.
    MA_COPTER-V4.3.0.16-OA-fastWP-fenceEscapeVector
    '''
    version_h_path = version_h_path or _version_h_path()
    with open(version_h_path, 'r', encoding='utf-8') as f:
        content = f.read()

    line_m = re.search(r'#define\s+THISFIRMWARE\s+(.+)$', content, re.MULTILINE)
    if not line_m:
        return None

    full_name = _quote_strip(line_m.group(1))
    m = _THISFIRMWARE_RE.match(full_name)
    if not m:
        return None

    return {
        'thisfirmware': full_name,
        'campaign_id': full_name,
        'firmware_version': m.group(1),
        'branch_suffix': m.group(2),
    }


def parse_arducopter_firmware_version(version_h_path=None):
    '''Return dotted build number (e.g. 4.3.0.16) from THISFIRMWARE.'''
    info = parse_thisfirmware(version_h_path)
    return info['firmware_version'] if info else None


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


def validate_repo_for_campaign(strict_branch=True):
    errors = []
    version_h = _version_h_path()
    info = None

    if not os.path.isfile(version_h):
        errors.append('ArduCopter/version.h not found at %s.' % version_h)
    else:
        info = parse_thisfirmware(version_h)
        if not info:
            errors.append(
                'THISFIRMWARE must match MA_COPTER-V<major>.<minor>.<patch>.<build>-<branch-name> '
                '(example: MA_COPTER-V4.3.0.16-OA-fastWP-fenceEscapeVector).',
            )

    branch = get_git_branch()
    if branch is None:
        errors.append(
            'Not on a named git branch (detached HEAD?). '
            'Check out the feature branch under test: git checkout <branch>',
        )
    elif strict_branch and branch in _DEFAULT_BRANCHES:
        errors.append(
            'Currently on integration/default branch "%s". '
            'Create a feature branch from MA-4.3.0.X and check it out.' % branch,
        )
    elif info and branch and branch != info['branch_suffix']:
        errors.append(
            'Git branch "%s" does not match THISFIRMWARE suffix "%s". '
            'Either rename the branch or update ArduCopter/version.h so both match.'
            % (branch, info['branch_suffix']),
        )

    return info, branch, errors


def write_campaign_config(info, branch):
    data = {
        'campaign_id': info['campaign_id'],
        'thisfirmware': info['thisfirmware'],
        'firmware_version': info['firmware_version'],
        'branch_suffix': info['branch_suffix'],
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
    global CAMPAIGN_ID, FIRMWARE_VERSION, THISFIRMWARE, CAMPAIGN_FEATURE, GIT_BRANCH
    if not cfg:
        CAMPAIGN_ID = None
        FIRMWARE_VERSION = None
        THISFIRMWARE = None
        CAMPAIGN_FEATURE = None
        GIT_BRANCH = None
        return
    CAMPAIGN_ID = cfg['campaign_id']
    FIRMWARE_VERSION = cfg['firmware_version']
    THISFIRMWARE = cfg.get('thisfirmware', cfg['campaign_id'])
    GIT_BRANCH = cfg.get('git_branch', '')
    CAMPAIGN_FEATURE = cfg.get('branch_suffix', GIT_BRANCH)


def _campaign_not_initialized_message():
    print('Firmware SITL validation campaign is not initialized.', file=sys.stderr)
    print('', file=sys.stderr)
    print('From repo root, run:', file=sys.stderr)
    print('  %s' % RESET_SCRIPT, file=sys.stderr)
    print('', file=sys.stderr)
    print('That script reads THISFIRMWARE from ArduCopter/version.h and creates', file=sys.stderr)
    print('docs/<THISFIRMWARE>/ with the Phase 0 spreadsheet template.', file=sys.stderr)


def require_campaign_config():
    cfg = load_campaign_config(require=True)
    if cfg is None:
        raise SystemExit(1)
    return cfg


def prepare_campaign_from_repo(force=False):
    info, branch, errors = validate_repo_for_campaign(strict_branch=not force)
    if errors:
        print('Cannot prepare firmware SITL validation campaign:', file=sys.stderr)
        for err in errors:
            print('  - %s' % err, file=sys.stderr)
        print('', file=sys.stderr)
        print('Before running %s:' % RESET_SCRIPT, file=sys.stderr)
        print('  1. Create/check out feature branch from MA-4.3.0.X (branch name = feature name).', file=sys.stderr)
        print('  2. Set ArduCopter/version.h THISFIRMWARE to:', file=sys.stderr)
        print('       MA_COPTER-V<next-build>-<branch-name>', file=sys.stderr)
        print('     Increment the build number (.16, .17, ...) and match the branch suffix.', file=sys.stderr)
        return 1

    cfg = write_campaign_config(info, branch)
    print('THISFIRMWARE:     %s' % cfg['thisfirmware'])
    print('Campaign folder:  docs/%s/' % cfg['campaign_id'])
    print('Git branch:       %s' % cfg['git_branch'])
    print('Build version:    %s' % cfg['firmware_version'])
    return 0


def _phase_tests(phase):
    import generate_oafastwp_visual_evidence as visual
    return {
        0: visual.PHASE0_TESTS,
        1: visual.PHASE1_TESTS,
        2: visual.PHASE2_TESTS,
        3: visual.PHASE3_TESTS,
    }[int(phase)]


def summarize_phase_logs(phase):
    '''Print pass/fail summary and per-test re-run commands after an autotest run.'''
    phase = int(phase)
    buildlogs = phase_buildlogs(phase)
    tests = _phase_tests(phase)

    import generate_oafastwp_visual_evidence as visual
    results = visual.collect_results(buildlogs, tests)

    passed = [r for r in results if r['passed']]
    failed = [r for r in results if not r['passed']]
    missing = [r for r in results if not r.get('txt_path')]

    print('')
    print('=== Phase %d autotest summary ===' % phase)
    print('Logs: %s' % buildlogs)
    print('Result: %d/%d PASS' % (len(passed), len(results)))

    for r in results:
        if not r.get('txt_path'):
            status = 'MISSING'
        elif r['passed']:
            status = 'PASS'
        else:
            status = 'FAIL'
        log_name = os.path.basename(r['txt_path']) if r.get('txt_path') else '(no log yet)'
        print('  [%s] %s  %s  %s' % (status, r['sitl_ids'][0], r['name'], log_name))

    if failed or missing:
        print('')
        print('Re-run individually (--skip-build after first build):')
        seen = set()
        for r in failed + missing:
            tid = r['sitl_ids'][0]
            if tid in seen:
                continue
            seen.add(tid)
            print('  %s %d %s --skip-build' % (RUN_TESTS_SCRIPT, phase, r['name']))
        print('')
        print('Then refresh reports/spreadsheet:')
        print('  %s %d' % (GENERATE_ARTIFACTS_SCRIPT, phase))
    else:
        print('')
        print('All tests PASS. Generate evidence + spreadsheet:')
        print('  %s %d' % (GENERATE_ARTIFACTS_SCRIPT, phase))
        if phase == 0:
            print('')
            print('Phase 0 sign-off complete. Add Phase 1 tab when ready:')
            print('  %s 1' % ADD_PHASE_SCRIPT)

    return 0 if not failed and not missing else 1


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
    if len(sys.argv) > 1 and sys.argv[1] == 'prepare':
        force = '--force' in sys.argv[2:]
        sys.exit(prepare_campaign_from_repo(force=force))
    elif len(sys.argv) > 1 and sys.argv[1] == 'summarize':
        phase = int(sys.argv[2]) if len(sys.argv) > 2 else 0
        sys.exit(summarize_phase_logs(phase))
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
        info, branch, errors = validate_repo_for_campaign()
        if errors:
            for err in errors:
                print(err, file=sys.stderr)
            sys.exit(1)
        print('OK  THISFIRMWARE=%s  branch=%s' % (info['thisfirmware'], branch))
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
