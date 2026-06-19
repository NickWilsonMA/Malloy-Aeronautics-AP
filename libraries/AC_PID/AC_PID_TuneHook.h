#pragma once

#include <AP_PIDTuneMonitor/AP_PIDTuneMonitor_config.h>

#if AP_PID_TUNE_MONITOR_ENABLED
#include <AP_PIDTuneMonitor/AP_PIDTuneMonitor.h>

enum ac_pid_tune_event : uint8_t {
    AC_PID_TUNE_RESET_I = AP_PIDTuneMonitor::RESET_I,
    AC_PID_TUNE_RELAX_I = AP_PIDTuneMonitor::RELAX_I,
    AC_PID_TUNE_SET_I = AP_PIDTuneMonitor::SET_I,
};

inline void ac_pid_tune_hook(uint8_t id, ac_pid_tune_event ev, float i_before, float i_after, float error, bool limit)
{
    if (id == 0) {
        return;
    }
    AP_PIDTuneMonitor *mon = AP_PIDTuneMonitor::get_singleton();
    if (mon == nullptr) {
        return;
    }
    mon->record_event(AP_PIDTuneMonitor::Controller(id), AP_PIDTuneMonitor::Event(ev), i_before, i_after, error, limit);
}
#else
enum ac_pid_tune_event : uint8_t {
    AC_PID_TUNE_RESET_I = 1,
    AC_PID_TUNE_RELAX_I = 2,
    AC_PID_TUNE_SET_I = 3,
};
inline void ac_pid_tune_hook(uint8_t, ac_pid_tune_event, float, float, float, bool) {}
#endif
