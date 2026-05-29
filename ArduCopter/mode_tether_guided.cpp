#include "Copter.h"

#if MODE_TETHER_GUIDED_ENABLED == ENABLED

/*
 * TetherGuided — thin wrapper around ModeGuided.
 *
 * Tether offset tracking is now integrated directly into ModeGuided
 * (set_destination, run, and the _tether_* helpers) and activated via
 * TETH_ENABLE (or the TETHER_ENABLE RC aux switch).
 * This class exists for backwards compatibility with GCS flight-mode numbers.
 */

bool ModeTetherGuided::init(bool ignore_checks)
{
    if (!g2.tether.enabled()) {
        gcs().send_text(MAV_SEVERITY_WARNING, "TetherGuided: set TETH_ENABLE=1");
        return false;
    }
    return ModeGuided::init(ignore_checks);
}

// set_destination and run are fully handled by the ModeGuided base class.

#endif  // MODE_TETHER_GUIDED_ENABLED
