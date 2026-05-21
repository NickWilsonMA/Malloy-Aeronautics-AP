#!/usr/bin/env python3
"""
Visual validation evidence from autotest .txt logs.

Produces a presentation-ready HTML dashboard plus per-test PNG result cards
showing PASS/FAIL and a timeline parsed from the autotest log (proof the test ran).

Usage:
  ./Tools/autotest/generate_oafastwp_visual_evidence.py --phase 1
  ./Tools/autotest/generate_oafastwp_visual_evidence.py --phase all
"""

from __future__ import print_function

import argparse
import html
import os
import shutil
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(__file__))
import generate_oafastwp_report_common as rpt
import firmware_SITL_validation_campaign as campaign

# (autotest_name, sitl_id, description)
PHASE0_TESTS = [
    ('P0_01_Parameters', 'P0-01', 'Parameter load/set (upstream Parameters)'),
    ('P0_02_ArmFeatures', 'P0-02', 'Arm/disarm and pre-arm (upstream ArmFeatures)'),
    ('P0_03_Logging', 'P0-03', 'Onboard logging (upstream Logging)'),
    ('P0_04_ModeAltHold', 'P0-04', 'ALT_HOLD mode'),
    ('P0_05_ModeLoiter', 'P0-05', 'LOITER mode'),
    ('P0_06_TakeoffCheck', 'P0-06', 'Takeoff checks'),
    ('P0_07_Landing', 'P0-07', 'Landing sequence'),
    ('P0_08_CopterMission', 'P0-08', 'AUTO mission'),
    ('P0_09_GuidedSubModeChange', 'P0-09', 'GUIDED sub-mode changes'),
    ('P0_10_LoiterToAlt', 'P0-10', 'LOITER altitude change'),
    ('P0_11_HorizontalFence', 'P0-11', 'Horizontal geofence'),
    ('P0_12_ThrottleFailsafe', 'P0-12', 'Throttle failsafe'),
    ('P0_13_GCSFailsafe', 'P0-13', 'GCS failsafe'),
    ('P0_14_SMART_RTL', 'P0-14', 'SMART_RTL'),
    ('P0_15_RTL_TO_RALLY', 'P0-15', 'RTL to rally point'),
    ('P0_16_WPNAV_SPEED', 'P0-16', 'WP nav speed parameters'),
    ('P0_17_DataFlash', 'P0-17', 'Dataflash log integrity'),
    ('P0_18_ParameterChecks', 'P0-18', 'Parameter validation'),
    ('P0_19_Dijkstra_OutsideInclusion', 'P0-19', 'Dijkstra RTL outside inclusion'),
    ('P0_20_Dijkstra_InsideExclusion', 'P0-20', 'Dijkstra RTL inside exclusion'),
    ('P0_21_Dijkstra_PathPlanningReturn', 'P0-21', 'Dijkstra path planning return'),
    ('P0_22_RTL_BrakingDistance', 'P0-22', 'RTL braking distance'),
]

PHASE1_TESTS = [
    ('SITL_01_PolygonExclusionMission', 'SITL-01', 'Polygon exclusion AUTO mission'),
    ('SITL_02_CircleExclusionMission', 'SITL-02', 'Circular exclusion AUTO mission'),
    ('SITL_03_MultipleExclusionMission', 'SITL-03', 'Multiple exclusion fences corridor'),
    ('SITL_04_InclusionFenceMission', 'SITL-04', 'Inclusion fence operation'),
    ('SITL_05_OverlappingExclusionMission', 'SITL-05', 'Overlapping exclusion fences'),
    ('SITL_06_NarrowCorridorMission', 'SITL-06', 'Narrow corridor between fences'),
    ('SITL_07_NoValidPathMission', 'SITL-07', 'No valid path - safe hold'),
    ('SITL_08_AddFenceDuringMission', 'SITL-08', 'Add fence during AUTO'),
    ('SITL_09_ChangeFenceDuringMission', 'SITL-09', 'Change fence during AUTO'),
    ('SITL_10_DeleteFenceDuringMission', 'SITL-10', 'Delete fence during AUTO'),
    ('SITL_11_EnableFenceInAir', 'SITL-11', 'Enable fence in air'),
    ('SITL_12_DisableFenceInAir', 'SITL-12', 'Disable fence in air'),
    ('SITL_13_FenceBreachRecovery', 'SITL-13', 'Fence breach recovery'),
    ('SITL_14_RTLBlockedPath', 'SITL-14', 'RTL through blocked path'),
    ('SITL_15_RTLToRallyBlockedPath', 'SITL-15', 'RTL to rally through fence'),
    ('SITL_16_FastWaypointsDisabled', 'SITL-16', 'Fast waypoints disabled baseline'),
    ('SITL_17_FastWaypointsEnabled', 'SITL-17', 'Fast waypoints enabled'),
    ('SITL_18_DenseWaypointsNearFence', 'SITL-18', 'Dense WPs near fence'),
    ('SITL_19_WaypointsCloseToMargin', 'SITL-19', 'WPs close to fence margin'),
    ('SITL_20_AltitudeGeofenceCeiling', 'SITL-20', 'Altitude geofence ceiling'),
    ('SITL_21_AltitudeAndHorizontalFence', 'SITL-21', 'Altitude + horizontal fence'),
    ('SITL_22_OAOptionsToggleInFlight', 'SITL-22', 'OA_OPTIONS toggle in flight'),
    ('SITL_23_ThreePointDogleg', 'SITL-23', 'Three-point dogleg'),
]

PHASE2_TESTS = [
    ('OAfastWP_GuidedInsideExclusion', 'SITL-29', 'GUIDED goto inside exclusion rejected'),
    ('OAfastWP_BreachEscape_ModeChangeAtStandoff', 'SITL-32', 'Mode change at escape stand-off'),
    ('OAfastWP_RTL_BlockedPath', 'SITL-14', 'RTL avoids fence between aircraft and home'),
    ('OAfastWP_FastWaypoints_Mission', 'SITL-17', 'Fast waypoints AUTO mission'),
    ('OAfastWP_ThreePointDogleg', 'SITL-23', 'Three-point dogleg smoothing'),
]

PHASE3_TESTS = [
    ('OAfastWP_BreachEscape_RTL_Home', 'SITL-25', 'Breach escape + RTL home (also 26,27,31)'),
    ('OAfastWP_MissionWP_InsideExclusion', 'SITL-28', 'Mission WP inside exclusion'),
    ('OAfastWP_BreachEscape_RepeatedCycles', 'SITL-30', 'Repeated breach RTL cycles'),
]

PHASE_META = {
    0: (campaign.FIRMWARE_REGRESSION_DASHBOARD_TITLE, campaign.FIRMWARE_VERSION,
        campaign.RUN_TESTS_SCRIPT + ' 0'),
    1: ('Phase 1 - SITL-01..23 regression', campaign.FIRMWARE_VERSION, campaign.RUN_TESTS_SCRIPT + ' 1'),
    2: ('Phase 2 - SITL-14,17,23,29,32', campaign.FIRMWARE_VERSION, campaign.RUN_TESTS_SCRIPT + ' 2'),
    3: ('Phase 3 - SITL-25..31 fence escape', campaign.FIRMWARE_VERSION, campaign.RUN_TESTS_SCRIPT + ' 3'),
}

KIND_CSS = {
    'start': 'ev-start', 'setup': 'ev-setup', 'action': 'ev-action', 'mode': 'ev-mode',
    'gcs': 'ev-gcs', 'check': 'ev-check', 'pass': 'ev-pass', 'fail': 'ev-fail', 'error': 'ev-error',
}


def collect_results(buildlogs, tests):
    results = []
    for name, sitl, desc in tests:
        txt = rpt.latest_test_log(buildlogs, name)
        tlog = rpt.latest_file(os.path.join(buildlogs, 'ArduCopter-%s-autotest-*.tlog' % name))
        binlog = rpt.latest_bin_for_test(buildlogs, name)

        passed = False
        content = ''
        fail_reason = ''
        if txt:
            passed, content = rpt.parse_test_result(txt)
            if not passed:
                import re
                m = re.search(r'FAILED: "[^"]+": ([^(]+)', content)
                if m:
                    fail_reason = m.group(1).strip()

        timeline, duration = rpt.parse_autotest_timeline(content)
        results.append({
            'name': name,
            'sitl_ids': [sitl],
            'description': desc,
            'passed': passed,
            'fail_reason': fail_reason,
            'timeline': timeline,
            'duration_s': duration,
            'log_basename': os.path.basename(txt) if txt else '(no log)',
            'txt_path': txt,
            'tlog_path': tlog,
            'bin_path': binlog,
        })
    return results


def write_visual_dashboard(out_dir, phase_num, results):
    title, fw, run_cmd = PHASE_META[phase_num]
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    gith = rpt.git_hash()
    n_pass = sum(1 for r in results if r['passed'])
    n_total = len(results)
    all_pass = n_pass == n_total and n_total > 0

    os.makedirs(out_dir, exist_ok=True)
    cards_dir = os.path.join(out_dir, 'cards')
    os.makedirs(cards_dir, exist_ok=True)

    for r in results:
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

    report_path = os.path.join(out_dir, 'validation_dashboard.html')

    parts = ['<!DOCTYPE html><html><head><meta charset="utf-8">',
             '<title>%s - Visual validation</title>' % html.escape(title),
             '<style>',
             '*{box-sizing:border-box;}',
             'body{font-family:Segoe UI,system-ui,sans-serif;margin:0;background:#f1f5f9;color:#0f172a;}',
             '.hero{background:linear-gradient(135deg,#1e3a5f,#0f766e);color:#fff;padding:2rem 2.5rem;}',
             '.hero h1{margin:0 0 .5rem;font-size:1.75rem;}',
             '.hero .meta{opacity:.9;font-size:.95rem;}',
             '.badge{display:inline-block;padding:.35rem 1rem;border-radius:999px;font-weight:700;font-size:1.1rem;margin-top:1rem;}',
             '.badge.pass{background:#22c55e;}.badge.fail{background:#ef4444;}',
             '.summary{display:flex;gap:1.5rem;flex-wrap:wrap;padding:1.5rem 2.5rem;}',
             '.stat{background:#fff;border-radius:12px;padding:1rem 1.5rem;box-shadow:0 1px 3px rgba(0,0,0,.08);min-width:140px;}',
             '.stat .num{font-size:2rem;font-weight:700;}',
             '.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:1rem;padding:0 2.5rem 2rem;}',
             '.tile{background:#fff;border-radius:12px;overflow:hidden;box-shadow:0 1px 3px rgba(0,0,0,.08);text-decoration:none;color:inherit;}',
             '.tile.pass{border-top:4px solid #22c55e;}.tile.fail{border-top:4px solid #ef4444;}.tile.missing{border-top:4px solid #94a3b8;}',
             '.tile img{width:100%;display:block;}',
             '.tile .lbl{padding:.75rem 1rem;font-size:.85rem;}',
             '.tile .lbl strong{display:block;font-size:1rem;}',
             '.detail{padding:0 2.5rem 3rem;}',
             '.detail section{background:#fff;border-radius:12px;margin-bottom:1.5rem;padding:1.5rem;box-shadow:0 1px 3px rgba(0,0,0,.08);}',
             '.detail h2{margin:0 0 .25rem;font-size:1.2rem;}',
             '.detail .sub{color:#64748b;font-size:.9rem;margin-bottom:1rem;}',
             '.verdict{font-size:1.5rem;font-weight:700;}.verdict.pass{color:#15803d;}.verdict.fail{color:#b91c1c;}',
             '.timeline{border-left:3px solid #cbd5e1;margin-left:.5rem;padding-left:1rem;}',
             '.timeline li{margin:.5rem 0;list-style:none;font-size:.88rem;}',
             '.timeline .t{color:#64748b;font-family:monospace;margin-right:.5rem;}',
             '.ev-gcs{color:#0f766e;}.ev-pass{color:#15803d;font-weight:600;}.ev-fail,.ev-error{color:#b91c1c;font-weight:600;}',
             '.cols{display:grid;grid-template-columns:1fr 1fr;gap:1.5rem;}',
             '@media(max-width:800px){.cols{grid-template-columns:1fr;}}',
             'img.track{max-width:100%;border:1px solid #e2e8f0;border-radius:8px;}',
             '@media print{.hero{background:#1e3a5f;-webkit-print-color-adjust:exact;print-color-adjust:exact;}}',
             '</style></head><body>']

    parts.append('<div class="hero">')
    parts.append('<h1>%s</h1>' % html.escape(title))
    parts.append('<div class="meta">Firmware <strong>%s</strong> &nbsp;|&nbsp; Generated %s &nbsp;|&nbsp; Git <code>%s</code></div>' % (
        fw, html.escape(now), html.escape(gith[:12])))
    parts.append('<span class="badge %s">%s (%d/%d tests)</span>' % (
        'pass' if all_pass else 'fail', 'ALL PASS' if all_pass else 'FAILURES PRESENT', n_pass, n_total))
    parts.append('</div>')

    parts.append('<div class="summary">')
    parts.append('<div class="stat"><div class="num">%d</div>Passed</div>' % n_pass)
    parts.append('<div class="stat"><div class="num">%d</div>Failed / missing</div>' % (n_total - n_pass))
    parts.append('<div class="stat"><div class="num">%d</div>Total SITL items</div>' % n_total)
    parts.append('<div class="stat"><div style="font-size:.85rem;color:#64748b">Evidence source</div><div style="font-weight:600">Autotest .txt logs</div><div style="font-size:.8rem">+ flight track maps from .tlog</div></div>')
    parts.append('</div>')

    parts.append('<h2 style="padding:0 2.5rem;margin:0 0 1rem;font-size:1.1rem;">Result cards (one per test — suitable for slides or audit pack)</h2>')
    parts.append('<div class="grid">')
    for r in results:
        anchor = html.escape(r['name'])
        css = 'pass' if r['passed'] else ('fail' if r.get('txt_path') else 'missing')
        parts.append('<a class="tile %s" href="#%s">' % (css, anchor))
        if r.get('card_png'):
            parts.append('<img src="%s" alt="%s">' % (html.escape(r['card_png']), anchor))
        parts.append('<div class="lbl"><strong>%s</strong>%s — %s</div>' % (
            r['sitl_ids'][0], 'PASS' if r['passed'] else 'FAIL', html.escape(r['description'][:50])))
        parts.append('</a>')
    parts.append('</div>')

    parts.append('<div class="detail">')
    parts.append('<h2 style="margin-bottom:1rem;">Detailed evidence (timeline from autotest log)</h2>')
    for r in results:
        parts.append('<section id="%s">' % html.escape(r['name']))
        parts.append('<h2>%s &mdash; <code>%s</code></h2>' % (html.escape(r['sitl_ids'][0]), html.escape(r['name'])))
        parts.append('<div class="sub">%s</div>' % html.escape(r['description']))
        parts.append('<div class="verdict %s">%s</div>' % (
            'pass' if r['passed'] else 'fail', 'PASS' if r['passed'] else 'FAIL'))
        if r.get('fail_reason'):
            parts.append('<p><strong>Failure:</strong> <code>%s</code></p>' % html.escape(r['fail_reason']))
        parts.append('<p>Sim duration: <strong>%.1f s</strong> &nbsp;|&nbsp; Log: <code>%s</code></p>' % (
            r['duration_s'], html.escape(r['log_basename'])))

        parts.append('<div class="cols">')
        parts.append('<div><h3>Execution timeline</h3><ul class="timeline">')
        if r['timeline']:
            for ev in r['timeline']:
                cls = KIND_CSS.get(ev['kind'], '')
                parts.append('<li><span class="t">%6.1fs</span><span class="%s">%s</span></li>' % (
                    ev['time'], cls, html.escape(ev['text'])))
        else:
            parts.append('<li><em>No autotest log found — run the test first.</em></li>')
        parts.append('</ul></div>')

        parts.append('<div>')
        if r.get('track_png'):
            parts.append('<h3>Flight track (.tlog)</h3>')
            parts.append('<img class="track" src="%s" alt="track">' % html.escape(r['track_png']))
        elif r.get('card_png'):
            parts.append('<h3>Result card</h3>')
            parts.append('<img class="track" src="%s" alt="card">' % html.escape(r['card_png']))
        parts.append('</div></div></section>')
    parts.append('</div>')

    parts.append('<div style="padding:2rem 2.5rem;background:#fff;border-top:1px solid #e2e8f0;font-size:.9rem;">')
    parts.append('<strong>Reproduce:</strong> <code>%s</code><br>' % html.escape(run_cmd))
    parts.append('Then regenerate this report: <code>python3 Tools/autotest/generate_oafastwp_visual_evidence.py --phase %d</code>' % phase_num)
    parts.append('</div></body></html>')

    with open(report_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(parts))

    # symlink-style copy as index.html for convenience
    index_path = os.path.join(out_dir, 'index.html')
    shutil.copy2(report_path, index_path)
    return report_path


def run_phase(phase_num, buildlogs, output_base):
    tests_map = {0: PHASE0_TESTS, 1: PHASE1_TESTS, 2: PHASE2_TESTS, 3: PHASE3_TESTS}
    stamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    out_dir = os.path.join(output_base, stamp)
    results = collect_results(buildlogs, tests_map[phase_num])
    path = write_visual_dashboard(out_dir, phase_num, results)
    latest = os.path.join(output_base, 'latest')
    if os.path.islink(latest):
        os.unlink(latest)
    elif os.path.isdir(latest):
        shutil.rmtree(latest)
    os.symlink(out_dir, latest)
    print('Visual evidence: %s' % path)
    print('Latest dashboard: %s/index.html' % latest)
    return 0 if all(r['passed'] for r in results) else 1


def main():
    parser = argparse.ArgumentParser(description='Generate visual validation evidence from autotest logs')
    parser.add_argument('--phase', type=str, default='1', choices=['0', '1', '2', '3', 'all'])
    parser.add_argument('--buildlogs', default=None)
    parser.add_argument('--output', default=None)
    args = parser.parse_args()

    if args.phase == 'all':
        rc = 0
        for p in (0, 1, 2, 3):
            buildlogs = os.path.abspath(args.buildlogs or campaign.phase_buildlogs(p))
            output_base = args.output or campaign.phase_visual_evidence(p)
            if os.path.isdir(buildlogs):
                rc = max(rc, run_phase(p, buildlogs, output_base))
        return rc

    phase_num = int(args.phase)
    buildlogs = os.path.abspath(args.buildlogs or campaign.phase_buildlogs(phase_num))
    output_base = args.output or campaign.phase_visual_evidence(phase_num)
    if not os.path.isdir(buildlogs):
        print('Logs not found: %s' % buildlogs, file=sys.stderr)
        return 1
    return run_phase(phase_num, buildlogs, output_base)


if __name__ == '__main__':
    sys.exit(main())
