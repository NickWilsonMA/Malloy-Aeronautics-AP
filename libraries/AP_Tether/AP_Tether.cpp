/*
   This program is free software: you can redistribute it and/or modify
   it under the terms of the GNU General Public License as published by
   the Free Software Foundation, either version 3 of the License, or
   (at your option) any later version.
*/

#include "AP_Tether.h"

extern const AP_HAL::HAL &hal;

// parameter defaults
#define AP_TETHER_STALE_MS_DEFAULT 2000

const AP_Param::GroupInfo AP_Tether::var_info[] = {

    // @Param: ENABLE
    // @DisplayName: Tether tracking enable
    // @Description: Enable the tether tracking subsystem. Must be 1 for TetherLoiter or TetherGuided modes to be usable.
    // @Values: 0:Disabled,1:Enabled
    // @User: Standard
    AP_GROUPINFO_FLAGS("ENABLE", 1, AP_Tether, _enabled, 0, AP_PARAM_FLAG_ENABLE),

    // @Param: BCN_SYSID
    // @DisplayName: Beacon MAVLink system ID
    // @Description: MAVLink system ID of the beacon to track. Set to 0 to auto-latch on to the first GLOBAL_POSITION_INT message seen. Change this value in flight to switch to a different beacon.
    // @Range: 0 255
    // @User: Standard
    AP_GROUPINFO("BCN_SYSID", 2, AP_Tether, _target_sysid, 0),

    // @Param: BCN_TIMEOUT
    // @DisplayName: Beacon data timeout
    // @Description: Time in milliseconds after which beacon data is considered stale if no new message has been received.
    // @Range: 500 10000
    // @Units: ms
    // @User: Standard
    AP_GROUPINFO("BCN_TIMEOUT", 3, AP_Tether, _stale_ms, AP_TETHER_STALE_MS_DEFAULT),

    // @Param: WPNAV_RADIUS
    // @DisplayName: Tether waypoint acceptance radius
    // @Description: Horizontal radius in metres within which the aircraft must be (relative to the beacon-frame target offset) before the dwell timer starts. Increase if the aircraft cannot converge on large offsets.
    // @Range: 1 50
    // @Units: m
    // @User: Standard
    AP_GROUPINFO("WP_RADIUS", 4, AP_Tether, _wp_radius, 5.0f),

    // @Param: FS_OPTIONS
    // @DisplayName: Tether beacon failsafe action
    // @Description: Action taken when the beacon has been lost for longer than BCN_TIMEOUT. 0=Hold position indefinitely, 1=RTL, 2=Land.
    // @Values: 0:Hold,1:RTL,2:Land
    // @User: Standard
    AP_GROUPINFO("FS_OPTIONS", 5, AP_Tether, _fs_action, 1),

    // @Param: OPTIONS
    // @DisplayName: Tether options bitmask
    // @Description: Bitmask of tether behaviour options. Bit0: fix aircraft yaw to the beacon track heading (applies to AUTO tether waypoints only, not Loiter).
    // @Bitmask: 0:BeaconHeading
    // @User: Standard
    AP_GROUPINFO("OPTIONS", 6, AP_Tether, _options, 0),

    AP_GROUPEND
};

AP_Tether::AP_Tether() :
    _last_update_ms(0),
    _target_heading_deg(0.0f),
    _have_target(false),
    _auto_sysid(false),
    _last_data_sysid(0)
{
    AP_Param::setup_object_defaults(this, var_info);
    memset(_beacon_cache, 0, sizeof(_beacon_cache));
}

// is_healthy — true if enabled, data is from the current target sysid, and within timeout
bool AP_Tether::is_healthy() const
{
    if (!_enabled || !_have_target) {
        return false;
    }
    // Reject stale data from a previous beacon after a sysid change
    if (_last_data_sysid != (uint8_t)_target_sysid) {
        return false;
    }
    return (AP_HAL::millis() - _last_update_ms) < (uint32_t)_stale_ms;
}

bool AP_Tether::get_position(Location &loc) const
{
    if (!is_healthy()) return false;
    loc = _target_location;
    return true;
}

bool AP_Tether::get_velocity_ned(Vector3f &vel_ned) const
{
    if (!is_healthy()) return false;
    vel_ned = _target_velocity_ned;
    return true;
}

bool AP_Tether::get_heading_deg(float &heading_deg) const
{
    if (!is_healthy()) return false;
    heading_deg = _target_heading_deg;
    return true;
}

// handle_msg — called for every incoming MAVLink message from GCS_Mavlink.cpp
void AP_Tether::handle_msg(const mavlink_message_t &msg)
{
    if (!_enabled) return;

    // only interested in GLOBAL_POSITION_INT
    if (msg.msgid != MAVLINK_MSG_ID_GLOBAL_POSITION_INT) return;

    const uint8_t incoming_sysid = msg.sysid;

    // decode packet
    mavlink_global_position_int_t pkt;
    mavlink_msg_global_position_int_decode(&msg, &pkt);

    const Location  loc(pkt.lat, pkt.lon, pkt.alt / 10, Location::AltFrame::ABSOLUTE);
    const Vector3f  vel(pkt.vx * 0.01f, pkt.vy * 0.01f, pkt.vz * 0.01f);
    const float     hdg = pkt.hdg * 0.01f;
    const uint32_t  now = AP_HAL::millis();

    // update per-sysid cache for every beacon regardless of target_sysid
    bool cached = false;
    for (uint8_t i = 0; i < BEACON_CACHE_MAX; i++) {
        if (_beacon_cache[i].valid && _beacon_cache[i].sysid == incoming_sysid) {
            _beacon_cache[i].location       = loc;
            _beacon_cache[i].velocity_ned   = vel;
            _beacon_cache[i].heading_deg    = hdg;
            _beacon_cache[i].last_update_ms = now;
            cached = true;
            break;
        }
    }
    if (!cached) {
        // find an empty slot
        for (uint8_t i = 0; i < BEACON_CACHE_MAX; i++) {
            if (!_beacon_cache[i].valid) {
                _beacon_cache[i].sysid          = incoming_sysid;
                _beacon_cache[i].location       = loc;
                _beacon_cache[i].velocity_ned   = vel;
                _beacon_cache[i].heading_deg    = hdg;
                _beacon_cache[i].last_update_ms = now;
                _beacon_cache[i].valid          = true;
                break;
            }
        }
        // if all slots full, oldest slot is silently dropped (cache is a best-effort store)
    }

    // update single-target tracking state for existing guided/loiter modes
    if ((uint8_t)_target_sysid == 0) {
        // auto-latch mode: accept the first sysid we see
        if (!_auto_sysid) {
            _target_sysid.set(incoming_sysid);
            _auto_sysid = true;
        } else if (incoming_sysid != (uint8_t)_target_sysid) {
            return;
        }
    } else {
        if (incoming_sysid != (uint8_t)_target_sysid) {
            return;
        }
    }

    _target_location     = loc;
    _target_velocity_ned = vel;
    _target_heading_deg  = hdg;
    _last_data_sysid     = incoming_sysid;
    _have_target         = true;
    _last_update_ms      = now;
}

// --- per-sysid query API ---

const AP_Tether::BeaconData* AP_Tether::_find_beacon(uint8_t sysid) const
{
    for (uint8_t i = 0; i < BEACON_CACHE_MAX; i++) {
        if (_beacon_cache[i].valid && _beacon_cache[i].sysid == sysid) {
            return &_beacon_cache[i];
        }
    }
    return nullptr;
}

bool AP_Tether::is_healthy(uint8_t sysid) const
{
    if (!_enabled) return false;
    const BeaconData* b = _find_beacon(sysid);
    return b && (AP_HAL::millis() - b->last_update_ms) < (uint32_t)_stale_ms;
}

bool AP_Tether::get_position(uint8_t sysid, Location &loc) const
{
    const BeaconData* b = _find_beacon(sysid);
    if (!b || !is_healthy(sysid)) return false;
    loc = b->location;
    return true;
}

bool AP_Tether::get_velocity_ned(uint8_t sysid, Vector3f &vel_ned) const
{
    const BeaconData* b = _find_beacon(sysid);
    if (!b || !is_healthy(sysid)) return false;
    vel_ned = b->velocity_ned;
    return true;
}

bool AP_Tether::get_heading_deg(uint8_t sysid, float &heading_deg) const
{
    const BeaconData* b = _find_beacon(sysid);
    if (!b || !is_healthy(sysid)) return false;
    heading_deg = b->heading_deg;
    return true;
}
