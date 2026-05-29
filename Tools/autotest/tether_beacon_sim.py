#!/usr/bin/env python3
"""
Tether beacon simulator.

Sends two streams simultaneously:
  1. GLOBAL_POSITION_INT (MAVLink, sysid=2) to the aircraft so AP_Tether tracks it.
  2. NMEA GGA + RMC + ZDA over UDP to port 3000 so QGC shows it on the map.

Beacon starts ~20 m north of the WW03 SITL location and moves northeast at 3 m/s.

QGC setup for NMEA map marker:
  Settings (gear) → General → NMEA GPS Device → UDP Port 3000

Usage:
    python3 tether_beacon_sim.py
    python3 tether_beacon_sim.py --port 14551 --nmea-host 172.30.224.1
    python3 tether_beacon_sim.py --lat 51.4961 --lon -0.7758 --alt 30
"""

import argparse
import math
import socket
import sys
import time

try:
    from pymavlink import mavutil
except ImportError:
    print("ERROR: pymavlink not installed.  Run:  pip install pymavlink")
    sys.exit(1)

# ---------------------------------------------------------------------------
DEFAULT_LAT =  51.4962507   # ~20 m north of WW03 SITL location
DEFAULT_LON = -0.7759028
DEFAULT_ALT =  0.0          # m MSL

SPEED_MS    = 3.0
HEADING_DEG = 45.0          # northeast
EARTH       = 6378137.0     # WGS-84 equatorial radius, m
_SQRT2_INV  = 1.0 / math.sqrt(2.0)
VN          = SPEED_MS * _SQRT2_INV   # north m/s
VE          = SPEED_MS * _SQRT2_INV   # east  m/s


def parse_args():
    p = argparse.ArgumentParser(
        description="Tether beacon simulator — MAVLink GLOBAL_POSITION_INT + NMEA GGA/RMC/ZDA")
    p.add_argument("--port",      type=int, default=14551,
                   help="MAVProxy output port to bind on (default: 14551, matches guided test)")
    p.add_argument("--sysid",     type=int, default=2,
                   help="MAVLink system ID for this beacon (default: 2, set TETH_BCN_SYSID to match)")
    p.add_argument("--nmea-host", default="127.0.0.1",
                   help="NMEA UDP destination host (default: 127.0.0.1, use Windows IP for WSL)")
    p.add_argument("--nmea-port", type=int, default=3000,
                   help="NMEA UDP destination port (default: 3000)")
    p.add_argument("--lat",  type=float, default=DEFAULT_LAT)
    p.add_argument("--lon",  type=float, default=DEFAULT_LON)
    p.add_argument("--alt",  type=float, default=DEFAULT_ALT,
                   help="Altitude m MSL (default: 0)")
    p.add_argument("--rate", type=float, default=5.0,
                   help="Send rate Hz (default: 5)")
    return p.parse_args()


# ---------------------------------------------------------------------------
# NMEA helpers

def _checksum(body: str) -> str:
    cs = 0
    for c in body:
        cs ^= ord(c)
    return f"{cs:02X}"


def _ddmm(deg: float):
    d = int(abs(deg))
    m = (abs(deg) - d) * 60.0
    return d, m


def make_gga(lat: float, lon: float, alt: float) -> str:
    t = time.gmtime()
    utc = f"{t.tm_hour:02d}{t.tm_min:02d}{t.tm_sec:02d}.00"
    ld, lm = _ddmm(lat);  ns = 'N' if lat >= 0 else 'S'
    od, om = _ddmm(lon);  ew = 'E' if lon >= 0 else 'W'
    body = (f"GPGGA,{utc},"
            f"{ld:02d}{lm:07.4f},{ns},"
            f"{od:03d}{om:07.4f},{ew},"
            f"1,08,1.0,{alt:.1f},M,0.0,M,,")
    return f"${body}*{_checksum(body)}\r\n"


def make_rmc(lat: float, lon: float, speed_ms: float, heading_deg: float) -> str:
    t = time.gmtime()
    utc  = f"{t.tm_hour:02d}{t.tm_min:02d}{t.tm_sec:02d}.00"
    date = f"{t.tm_mday:02d}{t.tm_mon:02d}{str(t.tm_year)[-2:]}"
    kts  = speed_ms * 1.94384
    ld, lm = _ddmm(lat);  ns = 'N' if lat >= 0 else 'S'
    od, om = _ddmm(lon);  ew = 'E' if lon >= 0 else 'W'
    body = (f"GPRMC,{utc},A,"
            f"{ld:02d}{lm:07.4f},{ns},"
            f"{od:03d}{om:07.4f},{ew},"
            f"{kts:.2f},{heading_deg:.2f},{date},,")
    return f"${body}*{_checksum(body)}\r\n"


def make_zda() -> str:
    t = time.gmtime()
    utc = f"{t.tm_hour:02d}{t.tm_min:02d}{t.tm_sec:02d}.00"
    body = f"GPZDA,{utc},{t.tm_mday:02d},{t.tm_mon:02d},{t.tm_year},00,00"
    return f"${body}*{_checksum(body)}\r\n"


# ---------------------------------------------------------------------------

def run(args):
    # Bind on the MAVProxy output port (same pattern as tether_guided_test.py).
    # udpin receives heartbeats from MAVProxy which establishes the return path;
    # subsequent sends go back through MAVProxy to SITL.
    print("Tether beacon simulator")
    print(f"  Connecting to udpin:0.0.0.0:{args.port} ...")
    mav = mavutil.mavlink_connection(
        f"udpin:0.0.0.0:{args.port}",
        source_system=args.sysid,
        source_component=mavutil.mavlink.MAV_COMP_ID_AUTOPILOT1)

    print("  Waiting for heartbeat ...", end="", flush=True)
    mav.wait_heartbeat(timeout=30)
    print(f" OK (sysid={mav.target_system})")

    # UDP socket for NMEA
    nmea_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    nmea_dest = (args.nmea_host, args.nmea_port)

    dt  = 1.0 / args.rate
    lat = args.lat
    lon = args.lon
    t   = 0.0

    print(f"  start     : ({lat:.7f}, {lon:.7f})  alt={args.alt:.1f} m MSL")
    print(f"  motion    : {SPEED_MS:.1f} m/s NE  (vN={VN:.2f} vE={VE:.2f} m/s)")
    print(f"  MAVLink   : udpin port {args.port}  sysid={args.sysid}  (set TETH_BCN_SYSID={args.sysid})")
    print(f"  NMEA      : udp:{args.nmea_host}:{args.nmea_port}  @ {args.rate:.1f} Hz")
    print(f"  QGC       : Settings -> General -> NMEA GPS Device -> UDP Port {args.nmea_port}")
    print("Press Ctrl-C to stop\n")

    try:
        while True:
            # Advance position
            lat += math.degrees(VN * dt / EARTH)
            lon += math.degrees(VE * dt / (EARTH * math.cos(math.radians(lat))))

            # --- MAVLink GLOBAL_POSITION_INT ---
            mav.mav.global_position_int_send(
                int(t * 1000) & 0xFFFFFFFF,  # time_boot_ms
                int(lat * 1e7),              # lat  degE7
                int(lon * 1e7),              # lon  degE7
                int(args.alt * 1000),        # alt  mm MSL
                int(args.alt * 1000),        # relative_alt mm AGL
                int(VN * 100),               # vx  cm/s north
                int(VE * 100),               # vy  cm/s east
                0,                           # vz  cm/s down
                int(HEADING_DEG * 100))      # hdg cdeg

            # --- NMEA ---
            nmea_payload = (
                make_gga(lat, lon, args.alt) +
                make_rmc(lat, lon, SPEED_MS, HEADING_DEG) +
                make_zda()
            ).encode('ascii')
            try:
                nmea_sock.sendto(nmea_payload, nmea_dest)
            except OSError as e:
                print(f"\nNMEA send error: {e}")

            ts = time.strftime("%H:%M:%S")
            print(f"\r  [{ts}]  lat={lat:.7f}  lon={lon:.7f}  t={t:.1f}s",
                  end="", flush=True)

            t += dt
            time.sleep(dt)

    except KeyboardInterrupt:
        print("\nBeacon simulator stopped.")
    finally:
        nmea_sock.close()


if __name__ == "__main__":
    run(parse_args())
