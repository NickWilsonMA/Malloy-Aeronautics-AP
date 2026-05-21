#!/usr/bin/env python3
"""Generate firmware SITL validation campaign artifacts; detects reruns and only rebuilds changed tests."""

from __future__ import print_function

import argparse
import json
import os
import shutil
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(__file__))
import generate_oafastwp_report_common as rpt
import generate_oafastwp_visual_evidence as visual
import firmware_SITL_validation_campaign as campaign
import oafastwp_spreadsheet_data as sheet

PHASE_TESTS = {
    0: visual.PHASE0_TESTS,
    1: visual.PHASE1_TESTS,
    2: visual.PHASE2_TESTS,
    3: visual.PHASE3_TESTS,
}

REPORT_MODULES = {
    0: 'generate_oafastwp_phase0_report',
    1: 'generate_oafastwp_phase1_report',
    2: 'generate_oafastwp_phase2_report',
    3: 'generate_oafastwp_phase3_report',
}


def _read_manifest(path):
    if not path or not os.path.isfile(path):
        return None
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def _log_fingerprint(txt_path):
    if not txt_path or not os.path.isfile(txt_path):
        return None
    st = os.stat(txt_path)
    return {'mtime': st.st_mtime, 'size': st.st_size, 'basename': os.path.basename(txt_path)}


def _resolve_latest(base_dir):
    latest = os.path.join(base_dir, 'latest')
    if os.path.islink(latest):
        return os.path.realpath(latest)
    if os.path.isdir(latest):
        return latest
    return None


def _write_manifest(path, phase, stamp, results):
    data = {
        'generated_at': stamp,
        'phase': phase,
        'tests': {},
    }
    for r in results:
        fp = _log_fingerprint(r.get('txt_path'))
        data['tests'][r['name']] = {
            'sitl_id': r['sitl_ids'][0],
            'passed': r['passed'],
            'log': fp,
        }
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2)


def _test_updated(name, txt_path, prev_manifest):
    fp = _log_fingerprint(txt_path)
    if fp is None:
        return True
    if prev_manifest is None:
        return True
    prev = prev_manifest.get('tests', {}).get(name, {}).get('log')
    if not prev:
        return True
    return fp['mtime'] != prev.get('mtime') or fp['size'] != prev.get('size')


def _copy_if_exists(src, dst):
    if src and os.path.isfile(src):
        shutil.copy2(src, dst)
        return True
    return False


def _regenerate_test_assets(r, out_dir, cards_dir):
    card_path = os.path.join(cards_dir, '%s_card.png' % r['name'])
    if rpt.render_result_card_png(r, card_path):
        r['card_png'] = os.path.join('cards', os.path.basename(card_path))
    else:
        r['card_png'] = None

    track_path = os.path.join(out_dir, '%s_track.png' % r['name'])
    if r.get('tlog_path') and rpt.plot_track(r['tlog_path'], track_path, r['name']):
        r['track_png'] = os.path.basename(track_path)
    else:
        r['track_png'] = None

    if r.get('txt_path') and os.path.isfile(r['txt_path']):
        dst = os.path.join(out_dir, os.path.basename(r['txt_path']))
        if os.path.abspath(r['txt_path']) != os.path.abspath(dst):
            shutil.copy2(r['txt_path'], dst)


def _copy_test_assets_from_prev(r, prev_dir, out_dir, cards_dir):
    name = r['name']
    copied = False
    prev_card = os.path.join(prev_dir, 'cards', '%s_card.png' % name)
    dst_card = os.path.join(cards_dir, '%s_card.png' % name)
    if _copy_if_exists(prev_card, dst_card):
        r['card_png'] = os.path.join('cards', os.path.basename(dst_card))
        copied = True

    prev_track = os.path.join(prev_dir, '%s_track.png' % name)
    dst_track = os.path.join(out_dir, '%s_track.png' % name)
    if _copy_if_exists(prev_track, dst_track):
        r['track_png'] = os.path.basename(dst_track)
        copied = True

    if r.get('txt_path'):
        dst_txt = os.path.join(out_dir, os.path.basename(r['txt_path']))
        if _copy_if_exists(os.path.join(prev_dir, os.path.basename(r['txt_path'])), dst_txt):
            copied = True
        elif _copy_if_exists(r['txt_path'], dst_txt):
            copied = True
    return copied


def _symlink_latest(link_path, target_dir):
    if os.path.islink(link_path):
        os.unlink(link_path)
    elif os.path.isdir(link_path):
        shutil.rmtree(link_path)
    os.symlink(target_dir, link_path)


def generate_visual_evidence(phase, buildlogs, results, prev_manifest, prev_visual_dir, force_full=False):
    stamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    out_base = campaign.phase_visual_evidence(phase)
    out_dir = os.path.join(out_base, stamp)
    os.makedirs(out_dir, exist_ok=True)
    cards_dir = os.path.join(out_dir, 'cards')
    os.makedirs(cards_dir, exist_ok=True)

    updated = []
    unchanged = []
    for r in results:
        is_updated = force_full or _test_updated(r['name'], r.get('txt_path'), prev_manifest)
        if is_updated or not prev_visual_dir:
            _regenerate_test_assets(r, out_dir, cards_dir)
            updated.append(r['sitl_ids'][0])
        else:
            if not _copy_test_assets_from_prev(r, prev_visual_dir, out_dir, cards_dir):
                _regenerate_test_assets(r, out_dir, cards_dir)
                updated.append(r['sitl_ids'][0])
            else:
                unchanged.append(r['sitl_ids'][0])

    visual.write_visual_dashboard(out_dir, phase, results)
    index_path = os.path.join(out_dir, 'index.html')
    if os.path.isfile(os.path.join(out_dir, 'validation_dashboard.html')):
        shutil.copy2(os.path.join(out_dir, 'validation_dashboard.html'), index_path)

    manifest_path = os.path.join(out_dir, 'manifest.json')
    _write_manifest(manifest_path, phase, stamp, results)
    _symlink_latest(os.path.join(out_base, 'latest'), out_dir)

    return out_dir, updated, unchanged


def main():
    parser = argparse.ArgumentParser(description='Generate firmware SITL validation campaign artifacts')
    parser.add_argument('phase', type=int, choices=[0, 1, 2, 3])
    args = parser.parse_args()

    phase = args.phase
    buildlogs = campaign.phase_buildlogs(phase)
    xlsx = campaign.spreadsheet_path()
    campaign_root = campaign.campaign_root()

    if not os.path.isfile(xlsx):
        print('Campaign not initialized. Run: %s' % campaign.RESET_SCRIPT, file=sys.stderr)
        return 1
    if not os.path.isdir(buildlogs):
        print('No logs folder: %s' % buildlogs, file=sys.stderr)
        print('Run: %s %d' % (campaign.RUN_TESTS_SCRIPT, phase), file=sys.stderr)
        return 1

    tests = PHASE_TESTS[phase]
    results = visual.collect_results(buildlogs, tests)

    prev_visual_dir = _resolve_latest(campaign.phase_visual_evidence(phase))
    prev_manifest = _read_manifest(
        os.path.join(prev_visual_dir, 'manifest.json') if prev_visual_dir else None)

    any_log_change = prev_manifest is None
    if prev_manifest:
        for r in results:
            if _test_updated(r['name'], r.get('txt_path'), prev_manifest):
                any_log_change = True
                break

    passed_n = sum(1 for r in results if r['passed'])
    total = len(results)
    failed = [r for r in results if not r['passed']]
    missing = [r for r in results if not r.get('txt_path')]

    print('')
    print('=== Campaign artifacts — Phase %d ===' % phase)
    print('Campaign: %s' % campaign_root)
    print('Logs:     %s' % buildlogs)
    print('Results:  %d/%d PASS' % (passed_n, total))

    if not any_log_change:
        print('')
        print('No log changes since last artifacts run (%s).' % (
            prev_manifest.get('generated_at', 'unknown') if prev_manifest else 'none'))
        print('Skipping new visual/report folders. Updating spreadsheet only.')
        print('')
        import update_fence_escape_spreadsheet as upd
        upd.update_spreadsheet(phase, buildlogs, xlsx)
        print('')
        print('Latest (unchanged):')
        print('  Dashboard:  %s/index.html' % os.path.join(campaign.phase_visual_evidence(phase), 'latest'))
        print('  Report:     %s' % os.path.join(campaign.phase_report(phase), 'latest'))
        print('  Spreadsheet: %s' % xlsx)
        print('')
        _print_rerun_commands(phase, failed, missing)
        return 0 if not failed else 1

    mode = 'full' if prev_manifest is None else 'rerun'
    print('Mode:     %s' % mode)

    out_dir, updated, unchanged = generate_visual_evidence(
        phase, buildlogs, results, prev_manifest, prev_visual_dir)

    report_stamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    report_dir = os.path.join(campaign.phase_report(phase), report_stamp)
    os.makedirs(report_dir, exist_ok=True)

    if phase == 0:
        import generate_oafastwp_phase0_report as p0rpt
        p0_results = p0rpt.collect_phase0_results(buildlogs)
        stamp_human = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        p0rpt.write_rtf_report(
            os.path.join(report_dir, campaign.FIRMWARE_REGRESSION_RTF_NAME),
            p0_results, stamp_human)
        p0rpt.write_html_report(report_dir, p0_results, stamp_human)
        _write_manifest(os.path.join(report_dir, 'manifest.json'), phase, report_stamp, results)
        _symlink_latest(os.path.join(campaign.phase_report(phase), 'latest'), report_dir)
    else:
        mod = __import__(REPORT_MODULES[phase])
        sys.argv = [REPORT_MODULES[phase], '--buildlogs', buildlogs, '--output', report_dir]
        mod.main()
        _write_manifest(os.path.join(report_dir, 'manifest.json'), phase, report_stamp, results)
        _symlink_latest(os.path.join(campaign.phase_report(phase), 'latest'), report_dir)

    import update_fence_escape_spreadsheet as upd
    upd.update_spreadsheet(phase, buildlogs, xlsx)

    print('')
    if updated:
        print('Updated tests (%d): %s' % (len(updated), ', '.join(updated)))
    if unchanged:
        print('Unchanged (%d): copied from previous latest dashboard' % len(unchanged))
    print('')
    print('Saved:')
    print('  Dashboard:  %s/index.html' % out_dir)
    print('  Latest dash: %s/index.html' % os.path.join(campaign.phase_visual_evidence(phase), 'latest'))
    if phase == 0:
        print('  RTF report:  %s/%s' % (report_dir, campaign.FIRMWARE_REGRESSION_RTF_NAME))
    print('  Latest report: %s' % os.path.join(campaign.phase_report(phase), 'latest'))
    print('  Spreadsheet: %s' % xlsx)
    print('')

    _print_rerun_commands(phase, failed, missing)
    return 0 if not failed else 1


def _print_rerun_commands(phase, failed, missing):
    if not failed and not missing:
        print('All tests PASS. Phase %d sign-off complete.' % phase)
        if phase == 0:
            print('Next: %s 1  (when ready for fence regression)' % campaign.ADD_PHASE_SCRIPT)
        return

    print('Re-run failed or missing tests (logs go to campaign phase%d/logs):' % phase)
    seen = set()
    for r in failed + missing:
        tid = r['sitl_ids'][0]
        if tid in seen:
            continue
        seen.add(tid)
        print('  %s %d %s --skip-build' % (campaign.RUN_TESTS_SCRIPT, phase, r['name']))
    print('')
    print('Then refresh artifacts:')
    print('  %s %d' % (campaign.GENERATE_ARTIFACTS_SCRIPT, phase))


if __name__ == '__main__':
    sys.exit(main())
