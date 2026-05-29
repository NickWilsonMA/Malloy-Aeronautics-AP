#include "Copter.h"

#if MODE_TETHER_LOITER_ENABLED == ENABLED

/*
 * TetherLoiter — thin wrapper around ModeLoiter.
 *
 * Tether velocity tracking is now integrated directly into ModeLoiter::run()
 * and activated via TETH_ENABLE (or the TETHER_ENABLE RC aux switch).
 * This class exists for backwards compatibility with GCS flight-mode numbers.
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
    // All tether logic is now in ModeLoiter::run().
    ModeLoiter::run();
}

#endif  // MODE_TETHER_LOITER_ENABLED
