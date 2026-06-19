#include "Copter.h"

#if AP_PID_TUNE_MONITOR_ENABLED

void Copter::pid_tune_monitor_setup()
{
    using ID = AP_PIDTuneMonitor::Controller;

    g2.pid_tune_monitor.register_controller(ID::RAT_RLL, "RAT_RLL");
    g2.pid_tune_monitor.register_controller(ID::RAT_PIT, "RAT_PIT");
    g2.pid_tune_monitor.register_controller(ID::RAT_YAW, "RAT_YAW");
    g2.pid_tune_monitor.register_controller(ID::ACCZ, "ACCZ");
    g2.pid_tune_monitor.register_controller(ID::VELZ, "VELZ");
    g2.pid_tune_monitor.register_controller(ID::VELX, "VELX");
    g2.pid_tune_monitor.register_controller(ID::VELY, "VELY");

    attitude_control->get_rate_roll_pid().set_tune_monitor_id(uint8_t(ID::RAT_RLL));
    attitude_control->get_rate_pitch_pid().set_tune_monitor_id(uint8_t(ID::RAT_PIT));
    attitude_control->get_rate_yaw_pid().set_tune_monitor_id(uint8_t(ID::RAT_YAW));
    pos_control->get_accel_z_pid().set_tune_monitor_id(uint8_t(ID::ACCZ));
    pos_control->get_vel_z_pid().set_tune_monitor_id(uint8_t(ID::VELZ));
    pos_control->get_vel_xy_pid().set_tune_monitor_ids(uint8_t(ID::VELX), uint8_t(ID::VELY));
}

void Copter::pid_tune_monitor_update()
{
    g2.pid_tune_monitor.update();
}

#endif
