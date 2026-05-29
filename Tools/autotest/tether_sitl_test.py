#!/usr/bin/env python3
"""
Tether SITL integration test.

Connects to MAVProxy on port 14551, then:
  1. Reboots the flight controller to clear any crash state
  2. Sets TETH_ENABLE=1 and TETH_SYSID=2
  3. Arms the vehicle and commands a 20 m AGL takeoff
  4. Waits for altitude, then switches to TetherLoiter (mode 29)
  5. Injects a straight-north GLOBAL_POSITION_INT beacon (sysid=2)
  6. Continuously sends RC ch3=1500 (mid-stick throttle) so the
     AltHold/Loiter altitude controller holds height in SITL

Usage:
    python3 tether_sitl_test.py [--port 14551] [--speed 3] [--alt 20]
"""

import argparse
import math
import sys
import threading
import time

try:
    from pymavlink import mavutil
except ImportError:
    print("ERROR: pymavlink not installed.  Run:  pip install pymavlink")
    sys.exit(1)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
DEFAULT_LAT  =  51.4960709
DEFAULT_LON  = -0.7759028
TAKEOFF_ALT  = 20.0          # metres AGL
BEACON_SPEED  = 3.0           # m/s  (straight north)
BEACON_RATE   = 5.0           # Hz
EARTH         = 6378137.0
MODE_TETHER_LOITER = 29


def wait_for_heartbeat(conn, timeout=30):
    print("  Waiting for heartbeat ...", end="", flush=True)
    conn.wait_heartbeat(timeout=timeout)
    print(f" sysid={conn.target_system}")


def reboot_vehicle(conn):
    """Send reboot command and wait for the vehicle to come back online."""
    print("\nRebooting flight controller to clear crash state ...")
    conn.mav.command_long_send(
        conn.target_system, conn.target_component,
        mavutil.mavlink.MAV_CMD_PREFLIGHT_REBOOT_SHUTDOWN,
        0, 1, 0, 0, 0, 0, 0, 0)
    time.sleep(5)
    # Re-wait for heartbeat on a fresh connection
    conn2 = mavutil.mavlink_connection(
        f"udpin:0.0.0.0:{conn._port if hasattr(conn, '_port') else 14551}",
        source_system=255,
        source_component=mavutil.mavlink.MAV_COMP_ID_MISSIONPLANNER)
    conn2.wait_heartbeat(timeout=20)
    print(f"  Back online — mode={conn2.flightmode}")
    return conn2


def set_param(conn, name, value, retries=5):
    """Send PARAM_SET and wait for PARAM_VALUE confirmation."""
    for attempt in range(retries):
        conn.mav.param_set_send(
            conn.target_system,
            conn.target_component,
            name.encode(),
            float(value),
            mavutil.mavlink.MAV_PARAM_TYPE_REAL32)
        msg = conn.recv_match(type='PARAM_VALUE', blocking=True, timeout=3)
        if msg and msg.param_id.rstrip('\x00') == name:
            print(f"  {name} = {msg.param_value}")
            return True
        print(f"  {name} retry {attempt+1}...")
    print(f"  WARNING: could not confirm {name}")
    return False


def arm_and_takeoff(conn, alt_m):
    print(f"\nArming vehicle ...")
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
        print("  WARNING: did not confirm armed state")

    print(f"Taking off to {alt_m} m AGL ...")
    conn.mav.set_mode_send(
        conn.target_system,
        mavutil.mavlink.MAV_MODE_FLAG_CUSTOM_MODE_ENABLED,
        4)   # GUIDED = 4
    time.sleep(0.5)
    conn.mav.command_long_send(
        conn.target_system, conn.target_component,
        mavutil.mavlink.MAV_CMD_NAV_TAKEOFF,
        0, 0, 0, 0, 0, 0, 0, alt_m)

    print(f"  Climbing ...", end="", flush=True)
    reached = False
    for _ in range(120):
        msg = conn.recv_match(type='GLOBAL_POSITION_INT', blocking=True, timeout=2)
        if msg and msg.get_srcSystem() == 1:
            agl = msg.relative_alt / 1000.0
            print(f"\r  Climbing ... {agl:.1f}/{alt_m:.0f} m   ", end="", flush=True)
            if agl >= alt_m - 1.0:
                print(f"\n  Altitude reached ({agl:.1f} m) — hovering 3 s ...")
                reached = True
                break
    if not reached:
        print("\n  WARNING: takeoff altitude not reached in time")
        return False, None, None

    time.sleep(3.0)
    hover_lat, hover_lon, hover_agl = None, None, None
    for _ in range(20):
        msg = conn.recv_match(type='GLOBAL_POSITION_INT', blocking=True, timeout=1)
        if msg and msg.get_srcSystem() == 1:
            hover_lat = msg.lat / 1e7
            hover_lon = msg.lon / 1e7
            hover_agl = msg.relative_alt / 1000.0
            print(f"  Hover position: ({hover_lat:.7f}, {hover_lon:.7f})  agl={hover_agl:.1f} m")
            break
    return True, hover_lat, hover_lon


def switch_mode(conn, mode_num, mode_name):
    print(f"\nSwitching to {mode_name} (mode {mode_num}) ...")
    conn.mav.set_mode_send(
        conn.target_system,
        mavutil.mavlink.MAV_MODE_FLAG_CUSTOM_MODE_ENABLED,
        mode_num)
    for _ in range(20):
        msg = conn.recv_match(type='HEARTBEAT', blocking=True, timeout=2)
        if msg and msg.custom_mode == mode_num:
            print(f"  Mode confirmed: {mode_name}")
            return True
    print(f"  WARNING: mode {mode_name} not confirmed")
    return False


# ---------------------------------------------------------------------------
# RC throttle-hold thread
# ---------------------------------------------------------------------------
_rc_stop = threading.Event()

def rc_throttle_thread(conn, throttle_pwm=1500, rate_hz=10):
    """
    Sends RC channel override with throttle at mid-stick (1500 µs = hover).
    Required in SITL without a physical RC controller so that altitude-hold
    modes (Loiter / AltHold) maintain the current altitude rather than
    descending to zero.
    Channels set to 0 are pass-through (unchanged).
    """
    dt = 1.0 / rate_hz
    while not _rc_stop.is_set():
        conn.mav.rc_channels_override_send(
            conn.target_system,
            conn.target_component,
            0,            # ch1 roll   — pass-through
            0,            # ch2 pitch  — pass-through
            throttle_pwm, # ch3 throttle — mid-stick = hold alt
            0,            # ch4 yaw    — pass-through
            0, 0, 0, 0)   # ch5-8      — pass-through
        _rc_stop.wait(dt)


# ---------------------------------------------------------------------------
# Beacon thread  (straight north)
# ---------------------------------------------------------------------------
_beacon_stop = threading.Event()

def beacon_thread(conn, start_lat, start_lon, alt_m, speed, rate):
    """
    Injects GLOBAL_POSITION_INT with sysid=2 moving due north at `speed` m/s.
    """
    dt   = 1.0 / rate
    t    = 0.0
    lat  = start_lat
    lon  = start_lon
    vn   = speed          # constant northward velocity
    ve   = 0.0
    hdg  = 0.0            # north

    orig_sysid  = conn.mav.srcSystem
    orig_compid = conn.mav.srcComponent

    print(f"\nBeacon thread started  (sysid=2, straight north @ {speed:.1f} m/s)")

    while not _beacon_stop.is_set():
        # Advance position northward
        lat += math.degrees(vn * dt / EARTH)

        # Impersonate the beacon
        conn.mav.srcSystem    = 2
        conn.mav.srcComponent = mavutil.mavlink.MAV_COMP_ID_AUTOPILOT1

        conn.mav.global_position_int_send(
            int(t * 1000) & 0xFFFFFFFF,
            int(lat   * 1e7),
            int(lon   * 1e7),
            int(alt_m * 1000),
            int(alt_m * 1000),
            int(vn * 100),     # vx  cm/s north
            int(ve * 100),     # vy  cm/s east  (0)
            0,                 # vz  cm/s down  (0)
            int(hdg * 100))    # hdg cdeg  (0 = north)

        # Restore GCS identity
        conn.mav.srcSystem    = orig_sysid
        conn.mav.srcComponent = orig_compid

        t += dt
        _beacon_stop.wait(dt)

    print("Beacon thread stopped.")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def parse_args():
    p = argparse.ArgumentParser(description="Tether SITL integration test")
    p.add_argument("--port",  type=int,   default=14551)
    p.add_argument("--speed", type=float, default=BEACON_SPEED,
                   help="Beacon speed m/s due north (default 3)")
    p.add_argument("--alt",   type=float, default=TAKEOFF_ALT,
                   help="Takeoff altitude m AGL (default 20)")
    p.add_argument("--duration", type=float, default=60.0,
                   help="Monitoring duration seconds (default 60)")
    p.add_argument("--no-reboot", action="store_true",
                   help="Skip the startup reboot (if vehicle is known good)")
    return p.parse_args()


def main():
    args = parse_args()

    print("=" * 60)
    print("  Tether SITL Integration Test  —  Straight-North Beacon")
    print("=" * 60)
    print(f"  Connecting via udpin:0.0.0.0:{args.port} ...")

    conn = mavutil.mavlink_connection(
        f"udpin:0.0.0.0:{args.port}",
        source_system=255,
        source_component=mavutil.mavlink.MAV_COMP_ID_MISSIONPLANNER)
    conn._port = args.port   # stash for reboot helper

    wait_for_heartbeat(conn)

    # Reboot to clear any previous crash state
    if not args.no_reboot:
        conn = reboot_vehicle(conn)
        conn._port = args.port

    # ---- Tether parameters ----
    print("\nSetting Tether parameters ...")
    set_param(conn, "TETH_ENABLE", 1)
    set_param(conn, "TETH_SYSID",  2)

    # ---- Arm + Takeoff ----
    ok, hover_lat, hover_lon = arm_and_takeoff(conn, args.alt)
    if not ok:
        return

    beacon_lat = hover_lat if hover_lat is not None else DEFAULT_LAT
    beacon_lon = hover_lon if hover_lon is not None else DEFAULT_LON
    print(f"  Beacon will start at ({beacon_lat:.7f}, {beacon_lon:.7f})")

    # ---- RC throttle-hold thread (keeps altitude in AltHold/Loiter SITL) ----
    rt = threading.Thread(
        target=rc_throttle_thread,
        args=(conn, 1500, 10),
        daemon=True)
    rt.start()
    print("RC throttle-hold thread started (ch3=1500)")

    # ---- Beacon thread ----
    bt = threading.Thread(
        target=beacon_thread,
        args=(conn, beacon_lat, beacon_lon,
              args.alt, args.speed, BEACON_RATE),
        daemon=True)
    bt.start()

    time.sleep(1.5)

    # ---- Switch to TetherLoiter ----
    switch_mode(conn, MODE_TETHER_LOITER, "TetherLoiter")

    # ---- Monitor ----
    print(f"\nMonitoring ({args.duration:.0f} s) — Ctrl-C to stop early ...\n")
    deadline = time.time() + args.duration
    last_mode = MODE_TETHER_LOITER
    try:
        while time.time() < deadline:
            msg = conn.recv_match(
                type=['GLOBAL_POSITION_INT', 'STATUSTEXT', 'HEARTBEAT'],
                blocking=True, timeout=1)
            if msg is None:
                continue
            t_now = time.strftime("%H:%M:%S")
            mtype = msg.get_type()

            if mtype == 'GLOBAL_POSITION_INT' and msg.get_srcSystem() == 1:
                agl  = msg.relative_alt / 1000.0
                vn   = msg.vx / 100.0
                ve   = msg.vy / 100.0
                lat  = msg.lat / 1e7
                lon  = msg.lon / 1e7
                print(f"\r[{t_now}] lat={lat:.7f} lon={lon:.7f} "
                      f"agl={agl:.1f}m vN={vn:+.1f} vE={ve:+.1f}",
                      end="", flush=True)

            elif mtype == 'STATUSTEXT':
                print(f"\n[{t_now}] {msg.severity_str if hasattr(msg,'severity_str') else ''} {msg.text}")

            elif mtype == 'HEARTBEAT' and msg.get_srcSystem() == 1:
                mode = msg.custom_mode
                if mode != last_mode:
                    print(f"\n[{t_now}] Mode changed: {last_mode} → {mode}")
                    last_mode = mode

    except KeyboardInterrupt:
        pass

    print("\n\nTest complete — stopping threads ...")
    _beacon_stop.set()
    _rc_stop.set()
    bt.join(timeout=3)
    rt.join(timeout=3)
    print("Done.")


if __name__ == "__main__":
    main()
