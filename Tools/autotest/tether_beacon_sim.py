#!/usr/bin/env python3
"""
Tether beacon simulator — two simultaneous beacons, NMEA only.

Beacon 1 (default: NMEA port 3000):
  250 m radius, clockwise at 3 m/s.

Beacon 2 (default: NMEA port 3001):
  300 m radius, anti-clockwise at 3 m/s.

Each beacon sends NMEA GGA + RMC + ZDA over UDP so QGC shows it on the map.

QGC setup:
  Settings → General → NMEA GPS Device → UDP Port <nmea-port1 or nmea-port2>

Usage:
    python3 tether_beacon_sim.py
    python3 tether_beacon_sim.py --nmea-host 172.30.224.1
    python3 tether_beacon_sim.py --lat 51.4961 --lon -0.7758
"""

import argparse
import math
import socket
import time

# ---------------------------------------------------------------------------
DEFAULT_LAT =  51.4962507
DEFAULT_LON = -0.7759028
DEFAULT_ALT =  0.0          # m MSL
SPEED_MS    =  3.0
EARTH       =  6378137.0   # WGS-84 equatorial radius, m


def parse_args():
    p = argparse.ArgumentParser(
        description="Tether beacon simulator — two NMEA streams")

    p.add_argument("--nmea-port",  type=int, default=3000,
                   help="Beacon 1 NMEA UDP port (default: 3000)")
    p.add_argument("--nmea-port2", type=int, default=3001,
                   help="Beacon 2 NMEA UDP port (default: 3001)")
    p.add_argument("--nmea-host",  default="127.0.0.1",
                   help="NMEA UDP destination host (default: 127.0.0.1)")
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


def send_nmea(sock, dest, lat, lon, alt, speed_ms, heading):
    payload = (
        make_gga(lat, lon, alt) +
        make_rmc(lat, lon, speed_ms, heading) +
        make_zda()
    ).encode('ascii')
    try:
        sock.sendto(payload, dest)
    except OSError as e:
        print(f"\nNMEA send error: {e}")


# ---------------------------------------------------------------------------

def beacon_position(center_lat, center_lon, cos_lat, radius, omega, t, clockwise):
    """Return (lat, lon, vN, vE, heading) for a circular orbit."""
    theta = omega * t
    lat = center_lat + math.degrees(radius * math.cos(theta) / EARTH)
    if clockwise:
        lon = center_lon + math.degrees(radius * math.sin(theta) / (EARTH * cos_lat))
        vN = -SPEED_MS * math.sin(theta)
        vE =  SPEED_MS * math.cos(theta)
    else:
        lon = center_lon - math.degrees(radius * math.sin(theta) / (EARTH * cos_lat))
        vN = -SPEED_MS * math.sin(theta)
        vE = -SPEED_MS * math.cos(theta)
    heading = math.degrees(math.atan2(vE, vN)) % 360.0
    return lat, lon, vN, vE, heading


def run(args):
    print("Tether beacon simulator — NMEA only")
    print()

    nmea_sock  = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    nmea_dest1 = (args.nmea_host, args.nmea_port)
    nmea_dest2 = (args.nmea_host, args.nmea_port2)

    center_lat = args.lat
    center_lon = args.lon
    cos_lat    = math.cos(math.radians(center_lat))

    radius1 = 250.0
    omega1  = SPEED_MS / radius1
    period1 = 2 * math.pi / omega1

    radius2 = 300.0
    omega2  = SPEED_MS / radius2
    period2 = 2 * math.pi / omega2

    dt = 1.0 / args.rate
    t  = 0.0

    print(f"  Centre   : ({center_lat:.7f}, {center_lon:.7f})  alt={args.alt:.1f} m MSL")
    print(f"  Beacon 1 : r={radius1:.0f} m  CW   period={period1:.0f} s  NMEA → {args.nmea_host}:{args.nmea_port}")
    print(f"  Beacon 2 : r={radius2:.0f} m  CCW  period={period2:.0f} s  NMEA → {args.nmea_host}:{args.nmea_port2}")
    print(f"  Rate     : {args.rate:.1f} Hz")
    print("Press Ctrl-C to stop\n")

    try:
        while True:
            lat1, lon1, vN1, vE1, hdg1 = beacon_position(
                center_lat, center_lon, cos_lat, radius1, omega1, t, clockwise=True)
            send_nmea(nmea_sock, nmea_dest1, lat1, lon1, args.alt, SPEED_MS, hdg1)

            lat2, lon2, vN2, vE2, hdg2 = beacon_position(
                center_lat, center_lon, cos_lat, radius2, omega2, t, clockwise=False)
            send_nmea(nmea_sock, nmea_dest2, lat2, lon2, args.alt, SPEED_MS, hdg2)

            ts = time.strftime("%H:%M:%S")
            print(f"\r  [{ts}]  "
                  f"B1 ({lat1:.6f},{lon1:.6f}) hdg={hdg1:.1f}°  "
                  f"B2 ({lat2:.6f},{lon2:.6f}) hdg={hdg2:.1f}°",
                  end="", flush=True)

            t += dt
            time.sleep(dt)

    except KeyboardInterrupt:
        print("\nBeacon simulator stopped.")
    finally:
        nmea_sock.close()


if __name__ == "__main__":
    run(parse_args())
