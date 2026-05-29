#!/usr/bin/env python3
"""
Tether beacon simulator for SITL testing.

Broadcasts GLOBAL_POSITION_INT on a configurable MAVLink sysid so that
the AP_Tether library (TETH_SYSID) sees a moving beacon and the
TetherLoiter / TetherGuided flight modes can be exercised in SITL.

Usage examples:
    # Stationary beacon at WW03
    python3 tether_beacon_sim.py

    # 3 m/s circle, beacon sysid=2
    python3 tether_beacon_sim.py --move circle --speed 3 --sysid 2

    # Straight north at 5 m/s, custom start position
    python3 tether_beacon_sim.py --move north --speed 5 \
        --lat 51.4960709 --lon -0.7759028

    # Custom MAVProxy output port (e.g. second --out from sim_vehicle.py)
    python3 tether_beacon_sim.py --out 127.0.0.1:14551

Prerequisites:
    pip install pymavlink
"""

import argparse
import math
import sys
import time

try:
    from pymavlink import mavutil
except ImportError:
    print("ERROR: pymavlink not installed.  Run:  pip install pymavlink")
    sys.exit(1)


# ---------------------------------------------------------------------------
# Defaults match the WW03 SITL location in locations.txt
DEFAULT_LAT =  51.4960709
DEFAULT_LON =  -0.7759028
DEFAULT_ALT = 30.0          # m MSL (reasonable AGL for a moving vehicle)


def parse_args():
    p = argparse.ArgumentParser(
        description="Tether beacon simulator — broadcasts GLOBAL_POSITION_INT for SITL Tether mode testing")

    p.add_argument("--out",   default="127.0.0.1:14550",
                   help="MAVLink UDP destination host:port (default: 127.0.0.1:14550)")
    p.add_argument("--sysid", type=int, default=2,
                   help="MAVLink system ID for this beacon (default: 2, set TETH_SYSID to match)")
    p.add_argument("--lat",   type=float, default=DEFAULT_LAT,
                   help="Starting latitude  (default: WW03)")
    p.add_argument("--lon",   type=float, default=DEFAULT_LON,
                   help="Starting longitude (default: WW03)")
    p.add_argument("--alt",   type=float, default=DEFAULT_ALT,
                   help="Altitude m MSL (default: 30 m)")
    p.add_argument("--move",  default="none",
                   choices=["none", "circle", "north", "south", "east", "west"],
                   help="Motion pattern (default: none / stationary)")
    p.add_argument("--speed", type=float, default=3.0,
                   help="Beacon speed m/s for moving patterns (default: 3)")
    p.add_argument("--radius",type=float, default=30.0,
                   help="Circle radius in metres (default: 30, only used with --move circle)")
    p.add_argument("--rate",  type=float, default=5.0,
                   help="Broadcast rate Hz (default: 5)")
    return p.parse_args()


def run(args):
    conn = mavutil.mavlink_connection(
        f"udpout:{args.out}",
        source_system=args.sysid,
        source_component=mavutil.mavlink.MAV_COMP_ID_AUTOPILOT1)

    lat   = args.lat
    lon   = args.lon
    alt   = args.alt
    spd   = args.speed
    dt    = 1.0 / args.rate
    t     = 0.0
    EARTH = 6378137.0       # WGS-84 equatorial radius, m

    print(f"Tether beacon simulator")
    print(f"  sysid  : {args.sysid}  (set TETH_SYSID={args.sysid} on vehicle)")
    print(f"  output : udp:{args.out}")
    print(f"  start  : ({lat:.7f}, {lon:.7f})  alt={alt:.0f} m MSL")
    print(f"  motion : {args.move}  speed={spd} m/s  rate={args.rate} Hz")
    print(f"Press Ctrl-C to stop\n")

    try:
        while True:
            # ------------------------------------------------------------------
            # Compute instantaneous NED velocity and advance position
            # ------------------------------------------------------------------
            vn = ve = 0.0

            if args.move == "circle":
                omega = spd / args.radius           # rad/s
                vn = -spd * math.sin(omega * t)
                ve =  spd * math.cos(omega * t)

            elif args.move == "north":
                vn =  spd
            elif args.move == "south":
                vn = -spd
            elif args.move == "east":
                ve =  spd
            elif args.move == "west":
                ve = -spd
            # "none" → vn=ve=0, stationary

            # Flat-earth position integration (accurate to < 1 m for radius < 5 km)
            lat += math.degrees(vn * dt / EARTH)
            lon += math.degrees(ve * dt / (EARTH * math.cos(math.radians(lat))))

            # Heading from velocity (0 = north)
            if abs(vn) > 0.01 or abs(ve) > 0.01:
                heading_deg = math.degrees(math.atan2(ve, vn)) % 360.0
            else:
                heading_deg = 0.0

            # ------------------------------------------------------------------
            # Send GLOBAL_POSITION_INT  (MAVLink message ID 33)
            # Fields:
            #   time_boot_ms  uint32  ms
            #   lat           int32   degE7
            #   lon           int32   degE7
            #   alt           int32   mm MSL
            #   relative_alt  int32   mm AGL  (approximated as same as alt here)
            #   vx            int16   cm/s  north
            #   vy            int16   cm/s  east
            #   vz            int16   cm/s  down  (0 — beacon stays level)
            #   hdg           uint16  cdeg  (0=north, 36000=north)
            # ------------------------------------------------------------------
            conn.mav.global_position_int_send(
                int(t * 1000) & 0xFFFFFFFF,     # time_boot_ms (wraps at ~49 days)
                int(lat * 1e7),                  # lat  degE7
                int(lon * 1e7),                  # lon  degE7
                int(alt * 1000),                 # alt  mm MSL
                int(alt * 1000),                 # relative_alt mm AGL (approx)
                int(vn * 100),                   # vx  cm/s north
                int(ve * 100),                   # vy  cm/s east
                0,                               # vz  cm/s down
                int(heading_deg * 100))          # hdg cdeg

            print(
                f"\r  lat={lat:12.7f}  lon={lon:12.7f}  "
                f"vN={vn:+5.1f} vE={ve:+5.1f} m/s  "
                f"hdg={heading_deg:5.1f}°  t={t:6.1f}s",
                end="", flush=True)

            t += dt
            time.sleep(dt)

    except KeyboardInterrupt:
        print("\nBeacon simulator stopped.")


if __name__ == "__main__":
    run(parse_args())
