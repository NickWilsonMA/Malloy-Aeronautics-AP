#pragma once

#include <AP_HAL/AP_HAL.h>
#include <AP_Param/AP_Param.h>
#include <AP_Logger/AP_Logger.h>

// PID integrator / tuning monitor for live tuning and post-flight .bin review.
// Enabled on tuning firmware builds (ArduCopter define AP_PID_TUNE_MONITOR_ENABLED).

class AP_PIDTuneMonitor {
public:
    AP_PIDTuneMonitor();

    CLASS_NO_COPY(AP_PIDTuneMonitor);

    static AP_PIDTuneMonitor *get_singleton() { return _singleton; }

    enum Controller : uint8_t {
        RAT_RLL = 1,
        RAT_PIT = 2,
        RAT_YAW = 3,
        ACCZ    = 4,
        VELZ    = 5,
        VELX    = 6,
        VELY    = 7,
    };

    enum Event : uint8_t {
        RESET_I  = 1,
        RELAX_I  = 2,
        SET_I    = 3,
        LIMIT_ON = 4,
    };

    void register_controller(Controller id, const char *name);

    void record_event(Controller id, Event ev, float i_before, float i_after, float error, bool limit);

    void update();

    static const struct AP_Param::GroupInfo var_info[];

private:
    static AP_PIDTuneMonitor *_singleton;

    AP_Int8 _enable;
    AP_Int8 _gcs_notify;

    struct RegEntry {
        Controller id;
        const char *name;
    };
    static constexpr uint8_t MAX_CONTROLLERS = 8;
    RegEntry _registry[MAX_CONTROLLERS];
    uint8_t _registry_count;

    uint32_t _event_count_window;
    uint32_t _last_summary_ms;
    uint32_t _last_gcs_ms;

    const char *controller_name(Controller id) const;
    void write_log(Controller id, Event ev, float i_before, float i_after, float error, bool limit);
    void maybe_gcs_notify(Controller id, Event ev, float i_before, float i_after);
};

namespace AP {
AP_PIDTuneMonitor &pid_tune_monitor();
}
