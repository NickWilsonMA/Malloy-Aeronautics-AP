#!/usr/bin/env python3
"""
TetherGuided SITL integration test.

What this script does:
  1. Reboots the flight controller
  2. Sets TETH_ENABLE=1 and TETH_SYSID=2
  3. Arms and takes off to --alt metres AGL (in GUIDED mode)
  4. Starts a straight-north beacon (sysid=2) so TetherGuided has a live target
  5. Switches to TetherGuided (mode 30)
  6. Every --interval seconds, reads the vehicle's current GPS position and
     sends a SET_POSITION_TARGET_GLOBAL_INT offset by --offset metres in one of:
         FRONT  (+N)  LEFT  (-E)  BEHIND (-S)  RIGHT (+E)

     TetherGuided captures the offset from the beacon at that moment and then
     continuously drives the vehicle to  beacon_pos + offset  as the beacon
     moves.  This script provides the "human pointing" input — all tracking
     logic is in the firmware.

Usage:
    python3 tether_guided_test.py [--port 14551] [--speed 3] [--alt 20]
                                  [--offset 20] [--interval 20]
"""

import argparse
import math
import socket
import sys
import threading
import time

try:
    from pymavlink import mavutil
except ImportError:
    print("ERROR: pymavlink not installed.  Run:  pip install pymavlink")
    sys.exit(1)

# ---------------------------------------------------------------------------
EARTH              = 6378137.0
DEFAULT_LAT        = 51.4960709
DEFAULT_LON        = -0.7759028
TAKEOFF_ALT        = 20.0
BEACON_SPEED       = 3.0           # m/s  straight north
BEACON_RATE        = 5.0           # Hz
MODE_TETHER_GUIDED = 30

OFFSET_SEQUENCE = [
    ("BEHIND (-S)", -1,   0),
    ("LEFT   (-E)",  0,  -1),
    ("FRONT  (+N)", +1,   0),
    ("RIGHT  (+E)",  0,  +1),
]

# ---------------------------------------------------------------------------
def m_to_deg_lat(metres):
    return metres / EARTH * (180.0 / math.pi)

def m_to_deg_lon(metres, lat_deg):
    return metres / (EARTH * math.cos(math.radians(lat_deg))) * (180.0 / math.pi)

# ---------------------------------------------------------------------------
# Shared state
# ---------------------------------------------------------------------------
_veh    = {"lat": None, "lon": None, "agl": None}
_beacon = {"lat": None, "lon": None}          # updated by beacon_thread
_veh_lock    = threading.Lock()
_beacon_lock = threading.Lock()
_stop = threading.Event()


# ---------------------------------------------------------------------------
# MAVLink helpers
# ---------------------------------------------------------------------------
def connect(port):
    conn = mavutil.mavlink_connection(
        f"udpin:0.0.0.0:{port}", source_system=255,
        source_component=mavutil.mavlink.MAV_COMP_ID_MISSIONPLANNER)
    print("  Waiting for heartbeat ...", end="", flush=True)
    conn.wait_heartbeat(timeout=30)
    print(f" sysid={conn.target_system}")
    return conn


def reboot_vehicle(conn, port):
    print("\nRebooting flight controller ...")
    conn.mav.command_long_send(
        conn.target_system, conn.target_component,
        mavutil.mavlink.MAV_CMD_PREFLIGHT_REBOOT_SHUTDOWN,
        0, 1, 0, 0, 0, 0, 0, 0)
    time.sleep(6)
    conn2 = connect(port)
    print(f"  Back online — mode={conn2.flightmode}")
    return conn2


def set_param(conn, name, value, retries=5):
    for attempt in range(retries):
        conn.mav.param_set_send(
            conn.target_system, conn.target_component,
            name.encode(), float(value),
            mavutil.mavlink.MAV_PARAM_TYPE_REAL32)
        msg = conn.recv_match(type='PARAM_VALUE', blocking=True, timeout=3)
        if msg and msg.param_id.rstrip('\x00') == name:
            print(f"  {name} = {msg.param_value}")
            return True
        print(f"  {name} retry {attempt + 1}...")
    print(f"  WARNING: could not confirm {name}")
    return False


def set_mode(conn, mode_num):
    """Send set_mode and wait for confirmation; return True on success."""
    conn.mav.set_mode_send(
        conn.target_system,
        mavutil.mavlink.MAV_MODE_FLAG_CUSTOM_MODE_ENABLED, mode_num)
    for _ in range(20):
        msg = conn.recv_match(type='HEARTBEAT', blocking=True, timeout=2)
        if msg and msg.get_srcSystem() == conn.target_system and msg.custom_mode == mode_num:
            return True
    return False


def arm_and_takeoff(conn, alt_m):
    # ---- Arm ----
    print("\nArming ...")
    conn.mav.command_long_send(
        conn.target_system, conn.target_component,
        mavutil.mavlink.MAV_CMD_COMPONENT_ARM_DISARM,
        0, 1, 0, 0, 0, 0, 0, 0)
    for _ in range(40):
        msg = conn.recv_match(type='HEARTBEAT', blocking=True, timeout=2)
        if msg and (msg.base_mode & mavutil.mavlink.MAV_MODE_FLAG_SAFETY_ARMED):
            print("  Armed!")
            break
    else:
        print("  WARNING: arm not confirmed")

    # ---- Switch to GUIDED and confirm ----
    print("Switching to GUIDED ...")
    if not set_mode(conn, 4):
        print("  WARNING: GUIDED mode not confirmed — proceeding anyway")
    else:
        print("  GUIDED mode confirmed")

    # ---- Takeoff ----
    print(f"Taking off to {alt_m} m AGL ...")
    conn.mav.command_long_send(
        conn.target_system, conn.target_component,
        mavutil.mavlink.MAV_CMD_NAV_TAKEOFF,
        0, 0, 0, 0, 0, 0, 0, alt_m)

    print("  Climbing ...", end="", flush=True)
    for _ in range(120):
        msg = conn.recv_match(type='GLOBAL_POSITION_INT', blocking=True, timeout=2)
        if msg and msg.get_srcSystem() == conn.target_system:
            agl = msg.relative_alt / 1000.0
            print(f"\r  Climbing ... {agl:.1f}/{alt_m:.0f} m   ", end="", flush=True)
            if agl >= alt_m - 1.0:
                print(f"\n  Altitude reached ({agl:.1f} m) — hovering 3 s ...")
                break
    time.sleep(3.0)

    # Capture hover position
    hover_lat, hover_lon = DEFAULT_LAT, DEFAULT_LON
    for _ in range(20):
        msg = conn.recv_match(type='GLOBAL_POSITION_INT', blocking=True, timeout=1)
        if msg and msg.get_srcSystem() == conn.target_system:
            hover_lat = msg.lat / 1e7
            hover_lon = msg.lon / 1e7
            print(f"  Hover: ({hover_lat:.7f}, {hover_lon:.7f})  "
                  f"agl={msg.relative_alt/1000:.1f} m")
            break
    return hover_lat, hover_lon


def send_position_target(conn, lat_deg, lon_deg, alt_m_rel):
    """
    SET_POSITION_TARGET_GLOBAL_INT — position only, ignore vel/accel/yaw.
    Frame: MAV_FRAME_GLOBAL_RELATIVE_ALT_INT.
    """
    type_mask = (
        mavutil.mavlink.POSITION_TARGET_TYPEMASK_VX_IGNORE  |
        mavutil.mavlink.POSITION_TARGET_TYPEMASK_VY_IGNORE  |
        mavutil.mavlink.POSITION_TARGET_TYPEMASK_VZ_IGNORE  |
        mavutil.mavlink.POSITION_TARGET_TYPEMASK_AX_IGNORE  |
        mavutil.mavlink.POSITION_TARGET_TYPEMASK_AY_IGNORE  |
        mavutil.mavlink.POSITION_TARGET_TYPEMASK_AZ_IGNORE  |
        mavutil.mavlink.POSITION_TARGET_TYPEMASK_YAW_IGNORE |
        mavutil.mavlink.POSITION_TARGET_TYPEMASK_YAW_RATE_IGNORE
    )
    conn.mav.set_position_target_global_int_send(
        0,
        conn.target_system, conn.target_component,
        mavutil.mavlink.MAV_FRAME_GLOBAL_RELATIVE_ALT_INT,
        type_mask,
        int(lat_deg * 1e7),
        int(lon_deg * 1e7),
        alt_m_rel,
        0, 0, 0,
        0, 0, 0,
        0, 0)


# ---------------------------------------------------------------------------
# Background threads
# ---------------------------------------------------------------------------

def beacon_thread(conn, start_lat, start_lon, alt_m, speed, rate):
    """
    Continuously injects GLOBAL_POSITION_INT with sysid=2 moving due north
    at `speed` m/s.  This is the tether beacon the firmware tracks.
    """
    dt   = 1.0 / rate
    t    = 0.0
    lat  = start_lat
    lon  = start_lon
    vn   = speed

    orig_sys  = conn.mav.srcSystem
    orig_comp = conn.mav.srcComponent

    print(f"Beacon thread started  (sysid=2, north @ {speed:.1f} m/s)")

    next_hb = 0.0

    while not _stop.is_set():
        lat += m_to_deg_lat(vn * dt)

        with _beacon_lock:
            _beacon["lat"] = lat
            _beacon["lon"] = lon

        conn.mav.srcSystem    = 2
        conn.mav.srcComponent = mavutil.mavlink.MAV_COMP_ID_AUTOPILOT1

        # Heartbeat at 1 Hz — QGC registers sysid=2 as a second vehicle on the map
        if t >= next_hb:
            conn.mav.heartbeat_send(
                mavutil.mavlink.MAV_TYPE_GROUND_ROVER,
                mavutil.mavlink.MAV_AUTOPILOT_GENERIC,
                mavutil.mavlink.MAV_MODE_FLAG_SAFETY_ARMED,
                0,
                mavutil.mavlink.MAV_STATE_ACTIVE)
            next_hb = t + 1.0

        conn.mav.global_position_int_send(
            int(t * 1000) & 0xFFFFFFFF,
            int(lat * 1e7), int(lon * 1e7),
            int(alt_m * 1000), int(alt_m * 1000),
            int(vn * 100), 0, 0, 0)

        conn.mav.srcSystem    = orig_sys
        conn.mav.srcComponent = orig_comp

        t += dt
        _stop.wait(dt)

    print("Beacon thread stopped.")


def rc_throttle_thread(conn):
    """Hold ch3 at mid-stick so altitude-hold modes work without a physical RC."""
    while not _stop.is_set():
        conn.mav.rc_channels_override_send(
            conn.target_system, conn.target_component,
            0, 0, 1500, 0, 0, 0, 0, 0)
        _stop.wait(0.1)


def telemetry_thread(conn):
    """Drain messages and keep _veh current; print STATUSTEXT."""
    while not _stop.is_set():
        msg = conn.recv_match(
            type=['GLOBAL_POSITION_INT', 'STATUSTEXT'],
            blocking=True, timeout=0.5)
        if msg is None:
            continue
        if msg.get_type() == 'GLOBAL_POSITION_INT' and \
                msg.get_srcSystem() == conn.target_system:
            with _veh_lock:
                _veh["lat"] = msg.lat / 1e7
                _veh["lon"] = msg.lon / 1e7
                _veh["agl"] = msg.relative_alt / 1000.0
        elif msg.get_type() == 'STATUSTEXT':
            print(f"\n  [{time.strftime('%H:%M:%S')}] {msg.text}")


def _nmea_checksum(body: str) -> str:
    cs = 0
    for c in body:
        cs ^= ord(c)
    return f"{cs:02X}"


def _ddmm(deg: float):
    """Return (DD, MM.MMMM) from decimal degrees."""
    d = int(abs(deg))
    m = (abs(deg) - d) * 60.0
    return d, m


def _make_gga(lat_deg: float, lon_deg: float, alt_m: float) -> str:
    """$GPGGA — position, altitude, fix quality."""
    t = time.gmtime()
    utc = f"{t.tm_hour:02d}{t.tm_min:02d}{t.tm_sec:02d}.00"
    ld, lm = _ddmm(lat_deg);  ns = 'N' if lat_deg >= 0 else 'S'
    od, om = _ddmm(lon_deg);  ew = 'E' if lon_deg >= 0 else 'W'
    body = (f"GPGGA,{utc},"
            f"{ld:02d}{lm:07.4f},{ns},"
            f"{od:03d}{om:07.4f},{ew},"
            f"1,08,1.0,{alt_m:.1f},M,0.0,M,,")
    return f"${body}*{_nmea_checksum(body)}\r\n"


def _make_zda() -> str:
    """$GPZDA — UTC date and time."""
    t = time.gmtime()
    utc = f"{t.tm_hour:02d}{t.tm_min:02d}{t.tm_sec:02d}.00"
    body = f"GPZDA,{utc},{t.tm_mday:02d},{t.tm_mon:02d},{t.tm_year},00,00"
    return f"${body}*{_nmea_checksum(body)}\r\n"


def _make_rmc(lat_deg: float, lon_deg: float, speed_ms: float) -> str:
    """$GPRMC — validity flag, speed (knots), heading, date."""
    t = time.gmtime()
    utc  = f"{t.tm_hour:02d}{t.tm_min:02d}{t.tm_sec:02d}.00"
    date = f"{t.tm_mday:02d}{t.tm_mon:02d}{str(t.tm_year)[-2:]}"
    kts  = speed_ms * 1.94384   # m/s → knots
    ld, lm = _ddmm(lat_deg);  ns = 'N' if lat_deg >= 0 else 'S'
    od, om = _ddmm(lon_deg);  ew = 'E' if lon_deg >= 0 else 'W'
    body = (f"GPRMC,{utc},A,"           # A = valid fix
            f"{ld:02d}{lm:07.4f},{ns},"
            f"{od:03d}{om:07.4f},{ew},"
            f"{kts:.2f},0.00,{date},,")  # heading 0 = north, no mag var
    return f"${body}*{_nmea_checksum(body)}\r\n"


def nmea_beacon_thread(host, port, alt_m, speed_ms):
    """
    Streams NMEA GGA sentences for the beacon position over UDP.
    QGC displays this as a live marker on the map.

    QGC setup:
      Settings (gear) → General → NMEA GPS Device
        Device type : UDP Port
        UDP port    : {port}
      Then enable Show GPS position on map / Follow Me GPS if prompted.
    """
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    print(f"  NMEA beacon → udp:{host}:{port}  (1 Hz, GGA+RMC)")
    print(f"  QGC: Settings → General → NMEA GPS Device → UDP Port {port}")

    # Send a test packet immediately so you can confirm UDP is flowing
    # before the beacon position is available (uses default SITL location).
    test_gga = _make_gga(DEFAULT_LAT, DEFAULT_LON, alt_m)
    test_rmc = _make_rmc(DEFAULT_LAT, DEFAULT_LON, 0.0)
    test_zda = _make_zda()
    try:
        sock.sendto((test_gga + test_rmc + test_zda).encode('ascii'), (host, port))
        print(f"  NMEA test packet sent → {host}:{port}")
        print(f"    {test_gga.strip()}")
        print(f"    {test_rmc.strip()}")
        print(f"    {test_zda.strip()}")
    except OSError as e:
        print(f"  NMEA send error: {e}")

    while not _stop.is_set():
        with _beacon_lock:
            lat = _beacon["lat"]
            lon = _beacon["lon"]

        if lat is not None:
            try:
                sock.sendto(
                    (_make_gga(lat, lon, alt_m) +
                     _make_rmc(lat, lon, speed_ms) +
                     _make_zda()).encode('ascii'),
                    (host, port))
            except OSError as e:
                print(f"  NMEA send error: {e}")

        _stop.wait(1.0)   # 1 Hz is plenty for a map marker

    sock.close()
    print("NMEA beacon thread stopped.")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def parse_args():
    p = argparse.ArgumentParser(description="TetherGuided SITL test")
    p.add_argument("--port",     type=int,   default=14551)
    p.add_argument("--speed",    type=float, default=BEACON_SPEED,
                   help="Beacon speed m/s north (default 3)")
    p.add_argument("--alt",      type=float, default=TAKEOFF_ALT,
                   help="Takeoff altitude m AGL (default 20)")
    p.add_argument("--offset",   type=float, default=20.0,
                   help="Offset from vehicle position in metres (default 20)")
    p.add_argument("--interval", type=float, default=20.0,
                   help="Seconds between guided commands (default 20)")
    p.add_argument("--no-reboot", action="store_true")
    p.add_argument("--beacon-host", type=str, default="127.0.0.1",
                   help="Host to push beacon telemetry to (default 127.0.0.1, use Windows IP for WSL e.g. 172.30.224.1)")
    p.add_argument("--beacon-port", type=int, default=3000,
                   help="UDP port for beacon GCS telemetry (0=off, default 3000)")
    return p.parse_args()


def main():
    args = parse_args()

    print("=" * 62)
    print("  TetherGuided SITL Test")
    print("=" * 62)
    print(f"  Connecting to udpin:0.0.0.0:{args.port} ...")

    conn = connect(args.port)

    if not args.no_reboot:
        conn = reboot_vehicle(conn, args.port)

    print("\nSetting parameters ...")
    set_param(conn, "TETH_ENABLE",  1)
    set_param(conn, "TETH_SYSID",   2)
    # GUID_OPTIONS bit 6 (=64): use WPNav for position control in Guided/TetherGuided.
    # TetherGuided forces this on internally, but set it explicitly so the base
    # Guided mode also uses the same WPNav path if the vehicle falls back to it.
    set_param(conn, "GUID_OPTIONS", 64)

    hover_lat, hover_lon = arm_and_takeoff(conn, args.alt)

    # ---- Start background threads ----
    threading.Thread(target=rc_throttle_thread, args=(conn,), daemon=True).start()
    threading.Thread(target=beacon_thread,
                     args=(conn, hover_lat, hover_lon, args.alt,
                           args.speed, BEACON_RATE),
                     daemon=True).start()
    threading.Thread(target=telemetry_thread, args=(conn,), daemon=True).start()

    if args.beacon_port:
        threading.Thread(target=nmea_beacon_thread,
                         args=(args.beacon_host, args.beacon_port,
                               args.alt, args.speed),
                         daemon=True).start()

    time.sleep(1.5)  # let beacon establish a lock in AP_Tether

    # ---- Switch to TetherGuided ----
    print(f"\nSwitching to TetherGuided (mode {MODE_TETHER_GUIDED}) ...")
    if not set_mode(conn, MODE_TETHER_GUIDED):
        print("  WARNING: TetherGuided not confirmed")
    else:
        print("  TetherGuided confirmed")
    time.sleep(1.0)

    # ---- Scale offset sequence ----
    D = args.offset
    sequence = [(lbl, dn * D, de * D) for (lbl, dn, de) in OFFSET_SEQUENCE]

    labels = [lbl for lbl, _, _ in sequence]
    print(f"\nCycling: {' → '.join(labels)} → (repeat)  every {args.interval:.0f} s")
    print(f"  ±{D:.0f} m offset  |  beacon moves north at {args.speed:.1f} m/s")
    print(f"  Ctrl-C to stop\n")

    last_send = time.time() - args.interval   # fire immediately on first tick
    pos_idx   = 0
    last_mode = MODE_TETHER_GUIDED

    try:
        while True:
            now = time.time()

            # ---- Send next guided command when interval expires ----
            if now - last_send >= args.interval:
                label, dn, de = sequence[pos_idx % len(sequence)]

                with _beacon_lock:
                    blat = _beacon["lat"] or hover_lat
                    blon = _beacon["lon"] or hover_lon
                with _veh_lock:
                    vagl = _veh["agl"] or args.alt

                # Command is relative to the BEACON, not the vehicle.
                # The firmware captures offset = cmd - beacon_now, so using
                # beacon position directly gives a clean cardinal offset.
                cmd_lat = blat + m_to_deg_lat(dn)
                cmd_lon = blon + m_to_deg_lon(de, blat)

                send_position_target(conn, cmd_lat, cmd_lon, args.alt)

                cycle = pos_idx // len(sequence) + 1
                step  = pos_idx % len(sequence) + 1
                ts = time.strftime("%H:%M:%S")
                print(f"\n  [{ts}] Cycle {cycle}  Step {step}/{len(sequence)}: {label}")
                print(f"    beacon=({blat:.7f}, {blon:.7f})  agl={vagl:.1f}m")
                print(f"    target=({cmd_lat:.7f}, {cmd_lon:.7f})  "
                      f"Δ=({dn:+.0f}m N, {de:+.0f}m E) from beacon")

                last_send = now
                pos_idx  += 1

            # ---- Print live telemetry ----
            with _veh_lock:
                vlat = _veh["lat"]
                vlon = _veh["lon"]
                vagl = _veh["agl"]

            if vlat is not None:
                ts        = time.strftime("%H:%M:%S")
                secs_left = max(0, args.interval - (time.time() - last_send))
                cur_label = sequence[(pos_idx - 1) % len(sequence)][0] if pos_idx > 0 else "---"
                print(f"\r  [{ts}] {cur_label}  "
                      f"veh=({vlat:.7f},{vlon:.7f}) agl={vagl:.1f}m  "
                      f"next={secs_left:.0f}s",
                      end="", flush=True)

            # ---- Check for mode change ----
            hb = conn.recv_match(type='HEARTBEAT', blocking=False)
            if hb and hb.get_srcSystem() == conn.target_system:
                mode = hb.custom_mode
                if mode != last_mode:
                    ts = time.strftime("%H:%M:%S")
                    print(f"\n  [{ts}] Mode: {last_mode} → {mode}")
                    last_mode = mode

            time.sleep(0.5)

    except KeyboardInterrupt:
        pass

    print("\n\nTest complete.")
    _stop.set()


if __name__ == "__main__":
    main()
