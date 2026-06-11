/*
   This program is free software: you can redistribute it and/or modify
   it under the terms of the GNU General Public License as published by
   the Free Software Foundation, either version 3 of the License, or
   (at your option) any later version.

   Tether tracking library — parses GLOBAL_POSITION_INT from a beacon
   identified by MAVLink sysid and exposes its position, velocity and
   heading to Tether flight modes (TetherLoiter, TetherGuided).
*/
#pragma once

#include <AP_Common/AP_Common.h>
#include <AP_Common/Location.h>
#include <AP_HAL/AP_HAL.h>
#include <AP_Param/AP_Param.h>
#include <AP_Math/AP_Math.h>
#include <GCS_MAVLink/GCS_MAVLink.h>

class AP_Tether
{
public:
    AP_Tether();

    // returns true if the subsystem is enabled
    bool enabled() const { return _enabled; }

    // returns true if beacon data is fresh (within TETH_BCN_TIMEOUT ms)
    bool is_healthy() const;

    // get beacon position — returns false if unhealthy
    bool get_position(Location &loc) const;

    // get beacon velocity in NED frame, m/s — returns false if unhealthy
    bool get_velocity_ned(Vector3f &vel_ned) const;

    // get beacon heading in degrees (0=north) — returns false if unhealthy
    bool get_heading_deg(float &heading_deg) const;

    // enable or disable tether at runtime (mirrors TETH_ENABLE param without saving)
    void set_enabled(bool enable) { _enabled.set(enable ? 1 : 0); }

    // change active beacon sysid at runtime (0 = auto-latch first seen)
    void set_target_sysid(uint8_t sysid) { _target_sysid.set(sysid); _auto_sysid = false; }
    uint8_t get_target_sysid() const { return (uint8_t)_target_sysid; }

    // last update timestamp (ms since boot)
    uint32_t get_last_update_ms() const { return _last_update_ms; }

    // parse incoming MAVLink message — call from GCS_Mavlink.cpp
    void handle_msg(const mavlink_message_t &msg);

    // per-sysid query API — used by tether auto waypoints so each mission item
    // can reference an independent beacon without changing the global target_sysid
    static constexpr uint8_t BEACON_CACHE_MAX = 4;
    bool is_healthy(uint8_t sysid) const;
    bool get_position(uint8_t sysid, Location &loc) const;
    bool get_velocity_ned(uint8_t sysid, Vector3f &vel_ned) const;
    bool get_heading_deg(uint8_t sysid, float &heading_deg) const;

    // acceptance radius used by AUTO tether waypoints (cm)
    float get_wp_radius_cm() const { return _wp_radius * 100.0f; }

    // failsafe action taken after beacon timeout
    enum class FSAction : uint8_t { HOLD = 0, RTL = 1, LAND = 2 };
    FSAction get_fs_action() const { return (FSAction)(uint8_t)_fs_action; }

    // option bitmask
    static constexpr uint16_t OPTION_BEACON_HEADING = (1U << 0); // yaw locked to beacon track heading (not loiter)
    bool option_is_set(uint16_t opt) const { return (_options & opt) != 0; }

    // parameter list
    static const struct AP_Param::GroupInfo var_info[];

private:
    // parameters
    AP_Int8  _enabled;       // 0=disabled, 1=enabled
    AP_Int16 _target_sysid;  // beacon MAVLink sysid (0 = auto-latch)
    AP_Int16 _stale_ms;      // data considered stale after this many ms
    AP_Float _wp_radius;     // tether WP acceptance radius (m)
    AP_Int8  _fs_action;     // failsafe action: 0=Hold, 1=RTL, 2=Land
    AP_Int16 _options;       // option bitmask

    // runtime state — single-target tracking (existing guided/loiter modes)
    uint32_t _last_update_ms;
    Location _target_location;          // beacon lat/lon/alt (ABSOLUTE frame)
    Vector3f _target_velocity_ned;      // m/s, NED
    float    _target_heading_deg;
    bool     _have_target;
    bool     _auto_sysid;               // true when sysid was auto-latched
    uint8_t  _last_data_sysid;          // sysid of the beacon whose data we currently hold

    // per-sysid cache — populated for every received sysid regardless of target_sysid
    struct BeaconData {
        uint8_t  sysid;
        uint32_t last_update_ms;
        Location location;
        Vector3f velocity_ned;   // m/s NED
        float    heading_deg;
        bool     valid;
    };
    BeaconData _beacon_cache[BEACON_CACHE_MAX];

    const BeaconData* _find_beacon(uint8_t sysid) const;
};
