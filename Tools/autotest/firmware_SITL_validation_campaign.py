#!/usr/bin/env python3
"""Paths and layout for a firmware SITL validation campaign under docs/."""

from __future__ import print_function

import json
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime

# Workbook cover / campaign intro (Phase 0 is generic firmware regression on every update).
CAMPAIGN_TITLE = 'Firmware Update — SITL Validation'
PHASE0_WORKSHEET_NAME = 'Phase 0'

RESET_SCRIPT = './Tools/autotest/reset_firmware_SITL_validation_campaign.sh'
RUN_TESTS_SCRIPT = './Tools/autotest/run_firmware_SITL_validation_campaign_tests.sh'
GENERATE_ARTIFACTS_SCRIPT = './Tools/autotest/generate_firmware_SITL_validation_campaign_artifacts.sh'
ADD_PHASE_SCRIPT = './Tools/autotest/add_firmware_SITL_validation_phase.sh'

PHASE_SUBDIRS = ('logs',)

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


def _test_name_to_sitl_id(phase):
    mapping = {}
    for name, sitl, _desc in _phase_tests(phase):
        mapping[name] = sitl
    return mapping


def _failure_snippet(content):
    if not content:
        return ''
    m = re.search(r'FAILED: "[^"]+": (.+?)(?:\s*\(see|\n)', content, re.DOTALL)
    if m:
        return m.group(1).strip().replace('\n', ' ')[:240]
    if 'Exception caught' in content:
        m = re.search(r'Exception caught: (.+)', content)
        if m:
            return m.group(1).strip()[:240]
    return ''


def analyze_run_folder(run_dir, phase):
    '''Build pass/fail stats for tests in one full_/rerun_ folder.'''
    import generate_oafastwp_report_common as rpt

    phase = int(phase)
    run_dir = os.path.abspath(run_dir)
    sitl_map = _test_name_to_sitl_id(phase)
    tests_out = []
    passed_names = []
    failed_names = []
    missing_names = []

    for name in sorted(os.listdir(run_dir)):
        if name in ('_shared', 'manifest.json', 'run_results.json'):
            continue
        test_dir = os.path.join(run_dir, name)
        if not os.path.isdir(test_dir):
            continue
        txt = rpt.latest_test_log(test_dir, name)
        entry = {
            'sitl_id': sitl_map.get(name, ''),
            'name': name,
            'status': 'MISSING',
            'log': '',
            'failure': '',
        }
        if txt:
            passed, content = rpt.parse_test_result(txt)
            entry['log'] = log_ref_relative_path(txt)
            if passed:
                entry['status'] = 'PASS'
                passed_names.append(name)
            else:
                entry['status'] = 'FAIL'
                entry['failure'] = _failure_snippet(content)
                failed_names.append(name)
        else:
            missing_names.append(name)
        tests_out.append(entry)

    total = len(tests_out)
    passed_n = len(passed_names)
    failed_n = len(failed_names)
    missing_n = len(missing_names)
    return {
        'tests': tests_out,
        'summary': {
            'total': total,
            'passed': passed_n,
            'failed': failed_n,
            'missing': missing_n,
            'all_pass': failed_n == 0 and missing_n == 0 and total > 0,
        },
        'passed': passed_names,
        'failed': failed_names,
        'missing': missing_names,
    }


def _prior_test_result(logs_root, test_name, exclude_dir=None):
    '''Most recent result for test_name from a different run folder (before this rerun).'''
    import generate_oafastwp_report_common as rpt

    exclude_dir = os.path.abspath(exclude_dir) if exclude_dir else None
    best_txt = None
    best_run = None
    best_mtime = 0.0
    for run_dir in list_run_dirs(logs_root):
        if exclude_dir and os.path.abspath(run_dir) == exclude_dir:
            continue
        test_dir = os.path.join(run_dir, test_name)
        if not os.path.isdir(test_dir):
            continue
        txt = rpt.latest_test_log(test_dir, test_name)
        if txt:
            mtime = os.path.getmtime(txt)
            if mtime >= best_mtime:
                best_mtime = mtime
                best_txt = txt
                best_run = run_dir
    if not best_txt:
        return None
    passed, content = rpt.parse_test_result(best_txt)
    return {
        'folder': os.path.basename(best_run),
        'run_kind': 'full' if os.path.basename(best_run).startswith('full_') else 'rerun',
        'status': 'PASS' if passed else 'FAIL',
        'failure': _failure_snippet(content) if not passed else '',
        'log': log_ref_relative_path(best_txt),
    }


def write_run_results(run_dir, phase, run_kind=None, stamp=None, primary_test=None):
    '''Write run_results.json next to manifest.json in a run folder.'''
    run_dir = os.path.abspath(run_dir)
    logs_root = phase_buildlogs(int(phase))
    analysis = analyze_run_folder(run_dir, phase)
    meta_path = os.path.join(run_dir, 'manifest.json')
    if os.path.isfile(meta_path):
        with open(meta_path, 'r', encoding='utf-8') as f:
            meta = json.load(f)
        run_kind = run_kind or meta.get('run_kind')
        stamp = stamp or meta.get('stamp')
        primary_test = primary_test or meta.get('primary_test')

    payload = {
        'run_kind': run_kind or 'unknown',
        'phase': int(phase),
        'folder': os.path.basename(run_dir),
        'stamp': stamp,
        'primary_test': primary_test,
        'generated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'summary': analysis['summary'],
        'passed': analysis['passed'],
        'failed': analysis['failed'],
        'missing': analysis['missing'],
        'tests': analysis['tests'],
    }
    if run_kind == 'rerun' and not primary_test and len(analysis['tests']) == 1:
        primary_test = analysis['tests'][0]['name']
        payload['primary_test'] = primary_test
    if run_kind == 'rerun' and primary_test:
        payload['rerun_test'] = primary_test
        prior = _prior_test_result(logs_root, primary_test, exclude_dir=run_dir)
        if prior:
            payload['previous_attempt'] = prior
        current = next((t for t in analysis['tests'] if t['name'] == primary_test), None)
        if current and prior:
            payload['outcome'] = {
                'was': prior.get('status'),
                'now': current.get('status'),
                'improved': prior.get('status') == 'FAIL' and current.get('status') == 'PASS',
            }

    out_path = os.path.join(run_dir, 'run_results.json')
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(payload, f, indent=2)
        f.write('\n')
    return out_path, payload


def list_rerun_dirs(logs_root):
    return [
        d for d in list_run_dirs(logs_root)
        if os.path.basename(d).startswith('rerun_')
    ]


def _load_run_results(run_dir, phase):
    rr_path = os.path.join(run_dir, 'run_results.json')
    if os.path.isfile(rr_path):
        with open(rr_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    _, payload = write_run_results(run_dir, phase)
    return payload


def _full_run_folder(logs_root):
    latest_full = os.path.join(logs_root, 'latest_full')
    if os.path.islink(latest_full):
        return os.path.realpath(latest_full)
    if os.path.isdir(latest_full):
        return latest_full
    for run_dir in list_run_dirs(logs_root):
        if os.path.basename(run_dir).startswith('full_'):
            return run_dir
    return None


def write_reruns_aggregate(phase):
    '''
    Write Phase<N>/logs/run_results.json summarizing every rerun_* folder.
    One tests[] row per re-run test (latest status + attempt history).
    '''
    phase = int(phase)
    logs_root = phase_buildlogs(phase)
    rerun_dirs = list_rerun_dirs(logs_root)
    if not rerun_dirs:
        return None, None

    sitl_map = _test_name_to_sitl_id(phase)
    full_run = _full_run_folder(logs_root)
    full_run_name = os.path.basename(full_run) if full_run else None
    full_results = {}
    if full_run and os.path.isfile(os.path.join(full_run, 'run_results.json')):
        with open(os.path.join(full_run, 'run_results.json'), 'r', encoding='utf-8') as f:
            full_data = json.load(f)
        for t in full_data.get('tests', []):
            full_results[t['name']] = t

    rerun_summaries = []
    by_test = {}

    for rerun_dir in rerun_dirs:
        rr = _load_run_results(rerun_dir, phase)
        folder = os.path.basename(rerun_dir)
        rerun_summaries.append({
            'folder': folder,
            'stamp': rr.get('stamp'),
            'primary_test': rr.get('primary_test'),
            'summary': rr.get('summary'),
            'previous_attempt': rr.get('previous_attempt'),
            'outcome': rr.get('outcome'),
        })

        test_name = rr.get('primary_test')
        if not test_name and rr.get('tests'):
            test_name = rr['tests'][0]['name']
        if not test_name:
            continue

        if test_name not in by_test:
            by_test[test_name] = {
                'sitl_id': sitl_map.get(test_name, ''),
                'name': test_name,
                'attempts': [],
            }

        for t in rr.get('tests', []):
            if t.get('name') != test_name:
                continue
            by_test[test_name]['attempts'].append({
                'folder': folder,
                'stamp': rr.get('stamp'),
                'status': t.get('status'),
                'log': t.get('log'),
                'failure': t.get('failure', ''),
            })

    tests_out = []
    passed_names = []
    failed_names = []
    for name in sorted(by_test.keys()):
        info = by_test[name]
        latest = info['attempts'][-1]
        full_t = full_results.get(name, {})
        entry = {
            'sitl_id': info['sitl_id'],
            'name': name,
            'status': latest['status'],
            'rerun_count': len(info['attempts']),
            'full_run_status': full_t.get('status', ''),
            'log': latest.get('log', ''),
            'failure': latest.get('failure', ''),
            'latest_folder': latest['folder'],
            'attempts': info['attempts'],
        }
        if full_t.get('log'):
            entry['full_run_log'] = full_t['log']
        tests_out.append(entry)
        if latest['status'] == 'PASS':
            passed_names.append(name)
        else:
            failed_names.append(name)

    total = len(tests_out)
    passed_n = len(passed_names)
    failed_n = len(failed_names)
    payload = {
        'run_kind': 'reruns',
        'phase': phase,
        'folder': 'logs',
        'full_run': full_run_name,
        'generated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'summary': {
            'rerun_folders': len(rerun_dirs),
            'tests_rerun': total,
            'passed': passed_n,
            'failed': failed_n,
            'missing': 0,
            'all_pass': failed_n == 0 and total > 0,
        },
        'passed': passed_names,
        'failed': failed_names,
        'missing': [],
        'tests': tests_out,
        'rerun_folders': rerun_summaries,
    }

    out_path = os.path.join(logs_root, 'run_results.json')
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(payload, f, indent=2)
        f.write('\n')
    return out_path, payload


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
        log_name = r['txt_path'] if r.get('txt_path') else '(no log yet)'
        if r.get('txt_path'):
            log_name = log_ref_relative_path(r['txt_path'])
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
        print('Then refresh spreadsheet:')
        print('  %s %d' % (GENERATE_ARTIFACTS_SCRIPT, phase))
        latest_full = os.path.join(buildlogs, 'latest_full')
        if os.path.islink(latest_full):
            full_dir = os.path.realpath(latest_full)
            results_json = os.path.join(full_dir, 'run_results.json')
            if os.path.isfile(results_json):
                print('')
                print('Full run stats: %s' % log_ref_relative_path(results_json))
        reruns_json = os.path.join(buildlogs, 'run_results.json')
        if os.path.isfile(reruns_json):
            with open(reruns_json, 'r', encoding='utf-8') as f:
                reruns_data = json.load(f)
            if reruns_data.get('run_kind') == 'reruns':
                rs = reruns_data.get('summary', {})
                print('Reruns aggregate: %s  (%d tests re-run, %d pass, %d fail)' % (
                    log_ref_relative_path(reruns_json),
                    rs.get('tests_rerun', 0),
                    rs.get('passed', 0),
                    rs.get('failed', 0)))
    else:
        print('')
        print('All tests PASS. Update spreadsheet:')
        print('  %s %d' % (GENERATE_ARTIFACTS_SCRIPT, phase))
        if phase == 0:
            print('')
            print('Phase 0 sign-off complete. Add Phase 1 tab when ready:')
            print('  %s 1' % ADD_PHASE_SCRIPT)

    return 0 if not failed and not missing else 1


def _run_stamp():
    return datetime.now().strftime('%Y%m%d_%H%M%S')


def _is_run_dir(name):
    return name.startswith('full_') or name.startswith('rerun_')


def _extract_test_name_from_artifact(filename):
    base = os.path.basename(filename)
    if not base.startswith('ArduCopter-'):
        return None
    rest = base[len('ArduCopter-'):]
    for marker in ('.txt', '-autotest', '-retry-', '-dataflash-log-'):
        if marker in rest:
            rest = rest.split(marker)[0]
            break
    rest = re.sub(r'-\d+\.BIN$', '', rest)
    return rest or None


def list_run_dirs(logs_root):
    if not os.path.isdir(logs_root):
        return []
    runs = []
    for name in os.listdir(logs_root):
        if _is_run_dir(name):
            path = os.path.join(logs_root, name)
            if os.path.isdir(path):
                runs.append(path)
    return sorted(runs, key=os.path.getmtime)


def test_run_attempts(logs_root, test_name):
    '''Chronological (full_ / rerun_) attempts for one test.'''
    import generate_oafastwp_report_common as rpt

    attempts = []
    for run_dir in list_run_dirs(logs_root):
        test_dir = os.path.join(run_dir, test_name)
        if not os.path.isdir(test_dir):
            continue
        txt = rpt.latest_test_log(test_dir, test_name)
        if not txt:
            continue
        passed, _ = rpt.parse_test_result(txt)
        run_name = os.path.basename(run_dir)
        kind = 'rerun' if run_name.startswith('rerun_') else 'full'
        attempts.append({
            'kind': kind,
            'passed': passed,
            'log': txt,
            'folder': run_name,
        })
    return attempts


def reruns_to_pass(logs_root, test_name):
    '''
    Re-run folders required before first PASS (0 = passed on first full run).
    Returns None if no logs; returns (count, passed) where count is None when still failing.
    '''
    attempts = test_run_attempts(logs_root, test_name)
    if not attempts:
        return None, False

    rerun_attempts = 0
    for attempt in attempts:
        if attempt['kind'] == 'rerun':
            rerun_attempts += 1
        if attempt['passed']:
            if attempt['kind'] == 'rerun':
                return rerun_attempts, True
            return 0, True
    return None, False


def resolve_test_log_dir(logs_root, test_name):
    '''Newest per-test folder for test_name across full_ and rerun_ runs.'''
    best_dir = None
    best_mtime = 0.0
    for run_dir in list_run_dirs(logs_root):
        test_dir = os.path.join(run_dir, test_name)
        if not os.path.isdir(test_dir):
            continue
        import generate_oafastwp_report_common as rpt
        txt = rpt.latest_test_log(test_dir, test_name)
        if txt:
            mtime = os.path.getmtime(txt)
            if mtime >= best_mtime:
                best_mtime = mtime
                best_dir = test_dir
    return best_dir


def begin_run(phase, run_kind, primary_test=None):
    '''Create flat staging dir for autotest; returns absolute path for BUILDLOGS.'''
    phase = int(phase)
    if run_kind not in ('full', 'rerun'):
        raise ValueError('run_kind must be full or rerun')
    logs_root = phase_buildlogs(phase)
    os.makedirs(logs_root, exist_ok=True)
    stamp = _run_stamp()
    staging = os.path.join(logs_root, '.staging_%s' % stamp)
    os.makedirs(staging, exist_ok=True)
    meta = os.path.join(staging, '.run_meta.json')
    with open(meta, 'w', encoding='utf-8') as f:
        json.dump({
            'phase': phase,
            'run_kind': run_kind,
            'stamp': stamp,
            'primary_test': primary_test or '',
        }, f)
    return staging


def _organize_staging_into_run(staging_dir, dest_run_dir):
    groups = {}
    for name in os.listdir(staging_dir):
        if name == '.run_meta.json':
            continue
        src = os.path.join(staging_dir, name)
        if not os.path.isfile(src):
            continue
        test_name = _extract_test_name_from_artifact(name)
        if not test_name:
            continue
        groups.setdefault(test_name, []).append(src)

    os.makedirs(dest_run_dir, exist_ok=True)
    for test_name, files in sorted(groups.items()):
        test_dir = os.path.join(dest_run_dir, test_name)
        os.makedirs(test_dir, exist_ok=True)
        for src in files:
            dst = os.path.join(test_dir, os.path.basename(src))
            shutil.move(src, dst)
    return sorted(groups.keys())


def _symlink_latest(link_path, target_dir):
    if os.path.islink(link_path):
        os.unlink(link_path)
    elif os.path.isdir(link_path):
        shutil.rmtree(link_path)
    os.symlink(os.path.basename(target_dir), link_path)


def finalize_run(phase, staging_dir, run_kind, primary_test=None):
    '''Move staging artifacts into full_<ts>/ or rerun_<ts>-<Test>/ with per-test subfolders.'''
    phase = int(phase)
    staging_dir = os.path.abspath(staging_dir)
    logs_root = phase_buildlogs(phase)
    meta_path = os.path.join(staging_dir, '.run_meta.json')
    stamp = _run_stamp()
    if os.path.isfile(meta_path):
        with open(meta_path, 'r', encoding='utf-8') as f:
            meta = json.load(f)
            stamp = meta.get('stamp', stamp)
            if not primary_test:
                primary_test = meta.get('primary_test') or None
            if primary_test == '':
                primary_test = None

    if run_kind == 'rerun' and primary_test:
        dest_name = 'rerun_%s-%s' % (stamp, primary_test)
    else:
        dest_name = '%s_%s' % (run_kind, stamp)
    dest_run_dir = os.path.join(logs_root, dest_name)
    if os.path.exists(dest_run_dir):
        shutil.rmtree(dest_run_dir)

    tests = _organize_staging_into_run(staging_dir, dest_run_dir)
    manifest = {
        'run_kind': run_kind,
        'phase': phase,
        'stamp': stamp,
        'folder': dest_name,
        'primary_test': primary_test,
        'tests': tests,
        'finalized_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
    }
    with open(os.path.join(dest_run_dir, 'manifest.json'), 'w', encoding='utf-8') as f:
        json.dump(manifest, f, indent=2)
        f.write('\n')

    results_path, results = write_run_results(
        dest_run_dir, phase, run_kind=run_kind, stamp=stamp, primary_test=primary_test)
    manifest['summary'] = results['summary']
    with open(os.path.join(dest_run_dir, 'manifest.json'), 'w', encoding='utf-8') as f:
        json.dump(manifest, f, indent=2)
        f.write('\n')

    if run_kind == 'full':
        _symlink_latest(os.path.join(logs_root, 'latest_full'), dest_run_dir)
    elif run_kind == 'rerun':
        agg_path, agg = write_reruns_aggregate(phase)
        if agg_path:
            print('Reruns aggregate: %s  (%d tests, %d pass, %d fail)' % (
                log_ref_relative_path(agg_path),
                agg['summary']['tests_rerun'],
                agg['summary']['passed'],
                agg['summary']['failed']))

    try:
        os.rmdir(staging_dir)
    except OSError:
        shutil.rmtree(staging_dir, ignore_errors=True)

    summary = results['summary']
    print('Organized %d test(s) -> %s' % (len(tests), dest_run_dir))
    print('Run results: %s' % log_ref_relative_path(results_path))
    print('  %d pass, %d fail, %d missing' % (
        summary['passed'], summary['failed'], summary['missing']))
    if run_kind == 'rerun' and results.get('previous_attempt'):
        prev = results['previous_attempt']
        print('  Previous: %s in %s' % (prev.get('status'), prev.get('folder')))
        if results.get('outcome'):
            print('  Outcome:  %s -> %s' % (
                results['outcome'].get('was'), results['outcome'].get('now')))
    if summary['failed']:
        print('Failed in this run:')
        for name in results['failed']:
            for t in results['tests']:
                if t['name'] == name:
                    print('  %s  %s' % (t.get('sitl_id', name), t.get('failure') or '(see log)'))
                    break
    for test_name in tests:
        print('  %s/' % test_name)
    return dest_run_dir


def campaign_root():
    require_campaign_config()
    return os.path.join(_repo_root(), 'docs', CAMPAIGN_ID)


def spreadsheet_path():
    require_campaign_config()
    return os.path.join(campaign_root(), '%s.xlsx' % CAMPAIGN_ID)


def phase_dir_name(phase):
    return 'Phase%d' % int(phase)


def phase_dir(phase):
    return os.path.join(campaign_root(), phase_dir_name(phase))


def phase_buildlogs(phase):
    return os.path.join(phase_dir(phase), 'logs')


def migrate_campaign_layout(root=None):
    '''Rename legacy phaseN/ → PhaseN under the campaign folder.'''
    root = os.path.abspath(root or campaign_root())
    if not os.path.isdir(root):
        return
    for p in range(4):
        old = os.path.join(root, 'phase%d' % p)
        new = os.path.join(root, 'Phase%d' % p)
        if os.path.isdir(old) and not os.path.exists(new):
            os.rename(old, new)


def log_ref_relative(phase, filename):
    return '%s/logs/%s' % (phase_dir_name(phase), filename)


def log_ref_relative_path(abs_path):
    require_campaign_config()
    rel = os.path.relpath(os.path.abspath(abs_path), campaign_root())
    return rel.replace('\\', '/')


def ensure_phase_dirs(phase):
    phase = int(phase)
    os.makedirs(phase_buildlogs(phase), exist_ok=True)
    return phase_dir(phase)


def ensure_campaign_dirs(phases=(0,)):
    root = campaign_root()
    os.makedirs(root, exist_ok=True)
    os.makedirs(campaign_evidence_dir(), exist_ok=True)
    os.makedirs(campaign_report_dir(), exist_ok=True)
    for phase in phases:
        ensure_phase_dirs(phase)
    migrate_campaign_layout(root)
    return root


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
    elif len(sys.argv) > 1 and sys.argv[1] == 'begin-run':
        phase = int(sys.argv[2]) if len(sys.argv) > 2 else 0
        run_kind = sys.argv[3] if len(sys.argv) > 3 else 'full'
        primary_test = sys.argv[4] if len(sys.argv) > 4 else None
        if primary_test == '':
            primary_test = None
        print(begin_run(phase, run_kind, primary_test=primary_test))
        sys.exit(0)
    elif len(sys.argv) > 1 and sys.argv[1] == 'finalize-run':
        phase = int(sys.argv[2]) if len(sys.argv) > 2 else 0
        staging = sys.argv[3] if len(sys.argv) > 3 else ''
        run_kind = sys.argv[4] if len(sys.argv) > 4 else 'full'
        primary_test = sys.argv[5] if len(sys.argv) > 5 else None
        if primary_test == '':
            primary_test = None
        if not staging:
            print('Usage: finalize-run <phase> <staging_dir> <full|rerun> [TestName]', file=sys.stderr)
            sys.exit(1)
        finalize_run(phase, staging, run_kind, primary_test=primary_test)
        sys.exit(0)
    elif len(sys.argv) > 1 and sys.argv[1] == 'write-run-results':
        phase = int(sys.argv[2]) if len(sys.argv) > 2 else 0
        run_folder = sys.argv[3] if len(sys.argv) > 3 else ''
        if not run_folder:
            print('Usage: write-run-results <phase> <run_folder_name_or_path|all|reruns>', file=sys.stderr)
            sys.exit(1)
        logs_root = phase_buildlogs(phase)
        if run_folder == 'reruns':
            path, payload = write_reruns_aggregate(phase)
            if not path:
                print('No rerun folders under %s' % logs_root, file=sys.stderr)
                sys.exit(1)
            print('Wrote %s' % path)
            print('Summary: %d tests re-run, %d pass, %d fail' % (
                payload['summary']['tests_rerun'],
                payload['summary']['passed'],
                payload['summary']['failed']))
            sys.exit(0)
        if run_folder == 'all':
            run_dirs = list_run_dirs(logs_root)
            if not run_dirs:
                print('No run folders under %s' % logs_root, file=sys.stderr)
                sys.exit(1)
            for run_dir in run_dirs:
                path, payload = write_run_results(run_dir, phase)
                print('%s  %d/%d pass' % (path, payload['summary']['passed'], payload['summary']['total']))
            agg_path, agg = write_reruns_aggregate(phase)
            if agg_path:
                print('%s  %d tests re-run, %d pass, %d fail' % (
                    agg_path, agg['summary']['tests_rerun'],
                    agg['summary']['passed'], agg['summary']['failed']))
            sys.exit(0)
        if os.path.isdir(run_folder):
            run_dir = run_folder
        else:
            run_dir = os.path.join(logs_root, run_folder)
        if not os.path.isdir(run_dir):
            print('Run folder not found: %s' % run_dir, file=sys.stderr)
            sys.exit(1)
        path, payload = write_run_results(run_dir, phase)
        print('Wrote %s' % path)
        print('Summary: %d/%d pass, failed: %s' % (
            payload['summary']['passed'], payload['summary']['total'], ', '.join(payload['failed']) or 'none'))
        if payload.get('previous_attempt'):
            print('Previous attempt: %s in %s' % (
                payload['previous_attempt'].get('status'),
                payload['previous_attempt'].get('folder')))
        sys.exit(0)
    elif len(sys.argv) > 1 and sys.argv[1] == 'migrate-layout':
        migrate_campaign_layout()
        print('Migrated campaign layout under %s' % campaign_root())
        sys.exit(0)
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
