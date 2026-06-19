#include "AP_PIDTuneMonitor.h"

#include <GCS_MAVLink/GCS.h>

AP_PIDTuneMonitor *AP_PIDTuneMonitor::_singleton;

const AP_Param::GroupInfo AP_PIDTuneMonitor::var_info[] = {
    // @Param: ENABLE
    // @DisplayName: PID tune monitor enable
    // @Description: Enables logging of PID integrator events (reset, relax, set, limit). Log message PTUN.
    // @Values: 0:Disabled,1:Log events,2:Log and GCS notify on I reset/relax
    // @User: Advanced
    AP_GROUPINFO("ENABLE", 1, AP_PIDTuneMonitor, _enable, 1),

    // @Param: GCS
    // @DisplayName: PID tune monitor GCS rate limit
    // @Description: Minimum seconds between GCS text messages for integrator events when ENABLE=2
    // @Range: 0 10
    // @Units: s
    // @User: Advanced
    AP_GROUPINFO("GCS", 2, AP_PIDTuneMonitor, _gcs_notify, 1),

    AP_GROUPEND
};

AP_PIDTuneMonitor::AP_PIDTuneMonitor()
{
    if (_singleton != nullptr) {
        AP_HAL::panic("AP_PIDTuneMonitor must be singleton");
    }
    _singleton = this;
    AP_Param::setup_object_defaults(this, var_info);
}

void AP_PIDTuneMonitor::register_controller(Controller id, const char *name)
{
    if (_registry_count >= MAX_CONTROLLERS) {
        return;
    }
    for (uint8_t i = 0; i < _registry_count; i++) {
        if (_registry[i].id == id) {
            _registry[i].name = name;
            return;
        }
    }
    _registry[_registry_count].id = id;
    _registry[_registry_count].name = name;
    _registry_count++;
}

const char *AP_PIDTuneMonitor::controller_name(Controller id) const
{
    for (uint8_t i = 0; i < _registry_count; i++) {
        if (_registry[i].id == id) {
            return _registry[i].name;
        }
    }
    return "?";
}

void AP_PIDTuneMonitor::write_log(Controller id, Event ev, float i_before, float i_after, float error, bool limit)
{
    if (_enable <= 0) {
        return;
    }
    AP_Logger &logger = AP::logger();
    if (!logger.logging_enabled()) {
        return;
    }
    logger.Write_PTUN(uint8_t(id), uint8_t(ev), limit ? 1 : 0, i_before, i_after, error);
}

void AP_PIDTuneMonitor::maybe_gcs_notify(Controller id, Event ev, float i_before, float i_after)
{
    if (_enable < 2) {
        return;
    }
    if (ev != RESET_I && ev != RELAX_I && ev != SET_I) {
        return;
    }
    const uint32_t now = AP_HAL::millis();
    const uint32_t interval_ms = uint32_t(_gcs_notify.get()) * 1000U;
    if (interval_ms > 0 && (now - _last_gcs_ms) < interval_ms) {
        return;
    }
    _last_gcs_ms = now;

    const char *ev_name = (ev == RESET_I) ? "RST" : (ev == RELAX_I) ? "RLX" : "SET";
    GCS_SEND_TEXT(MAV_SEVERITY_INFO, "PTUN %s %s I %.1f->%.1f",
                  controller_name(id), ev_name, (double)i_before, (double)i_after);
}

void AP_PIDTuneMonitor::record_event(Controller id, Event ev, float i_before, float i_after, float error, bool limit)
{
    if (_enable <= 0) {
        return;
    }

    _event_count_window++;
    write_log(id, ev, i_before, i_after, error, limit);
    maybe_gcs_notify(id, ev, i_before, i_after);
}

void AP_PIDTuneMonitor::update()
{
    if (_enable <= 0) {
        return;
    }
    const uint32_t now = AP_HAL::millis();
    if (now - _last_summary_ms < 5000U) {
        return;
    }
    if (_event_count_window == 0) {
        _last_summary_ms = now;
        return;
    }
    if (_enable >= 2) {
        GCS_SEND_TEXT(MAV_SEVERITY_INFO, "PTUN: %u integrator events/5s", (unsigned)_event_count_window);
    }
    _event_count_window = 0;
    _last_summary_ms = now;
}

namespace AP {
AP_PIDTuneMonitor &pid_tune_monitor()
{
    return *AP_PIDTuneMonitor::get_singleton();
}
}
