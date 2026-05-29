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

    // @Param: SYSID
    // @DisplayName: Beacon MAVLink system ID
    // @Description: MAVLink system ID of the beacon to track. Set to 0 to auto-latch on to the first GLOBAL_POSITION_INT message seen. Change this value in flight to switch to a different beacon.
    // @Range: 0 255
    // @User: Standard
    AP_GROUPINFO("SYSID", 2, AP_Tether, _target_sysid, 0),

    // @Param: TIMEOUT
    // @DisplayName: Beacon data timeout
    // @Description: Time in milliseconds after which beacon data is considered stale if no new message has been received.
    // @Range: 500 10000
    // @Units: ms
    // @User: Standard
    AP_GROUPINFO("TIMEOUT", 3, AP_Tether, _stale_ms, AP_TETHER_STALE_MS_DEFAULT),

    AP_GROUPEND
};

AP_Tether::AP_Tether() :
    _last_update_ms(0),
    _target_heading_deg(0.0f),
    _have_target(false),
    _auto_sysid(false)
{
    AP_Param::setup_object_defaults(this, var_info);
}

// is_healthy — true if enabled and beacon data arrived within timeout
bool AP_Tether::is_healthy() const
{
    if (!_enabled || !_have_target) {
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

    if ((uint8_t)_target_sysid == 0) {
        // auto-latch mode: accept the first sysid we see
        if (!_auto_sysid) {
            _target_sysid.set(incoming_sysid);
            _auto_sysid = true;
        } else if (incoming_sysid != (uint8_t)_target_sysid) {
            return;  // already latched to a different sysid
        }
    } else {
        // fixed sysid mode
        if (incoming_sysid != (uint8_t)_target_sysid) {
            return;
        }
    }

    // decode packet
    mavlink_global_position_int_t pkt;
    mavlink_msg_global_position_int_decode(&msg, &pkt);

    // store position
    // pkt.lat/lon in degE7, pkt.alt in mm MSL → Location wants cm for alt
    _target_location = Location(pkt.lat, pkt.lon, pkt.alt / 10, Location::AltFrame::ABSOLUTE);

    // store velocity: GLOBAL_POSITION_INT vx/vy/vz are cm/s in NED frame
    _target_velocity_ned.x = pkt.vx * 0.01f;   // north, m/s
    _target_velocity_ned.y = pkt.vy * 0.01f;   // east,  m/s
    _target_velocity_ned.z = pkt.vz * 0.01f;   // down,  m/s

    // store heading: hdg in cdeg (0=north, 36000=north)
    _target_heading_deg = pkt.hdg * 0.01f;

    _have_target = true;
    _last_update_ms = AP_HAL::millis();
}
