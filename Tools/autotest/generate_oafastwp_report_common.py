#!/usr/bin/env python3
"""Shared HTML report utilities for OAfastWP SITL autotest phases."""

from __future__ import print_function

import glob
import html
import math
import os
import re
import subprocess
from datetime import datetime

try:
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.patches import Circle
    HAS_MPL = True
except ImportError:
    HAS_MPL = False

from pymavlink import mavutil

FENCE_CENTER = (-35.3629712, 149.1646305)
FENCE_RADIUS_M = 20.0
HOME = (-35.362938, 149.165085)

PARAMS = {
    'OA_TYPE': 2,
    'OA_OPTIONS': 4,
    'OA_MARGIN_MAX': 5,
    'FENCE_TYPE': 7,
    'FENCE_ACTION': 1,
    'WPNAV_SPEED': 500,
    'RTL_ALT': 1500,
}


def repo_root():
    return os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))


def default_buildlogs():
    return os.environ.get('BUILDLOGS', os.path.join(repo_root(), '..', 'buildlogs'))


def latest_test_log(buildlogs, test_name):
    '''Newest autotest .txt for a test (includes -retry-N files).'''
    pattern = os.path.join(buildlogs, 'ArduCopter-%s*.txt' % test_name)
    return latest_file(pattern)


def _resolve_test_dir(logs_root, test_name):
    try:
        import firmware_SITL_validation_campaign as campaign
        return campaign.resolve_test_log_dir(logs_root, test_name)
    except Exception:
        return None


def latest_test_log_for_campaign(logs_root, test_name):
    '''Newest log for a test across organized full_/rerun_ run folders.'''
    test_dir = _resolve_test_dir(logs_root, test_name)
    if test_dir:
        txt = latest_test_log(test_dir, test_name)
        if txt:
            return txt
    return latest_test_log(logs_root, test_name)


def latest_tlog_for_test(logs_root, test_name):
    test_dir = _resolve_test_dir(logs_root, test_name) or logs_root
    return latest_file(os.path.join(test_dir, 'ArduCopter-%s-autotest-*.tlog' % test_name))


def latest_bin_for_test(logs_root, test_name):
    test_dir = _resolve_test_dir(logs_root, test_name) or logs_root
    files = glob.glob(os.path.join(test_dir, 'ArduCopter-%s-*.BIN' % test_name))
    if not files:
        files = glob.glob(os.path.join(test_dir, 'ArduCopter-%s*.BIN' % test_name))
    if not files:
        return None
    return max(files, key=os.path.getsize)


def git_hash():
    try:
        out = subprocess.check_output(
            ['git', 'rev-parse', 'HEAD'],
            cwd=repo_root(),
            stderr=subprocess.DEVNULL,
        )
        return out.decode('utf-8').strip()
    except (subprocess.CalledProcessError, OSError):
        return 'unknown'


def latest_file(pattern):
    files = glob.glob(pattern)
    if not files:
        return None
    return max(files, key=os.path.getmtime)


def parse_test_result(txt_path):
    with open(txt_path, 'r', encoding='utf-8', errors='replace') as f:
        content = f.read()
    passed = bool(re.search(r'PASSED:.*' + re.escape(os.path.basename(txt_path).replace('.txt', '')), content))
    if not passed:
        passed = 'PASSED:' in content and 'FAILED:' not in content.split('PASSED:')[-1]
    m = re.search(r'PASSED: "([^"]+)"', content)
    if m:
        passed = True
    if re.search(r'FAILED:.*' + re.escape(os.path.basename(txt_path).replace('.txt', '')), content):
        passed = False
    return passed, content


def extract_lines(content, patterns):
    hits = []
    for line in content.splitlines():
        for pat in patterns:
            if re.search(pat, line, re.IGNORECASE):
                clean = re.sub(r'^AT-[0-9.]+:\s*', '', line)
                if clean not in hits:
                    hits.append(clean)
                break
    return hits


def parse_autotest_timeline(content, max_events=30):
    """Extract key milestones from an autotest .txt log for visual timeline."""
    if not content:
        return [], 0.0

    gcs_keywords = (
        'Fence Breached', 'Fence Indexed', 'Dijkstra', 'ArduPilot Ready',
        'Disarming', 'Mission:', 'PreArm', 'EKF3', 'Flight plan',
        'breach escape', 'OAfastWP',
    )
    events = []
    seen = set()
    times = []

    for line in content.splitlines():
        m = re.match(r'AT-([0-9.]+):\s*(.*)$', line)
        if not m:
            continue
        sim_t = float(m.group(1))
        body = m.group(2).strip()
        times.append(sim_t)

        kind = None
        text = body
        if '##########' in body:
            kind = 'start'
            text = re.sub(r'#+\s*', '', body).strip()
        elif body.startswith('PASSED:'):
            kind = 'pass'
        elif body.startswith('FAILED:'):
            kind = 'fail'
        elif body.startswith('Exception caught:'):
            kind = 'error'
            text = body.replace('Exception caught:', '').strip()
        elif body.startswith('AP:'):
            ap_text = body[3:].strip()
            if any(k in ap_text for k in gcs_keywords):
                kind = 'gcs'
                text = ap_text
        elif re.search(r'Got mode \w+', body):
            kind = 'mode'
        elif 'Loading fence' in body or 'Loading mission' in body:
            kind = 'setup'
        elif 'change_mode' in body or 'Arm vehicle' in body or 'Disarm' in body:
            kind = 'action'
        elif 'wait_current_waypoint' in body or 'Waiting RTL' in body:
            kind = 'check'

        if kind is None:
            continue
        key = (kind, text[:100])
        if key in seen:
            continue
        seen.add(key)
        events.append({'time': sim_t, 'kind': kind, 'text': text[:160]})

    duration = (max(times) - min(times)) if times else 0.0
    if len(events) > max_events:
        events = events[:3] + events[-(max_events - 3):]
    return events, duration


def render_result_card_png(result, png_path):
    """Single-page visual proof card from parsed autotest log (for slides/PDF)."""
    if not HAS_MPL:
        return False

    passed = result.get('passed', False)
    sitl = result.get('sitl_ids', [''])[0]
    name = result.get('name', '')
    desc = result.get('description', '')
    timeline = result.get('timeline', [])
    duration = result.get('duration_s', 0.0)
    log_name = result.get('log_basename', '')

    bg = '#ecfdf3' if passed else '#fef2f2'
    accent = '#15803d' if passed else '#b91c1c'
    verdict = 'PASS' if passed else 'FAIL'

    fig, ax = plt.subplots(figsize=(10, 7))
    fig.patch.set_facecolor('white')
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis('off')

    ax.add_patch(plt.Rectangle((0, 0.88), 1, 0.12, color=accent, transform=ax.transAxes))
    ax.text(0.03, 0.94, sitl, color='white', fontsize=22, fontweight='bold', va='center')
    ax.text(0.97, 0.94, verdict, color='white', fontsize=28, fontweight='bold',
            ha='right', va='center')

    ax.add_patch(plt.Rectangle((0, 0.08), 1, 0.80, color=bg, transform=ax.transAxes))
    ax.text(0.03, 0.82, name, fontsize=14, fontweight='bold', va='top', color='#111')
    ax.text(0.03, 0.77, desc, fontsize=10, va='top', color='#333', wrap=True)

    y = 0.70
    ax.text(0.03, y, 'Test timeline (from autotest log):', fontsize=11, fontweight='bold', color='#111')
    y -= 0.045
    kind_markers = {
        'start': '>', 'setup': '+', 'action': '*', 'mode': '~', 'gcs': '!',
        'check': '?', 'pass': 'OK', 'fail': 'X', 'error': '!!',
    }
    for ev in timeline[:14]:
        marker = kind_markers.get(ev['kind'], '-')
        line = '[%ss] %s  %s' % (ev['time'], marker, ev['text'])
        if len(line) > 95:
            line = line[:92] + '...'
        ax.text(0.04, y, line, fontsize=8.5, va='top', family='monospace', color='#222')
        y -= 0.038
        if y < 0.12:
            break

    footer = 'Duration: %.1fs sim  |  Log: %s' % (duration, log_name)
    ax.text(0.03, 0.04, footer, fontsize=8, color='#555')
    fig.tight_layout(pad=0.5)
    fig.savefig(png_path, dpi=150, facecolor='white')
    plt.close(fig)
    return True


def count_forbidden(content, patterns):
    found = []
    for line in content.splitlines():
        if 'AP:' not in line:
            continue
        for pat in patterns:
            if re.search(pat, line, re.IGNORECASE):
                if pat not in found:
                    found.append(pat)
                break
    return found


def count_oadj_state(bin_path, state=2):
    if not bin_path or not os.path.isfile(bin_path):
        return None
    try:
        mlog = mavutil.mavlink_connection(bin_path)
        count = 0
        while True:
            m = mlog.recv_match(type='OADJ', blocking=False)
            if m is None:
                break
            if getattr(m, 'State', None) == state:
                count += 1
        return count
    except Exception:
        return None


def meters_to_deg(lat, meters_n, meters_e):
    dlat = meters_n / 111320.0
    dlng = meters_e / (111320.0 * math.cos(math.radians(lat)))
    return dlat, dlng


def plot_track(tlog_path, png_path, title):
    if not HAS_MPL or not tlog_path:
        return False
    lats = []
    lons = []
    try:
        mlog = mavutil.mavlink_connection(tlog_path)
        while True:
            m = mlog.recv_match(type=['GLOBAL_POSITION_INT', 'GPS_RAW_INT'], blocking=False)
            if m is None:
                break
            if m.get_type() == 'GLOBAL_POSITION_INT':
                lat = m.lat / 1e7
                lon = m.lon / 1e7
            else:
                if m.lat == 0 and m.lon == 0:
                    continue
                lat = m.lat / 1e7
                lon = m.lon / 1e7
            lats.append(lat)
            lons.append(lon)
    except Exception as ex:
        print('Warning: could not read tlog %s: %s' % (tlog_path, ex))
        return False

    if len(lats) < 2:
        return False

    fig, ax = plt.subplots(figsize=(8, 8))
    ax.plot(lons, lats, 'b-', linewidth=1.2, label='Flight track')
    ax.plot(lons[0], lats[0], 'go', markersize=8, label='Start')
    ax.plot(lons[-1], lats[-1], 'rs', markersize=8, label='End')
    ax.plot(HOME[1], HOME[0], 'k^', markersize=10, label='Home')

    dlat, dlng = meters_to_deg(FENCE_CENTER[0], FENCE_RADIUS_M, 0)
    radius_deg = max(abs(dlat), abs(dlng))
    circle = Circle(
        (FENCE_CENTER[1], FENCE_CENTER[0]),
        radius_deg,
        fill=False,
        edgecolor='red',
        linewidth=2,
        linestyle='--',
        label='Exclusion fence (20 m)',
    )
    ax.add_patch(circle)
    ax.plot(FENCE_CENTER[1], FENCE_CENTER[0], 'rx', markersize=10)

    ax.set_xlabel('Longitude')
    ax.set_ylabel('Latitude')
    ax.set_title(title)
    ax.legend(loc='best', fontsize=8)
    ax.set_aspect('equal', adjustable='box')
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig(png_path, dpi=120)
    plt.close(fig)
    return True


def write_report(out_dir, buildlogs, results, phase_title, run_script):
    os.makedirs(out_dir, exist_ok=True)
    report_html = os.path.join(out_dir, 'index.html')
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    gith = git_hash()
    all_pass = all(r['passed'] for r in results)

    parts = ['<!DOCTYPE html><html><head><meta charset="utf-8">',
             '<title>%s</title>' % html.escape(phase_title),
             '<style>',
             'body{font-family:system-ui,sans-serif;max-width:960px;margin:2em auto;padding:0 1em;}',
             'table{border-collapse:collapse;width:100%;margin:1em 0;}',
             'th,td{border:1px solid #ccc;padding:8px;text-align:left;vertical-align:top;}',
             'th{background:#f4f4f4;}',
             '.pass{color:#0a0;font-weight:bold;}.fail{color:#c00;font-weight:bold;}',
             'img{max-width:100%;border:1px solid #ddd;margin:0.5em 0;}',
             'code{background:#f4f4f4;padding:2px 4px;}',
             'ul.evidence{font-size:0.9em;}',
             '</style></head><body>']

    parts.append('<h1>%s</h1>' % html.escape(phase_title))
    parts.append('<p><strong>Generated:</strong> %s<br>' % html.escape(now))
    parts.append('<strong>Git commit:</strong> <code>%s</code><br>' % html.escape(gith))
    parts.append('<strong>Overall:</strong> <span class="%s">%s</span></p>' % (
        'pass' if all_pass else 'fail', 'PASS' if all_pass else 'FAIL'))

    parts.append('<h2>Test matrix (copter)</h2>')
    parts.append('<table><tr><th>Spreadsheet</th><th>Autotest</th><th>Result</th><th>Checks</th></tr>')
    for r in results:
        for sitl in r['sitl_ids']:
            checks = html.escape(r['description'])
            parts.append('<tr><td>%s</td><td><code>%s</code></td><td class="%s">%s</td><td>%s</td></tr>' % (
                sitl, r['name'], 'pass' if r['passed'] else 'fail',
                'PASS' if r['passed'] else 'FAIL', checks))
    parts.append('</table>')

    parts.append('<h2>Configuration</h2><ul>')
    for k, v in sorted(PARAMS.items()):
        parts.append('<li><code>%s=%s</code></li>' % (k, v))
    parts.append('</ul>')
    parts.append('<p>Exclusion fence centre: <code>%.7f, %.7f</code>, radius %s m</p>' % (
        FENCE_CENTER[0], FENCE_CENTER[1], FENCE_RADIUS_M))

    for r in results:
        parts.append('<h2>%s</h2>' % html.escape(r['name']))
        parts.append('<p><strong>Result:</strong> <span class="%s">%s</span></p>' % (
            'pass' if r['passed'] else 'fail', 'PASS' if r['passed'] else 'FAIL'))
        if r.get('oadj_count') is not None:
            parts.append('<p><strong>OADJ State=2 (breach escape) entries in log:</strong> %d</p>' % r['oadj_count'])

        forbidden = r.get('forbidden_found', [])
        if forbidden:
            parts.append('<p class="fail"><strong>Unexpected debug messages seen:</strong> %s</p>' % (
                html.escape(', '.join(forbidden))))

        parts.append('<h3>Extracted evidence</h3><ul class="evidence">')
        for line in r.get('evidence', [])[:20]:
            parts.append('<li><code>%s</code></li>' % html.escape(line))
        parts.append('</ul>')

        if r.get('map_png'):
            rel = os.path.basename(r['map_png'])
            parts.append('<h3>Flight track map</h3>')
            parts.append('<p>Track from MAVLink tlog; red dashed circle = exclusion fence.</p>')
            parts.append('<img src="%s" alt="flight track">' % rel)

        parts.append('<h3>Artifacts</h3><ul>')
        for label, path in r.get('artifacts', []):
            if path:
                parts.append('<li>%s: <code>%s</code></li>' % (label, html.escape(path)))
        parts.append('</ul>')

    parts.append('<h2>How to reproduce</h2>')
    parts.append('<pre>%s</pre>' % html.escape(run_script))
    parts.append('</body></html>')

    with open(report_html, 'w', encoding='utf-8') as f:
        f.write('\n'.join(parts))
    return report_html
