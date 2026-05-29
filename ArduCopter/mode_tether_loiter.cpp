#include "Copter.h"

#if MODE_TETHER_LOITER_ENABLED == ENABLED

/*
 * TetherLoiter flight mode
 *
 * Identical to Loiter in feel and stick response. The only addition is that
 * the loiter anchor (pos_control XY position target) is advanced each cycle
 * at the beacon's current velocity, so that centre-stick means zero velocity
 * relative to the beacon. A gentle position correction toward the beacon's
 * reported lat/lon prevents accumulated integration drift.
 *
 * When the beacon goes stale the mode degrades silently to plain Loiter —
 * the anchor stops moving and the vehicle holds its current position.
 *
 * Beacon data source: AP_Tether (g2.tether), fed by GLOBAL_POSITION_INT
 * messages filtered by TETH_SYSID.
 */

bool ModeTetherLoiter::init(bool ignore_checks)
{
    if (!g2.tether.enabled()) {
        gcs().send_text(MAV_SEVERITY_WARNING, "TetherLoiter: set TETH_ENABLE=1");
        return false;
    }
    return ModeLoiter::init(ignore_checks);
}

void ModeTetherLoiter::run()
{
    // Advance the loiter anchor at beacon velocity before the Loiter state
    // machine runs.  Only do this when airborne — on the ground the loiter
    // target is managed by init_target() / soften_for_landing() and should
    // not be disturbed.
    if (!copter.ap.land_complete_maybe) {
        Vector3f beacon_vel_ned;
        const bool beacon_ok = g2.tether.is_healthy() &&
                               g2.tether.get_velocity_ned(beacon_vel_ned);

        if (beacon_ok) {
            // beacon velocity is NED m/s; pos_control target is NEU cm.
            // NE components are the same (north = x, east = y); no sign flip needed.
            const float vn_cms = beacon_vel_ned.x * 100.0f;
            const float ve_cms = beacon_vel_ned.y * 100.0f;

            Vector3p pos = pos_control->get_pos_target_cm();

            // 1. Velocity advancement — move anchor at beacon speed
            pos.x += vn_cms * G_Dt;
            pos.y += ve_cms * G_Dt;

            // 2. Position correction — gentle pull toward beacon lat/lon to
            //    cancel long-term integration drift from velocity quantisation.
            //    The correction velocity is capped at TETHER_LOITER_CORR_MAX_CMS
            //    (0.5 m/s) so a large initial offset between the beacon and the
            //    vehicle does not cause a sudden high-speed dash and altitude
            //    loss.  Proportional factor (k=0.05) provides smooth convergence
            //    for small errors; the speed cap takes over for larger ones.
            static constexpr float TETHER_LOITER_CORR_MAX_CMS = 50.0f;  // 0.5 m/s
            Location beacon_loc;
            if (g2.tether.get_position(beacon_loc)) {
                Vector3f beacon_neu_cm;
                if (beacon_loc.get_vector_from_origin_NEU(beacon_neu_cm)) {
                    Vector2f err(beacon_neu_cm.x - (float)pos.x,
                                 beacon_neu_cm.y - (float)pos.y);
                    // Proportional step; cap at max speed * dt
                    const float max_step = TETHER_LOITER_CORR_MAX_CMS * G_Dt;
                    Vector2f step = err * 0.05f;
                    if (step.length() > max_step) {
                        step = step.normalized() * max_step;
                    }
                    pos.x += step.x;
                    pos.y += step.y;
                }
            }

            pos_control->set_pos_target_xy_cm((float)pos.x, (float)pos.y);
        }
    }

    // Run the standard Loiter state machine — pilot inputs, altitude,
    // attitude control, z controller all unchanged.
    ModeLoiter::run();
}

#endif  // MODE_TETHER_LOITER_ENABLED
