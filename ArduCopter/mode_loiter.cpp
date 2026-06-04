#include "Copter.h"

#if MODE_LOITER_ENABLED == ENABLED

/*
 * Init and run calls for loiter flight mode
 */

// loiter_init - initialise loiter controller
bool ModeLoiter::init(bool ignore_checks)
{
    if (!copter.failsafe.radio) {
        float target_roll, target_pitch;
        // apply SIMPLE mode transform to pilot inputs
        update_simple_mode();

        // convert pilot input to lean angles
        get_pilot_desired_lean_angles(target_roll, target_pitch, loiter_nav->get_angle_max_cd(), attitude_control->get_althold_lean_angle_max_cd());

        // process pilot's roll and pitch input
        loiter_nav->set_pilot_desired_acceleration(target_roll, target_pitch);
    } else {
        // clear out pilot desired acceleration in case radio failsafe event occurs and we do not switch to RTL for some reason
        loiter_nav->clear_pilot_desired_acceleration();
    }
    loiter_nav->init_target();

#if MODE_TETHER_LOITER_ENABLED == ENABLED
    _tether.offset_valid       = false;
    _tether.heading_offset_deg = 0.0f;
    _tether.active_sysid       = 0;
    if (g2.tether.enabled()) {
        Location beacon_loc;
        Vector3f beacon_neu_cm;
        float beacon_hdg_deg;
        if (g2.tether.is_healthy() &&
            g2.tether.get_position(beacon_loc) &&
            beacon_loc.get_vector_from_origin_NEU(beacon_neu_cm) &&
            g2.tether.get_heading_deg(beacon_hdg_deg)) {
            const Vector3f &drone_neu_cm = copter.inertial_nav.get_position_neu_cm();
            const float ne_n = drone_neu_cm.x - beacon_neu_cm.x;
            const float ne_e = drone_neu_cm.y - beacon_neu_cm.y;
            const float h_bcn = radians(beacon_hdg_deg);
            _tether.offset_fwd_cm      =  ne_n * cosf(h_bcn) + ne_e * sinf(h_bcn);
            _tether.offset_right_cm    = -ne_n * sinf(h_bcn) + ne_e * cosf(h_bcn);
            _tether.heading_offset_deg = wrap_180(ahrs.yaw_sensor * 0.01f - beacon_hdg_deg);
            _tether.active_sysid       = g2.tether.get_target_sysid();
            _tether.offset_valid       = true;
        }
    }
#endif

    // initialise the vertical position controller
    if (!pos_control->is_active_z()) {
        pos_control->init_z_controller();
    }

    // set vertical speed and acceleration limits
    pos_control->set_max_speed_accel_z(-get_pilot_speed_dn(), g.pilot_speed_up, g.pilot_accel_z);
    pos_control->set_correction_speed_accel_z(-get_pilot_speed_dn(), g.pilot_speed_up, g.pilot_accel_z);

#if PRECISION_LANDING == ENABLED
    _precision_loiter_active = false;
#endif

    return true;
}

#if PRECISION_LANDING == ENABLED
bool ModeLoiter::do_precision_loiter()
{
    if (!_precision_loiter_enabled) {
        return false;
    }
    if (copter.ap.land_complete_maybe) {
        return false;        // don't move on the ground
    }
    // if the pilot *really* wants to move the vehicle, let them....
    if (loiter_nav->get_pilot_desired_acceleration().length() > 50.0f) {
        return false;
    }
    if (!copter.precland.target_acquired()) {
        return false; // we don't have a good vector
    }
    return true;
}

void ModeLoiter::precision_loiter_xy()
{
    loiter_nav->clear_pilot_desired_acceleration();
    Vector2f target_pos, target_vel;
    if (!copter.precland.get_target_position_cm(target_pos)) {
        target_pos = inertial_nav.get_position_xy_cm();
    }
    // get the velocity of the target
    copter.precland.get_target_velocity_cms(inertial_nav.get_velocity_xy_cms(), target_vel);

    Vector2f zero;
    Vector2p landing_pos = target_pos.topostype();
    // target vel will remain zero if landing target is stationary
    pos_control->input_pos_vel_accel_xy(landing_pos, target_vel, zero);
    // run pos controller
    pos_control->update_xy_controller();
}
#endif

// loiter_run - runs the loiter controller
// should be called at 100hz or more
void ModeLoiter::run()
{
    float target_roll = 0.0f, target_pitch = 0.0f;
    float target_yaw_rate = 0.0f;
    float target_climb_rate = 0.0f;

    // set vertical speed and acceleration limits
    pos_control->set_max_speed_accel_z(-get_pilot_speed_dn(), g.pilot_speed_up, g.pilot_accel_z);

    // process pilot inputs unless we are in radio failsafe
    if (!copter.failsafe.radio) {
        // apply SIMPLE mode transform to pilot inputs
        update_simple_mode();

        // convert pilot input to lean angles
        get_pilot_desired_lean_angles(target_roll, target_pitch, loiter_nav->get_angle_max_cd(), attitude_control->get_althold_lean_angle_max_cd());

        // process pilot's roll and pitch input
        loiter_nav->set_pilot_desired_acceleration(target_roll, target_pitch);

        // get pilot's desired yaw rate
        target_yaw_rate = get_pilot_desired_yaw_rate(channel_yaw->norm_input_dz());

        // get pilot desired climb rate
        target_climb_rate = get_pilot_desired_climb_rate(channel_throttle->get_control_in());
        target_climb_rate = constrain_float(target_climb_rate, -get_pilot_speed_dn(), g.pilot_speed_up);
    } else {
        // clear out pilot desired acceleration in case radio failsafe event occurs and we do not switch to RTL for some reason
        loiter_nav->clear_pilot_desired_acceleration();
    }

    // relax loiter target if we might be landed
    if (copter.ap.land_complete_maybe) {
        loiter_nav->soften_for_landing();
    }

    // Loiter State Machine Determination
    AltHoldModeState loiter_state = get_alt_hold_state(target_climb_rate);

    // Loiter State Machine
    switch (loiter_state) {

    case AltHold_MotorStopped:
        attitude_control->reset_rate_controller_I_terms();
        attitude_control->reset_yaw_target_and_rate();
        pos_control->relax_z_controller(0.0f);   // forces throttle output to decay to zero
        loiter_nav->init_target();
        attitude_control->input_thrust_vector_rate_heading(loiter_nav->get_thrust_vector(), target_yaw_rate, false);
        break;

    case AltHold_Takeoff:
        // initiate take-off
        if (!takeoff.running()) {
            takeoff.start(constrain_float(g.pilot_takeoff_alt,0.0f,1000.0f));
        }

        // get avoidance adjusted climb rate
        target_climb_rate = get_avoidance_adjusted_climbrate(target_climb_rate);

        // set position controller targets adjusted for pilot input
        takeoff.do_pilot_takeoff(target_climb_rate);

        // run loiter controller
        loiter_nav->update();

        // call attitude controller
        attitude_control->input_thrust_vector_rate_heading(loiter_nav->get_thrust_vector(), target_yaw_rate, false);
        break;

    case AltHold_Landed_Ground_Idle:
        attitude_control->reset_yaw_target_and_rate();
        FALLTHROUGH;

    case AltHold_Landed_Pre_Takeoff:
        attitude_control->reset_rate_controller_I_terms_smoothly();
        loiter_nav->init_target();
        attitude_control->input_thrust_vector_rate_heading(loiter_nav->get_thrust_vector(), target_yaw_rate, false);
        pos_control->relax_z_controller(0.0f);   // forces throttle output to decay to zero
        break;

    case AltHold_Flying:
        // set motors to full range
        motors->set_desired_spool_state(AP_Motors::DesiredSpoolState::THROTTLE_UNLIMITED);

        bool tether_yaw_active = false;
        float tether_desired_heading_cd = 0.0f;
#if MODE_TETHER_LOITER_ENABLED == ENABLED
        if (g2.tether.enabled()) {
            // If TETH_BCN_SYSID changed since the offset was captured, drop the old offset.
            // The lazy capture below will immediately re-capture from the aircraft's current
            // position relative to the new beacon.
            if (_tether.offset_valid &&
                g2.tether.get_target_sysid() != _tether.active_sysid) {
                _tether.offset_valid = false;
                gcs().send_text(MAV_SEVERITY_INFO,
                                "TetherLoiter: beacon sysid changed - reacquiring offset");
            }

            // Lazy offset capture in beacon track frame
            if (!_tether.offset_valid) {
                Location bcn_loc;
                Vector3f bcn_neu_cm;
                float bcn_hdg_deg;
                if (g2.tether.is_healthy() &&
                    g2.tether.get_position(bcn_loc) &&
                    bcn_loc.get_vector_from_origin_NEU(bcn_neu_cm) &&
                    g2.tether.get_heading_deg(bcn_hdg_deg)) {
                    const Vector3f &drone_neu = copter.inertial_nav.get_position_neu_cm();
                    const float ne_n = drone_neu.x - bcn_neu_cm.x;
                    const float ne_e = drone_neu.y - bcn_neu_cm.y;
                    const float h_b = radians(bcn_hdg_deg);
                    _tether.offset_fwd_cm      =  ne_n * cosf(h_b) + ne_e * sinf(h_b);
                    _tether.offset_right_cm    = -ne_n * sinf(h_b) + ne_e * cosf(h_b);
                    _tether.heading_offset_deg = wrap_180(ahrs.yaw_sensor * 0.01f - bcn_hdg_deg);
                    _tether.active_sysid       = g2.tether.get_target_sysid();
                    _tether.offset_valid       = true;
                }
            }

            if (_tether.offset_valid) {
                if (!g2.tether.is_healthy()) {
                    _tether.offset_valid = false;
                    gcs().send_text(MAV_SEVERITY_WARNING, "TetherLoiter: beacon lost");
                } else {
                    Location beacon_loc;
                    Vector3f beacon_neu_cm;
                    Vector3f beacon_vel_ned;
                    float beacon_hdg_deg;
                    if (g2.tether.get_position(beacon_loc) &&
                        beacon_loc.get_vector_from_origin_NEU(beacon_neu_cm) &&
                        g2.tether.get_velocity_ned(beacon_vel_ned) &&
                        g2.tether.get_heading_deg(beacon_hdg_deg)) {

                        const float h_bcn = radians(beacon_hdg_deg);
                        const float cos_h = cosf(h_bcn);
                        const float sin_h = sinf(h_bcn);

                        // Map pilot lean angles (aircraft frame) to offset velocity in beacon
                        // track frame.  Forward stick always moves the offset ahead of the
                        // beacon regardless of which direction the drone is pointing.
                        //   body→NE: fwd=(cos h_ac, sin h_ac), right=(-sin h_ac, cos h_ac)
                        //   NE→beacon: rotate by -h_bcn
                        //   Combined: body→beacon = rotate by (h_ac - h_bcn)
                        const float h_ac      = radians(ahrs.yaw_sensor * 0.01f);
                        const float angle_diff = h_ac - h_bcn;
                        const float cos_d     = cosf(angle_diff);
                        const float sin_d     = sinf(angle_diff);

                        const float angle_max_cd   = loiter_nav->get_angle_max_cd();
                        const float max_speed_cms  = wp_nav->get_default_speed_xy();
                        const float vel_fwd_body   = -target_pitch / angle_max_cd * max_speed_cms;
                        const float vel_right_body =  target_roll  / angle_max_cd * max_speed_cms;

                        _tether.offset_fwd_cm   += (vel_fwd_body * cos_d - vel_right_body * sin_d) * G_Dt;
                        _tether.offset_right_cm += (vel_fwd_body * sin_d + vel_right_body * cos_d) * G_Dt;

                        // Suppress loiter nav's own pilot-acceleration logic so it only
                        // holds the position target we set below.
                        loiter_nav->clear_pilot_desired_acceleration();

                        // Yaw stick: update heading offset while active, maintain it when neutral
                        if (!is_zero(target_yaw_rate)) {
                            _tether.heading_offset_deg = wrap_180(ahrs.yaw_sensor * 0.01f - beacon_hdg_deg);
                        } else {
                            tether_desired_heading_cd = wrap_360(beacon_hdg_deg + _tether.heading_offset_deg) * 100.0f;
                            tether_yaw_active = true;
                        }

                        // Position target: beacon + stored beacon-frame offset rotated to NE
                        const float desired_n = beacon_neu_cm.x
                                              + _tether.offset_fwd_cm * cos_h
                                              - _tether.offset_right_cm * sin_h;
                        const float desired_e = beacon_neu_cm.y
                                              + _tether.offset_fwd_cm * sin_h
                                              + _tether.offset_right_cm * cos_h;

                        const float beacon_speed_cms =
                            Vector2f(beacon_vel_ned.x, beacon_vel_ned.y).length() * 100.0f;
                        pos_control->set_correction_speed_accel_xy(
                            MAX(beacon_speed_cms * 1.5f, 200.0f),
                            pos_control->get_max_accel_xy_cmss());
                        pos_control->set_pos_target_xy_cm(desired_n, desired_e);
                    }
                }
            }
        }
#endif  // MODE_TETHER_LOITER_ENABLED

#if PRECISION_LANDING == ENABLED
        bool precision_loiter_old_state = _precision_loiter_active;
        if (do_precision_loiter()) {
            precision_loiter_xy();
            _precision_loiter_active = true;
        } else {
            _precision_loiter_active = false;
        }
        if (precision_loiter_old_state && !_precision_loiter_active) {
            // prec loiter was active, not any more, let's init again as user takes control
            loiter_nav->init_target();
        }
        // run loiter controller if we are not doing prec loiter
        if (!_precision_loiter_active) {
            loiter_nav->update();
        }
#else
        loiter_nav->update();
#endif

        // call attitude controller
#if MODE_TETHER_LOITER_ENABLED == ENABLED
        if (tether_yaw_active) {
            attitude_control->input_thrust_vector_heading(loiter_nav->get_thrust_vector(), tether_desired_heading_cd);
        } else
#endif
        {
            attitude_control->input_thrust_vector_rate_heading(loiter_nav->get_thrust_vector(), target_yaw_rate, false);
        }

        // get avoidance adjusted climb rate
        target_climb_rate = get_avoidance_adjusted_climbrate(target_climb_rate);

        // update the vertical offset based on the surface measurement
        copter.surface_tracking.update_surface_offset();

        // Send the commanded climb rate to the position controller
        pos_control->set_pos_target_z_from_climb_rate_cm(target_climb_rate);
        break;
    }

    // run the vertical position controller and set output throttle
    pos_control->update_z_controller();
}

uint32_t ModeLoiter::wp_distance() const
{
    return loiter_nav->get_distance_to_target();
}

int32_t ModeLoiter::wp_bearing() const
{
    return loiter_nav->get_bearing_to_target();
}

#endif
