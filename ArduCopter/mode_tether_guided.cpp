#include "Copter.h"

#if MODE_TETHER_GUIDED_ENABLED == ENABLED

/*
 * TetherGuided flight mode
 *
 * Continuous tracking uses the PosVelAccel controller with beacon velocity
 * feedforward — the same mechanism ArduCopter's ModeFollow uses to track
 * another vehicle.  WPNav cannot smoothly track a continuously moving
 * target because its S-curve planner always tries to decelerate to a stop
 * at the destination; velocity feedforward avoids this entirely.
 *
 * GCS commands (SET_POSITION_TARGET_GLOBAL_INT / DO_REPOSITION) go through
 * the standard ModeGuided path, which uses WPNav when GUID_OPTIONS bit 6
 * (=64) is set — giving OA/fence avoidance on the initial move to the
 * commanded position.  Once the offset is captured, continuous tracking
 * takes over via PosVelAccel + fence check.
 *
 * Speed/acceleration limits: WPNAV_SPEED, WPNAV_ACCEL (WPNav initial move)
 * and WPNAV_SPEED for the PosVelAccel tracking loop are all inherited from
 * the standard Guided mode controllers.
 */

// Minimum target displacement (cm) before re-issuing set_destination_posvel.
static constexpr float TETHER_GUIDED_UPDATE_DIST_CM = 10.0f;

// -----------------------------------------------------------------------
bool ModeTetherGuided::init(bool ignore_checks)
{
    if (!g2.tether.enabled()) {
        gcs().send_text(MAV_SEVERITY_WARNING, "TetherGuided: set TETH_ENABLE=1");
        return false;
    }

    _offset_valid       = false;
    _new_cmd_pending    = false;
    _target_alt_cm      = 0.0f;
    _offset_ne_cm.zero();
    _pending_cmd_neu_cm.zero();
    _last_update_neu_cm.zero();

    if (!ModeGuided::init(ignore_checks)) {
        return false;
    }

    // Hold current position with PosVelAccel (zero velocity) until a GCS
    // command arrives and an offset is captured.
    const Vector3f& cur = copter.inertial_nav.get_position_neu_cm();
    set_destination_posvel(cur, Vector3f(), false, 0.0f, false, 0.0f, false);
    _last_update_neu_cm = cur;

    return true;
}

// -----------------------------------------------------------------------
// Intercept Location-based GCS commands to set the pending offset flag.
bool ModeTetherGuided::set_destination(const Location& dest_loc,
                                        bool use_yaw, float yaw_cd,
                                        bool use_yaw_rate, float yaw_rate_cds,
                                        bool yaw_relative)
{
    Vector3f dest_neu_cm;
    if (dest_loc.get_vector_from_origin_NEU(dest_neu_cm)) {
        _pending_cmd_neu_cm = dest_neu_cm;
        _new_cmd_pending    = true;
    }

    // Base class handles the actual move: uses WPNav if GUID_OPTIONS bit 6
    // is set (fence/OA active on the initial commanded move), otherwise
    // uses Pos controller.
    return ModeGuided::set_destination(dest_loc, use_yaw, yaw_cd,
                                        use_yaw_rate, yaw_rate_cds, yaw_relative);
}

// -----------------------------------------------------------------------
void ModeTetherGuided::run()
{
    if (_new_cmd_pending) {
        _new_cmd_pending = false;
        _try_capture_offset();
    }

    if (_offset_valid) {
        _update_destination();
    }

    ModeGuided::run();
}

// -----------------------------------------------------------------------
void ModeTetherGuided::_try_capture_offset()
{
    Location beacon_loc;
    Vector3f beacon_neu_cm;

    if (g2.tether.is_healthy() &&
        g2.tether.get_position(beacon_loc) &&
        beacon_loc.get_vector_from_origin_NEU(beacon_neu_cm)) {

        _offset_ne_cm.x = _pending_cmd_neu_cm.x - beacon_neu_cm.x;
        _offset_ne_cm.y = _pending_cmd_neu_cm.y - beacon_neu_cm.y;
        _target_alt_cm  = _pending_cmd_neu_cm.z;
        _offset_valid   = true;

        // Ensure _update_destination() fires on the very next tick
        _last_update_neu_cm = _pending_cmd_neu_cm +
                              Vector3f(TETHER_GUIDED_UPDATE_DIST_CM + 1.0f, 0, 0);

        gcs().send_text(MAV_SEVERITY_INFO,
                        "TetherGuided: offset captured %.1f,%.1f m",
                        (double)(_offset_ne_cm.x * 0.01f),
                        (double)(_offset_ne_cm.y * 0.01f));
    } else {
        _offset_valid = false;
        gcs().send_text(MAV_SEVERITY_WARNING,
                        "TetherGuided: no beacon — flying to absolute position");
    }
}

// -----------------------------------------------------------------------
// _update_destination — PosVelAccel with beacon velocity feedforward.
// Called every run() tick so the position controller always has an up-to-date
// target and a velocity term that prevents it decelerating to a stop.
// A fence check gates the update so the vehicle respects geofences.
void ModeTetherGuided::_update_destination()
{
    if (!g2.tether.is_healthy()) {
        return;
    }

    Location beacon_loc;
    Vector3f beacon_neu_cm;
    if (!g2.tether.get_position(beacon_loc) ||
        !beacon_loc.get_vector_from_origin_NEU(beacon_neu_cm)) {
        return;
    }

    // Target position: beacon + captured NE offset, original altitude
    const Vector3f new_target_neu_cm(
        beacon_neu_cm.x + _offset_ne_cm.x,
        beacon_neu_cm.y + _offset_ne_cm.y,
        _target_alt_cm);

    // Gate: suppress updates when the target hasn't moved enough
    if ((new_target_neu_cm - _last_update_neu_cm).length_squared() <
            sq(TETHER_GUIDED_UPDATE_DIST_CM)) {
        return;
    }

#if AP_FENCE_ENABLED
    // Respect geofences: if the target is outside the fence, don't update.
    // The vehicle will hold the last valid target until the beacon moves
    // back into a position whose offset is within the fence.
    if (copter.fence.enabled()) {
        const Location target_loc(new_target_neu_cm.tofloat(),
                                  Location::AltFrame::ABOVE_ORIGIN);
        if (!copter.fence.check_destination_within_fence(target_loc)) {
            return;
        }
    }
#endif

    // Beacon velocity feedforward: NED m/s → NE cm/s (ignore vertical)
    Vector3f beacon_vel_ned;
    g2.tether.get_velocity_ned(beacon_vel_ned);
    const Vector3f vel_feedforward(
         beacon_vel_ned.x * 100.0f,
         beacon_vel_ned.y * 100.0f,
         0.0f);

    set_destination_posvel(new_target_neu_cm, vel_feedforward,
                           false, 0.0f, false, 0.0f, false);
    _last_update_neu_cm = new_target_neu_cm;
}

#endif  // MODE_TETHER_GUIDED_ENABLED
