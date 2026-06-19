# PID tuning monitor firmware

Branch: `feature/pid-tuning-monitor`

## Purpose

Lightweight **integrator event telemetry** for PID tuning: logs when I-terms are
reset, relaxed, or explicitly set, with before/after values and error at the event.

## Parameters

| Param | Default | Meaning |
|-------|---------|---------|
| `PTUN_ENABLE` | 1 | 0=off, 1=log PTUN to .bin, 2=log + GCS text on I events |
| `PTUN_GCS` | 1 | Min seconds between GCS notify messages (when ENABLE=2) |

## Log message: PTUN

| Field | Meaning |
|-------|---------|
| Ctrl | 1=RAT_RLL, 2=RAT_PIT, 3=RAT_YAW, 4=ACCZ, 5=VELZ, 6=VELX, 7=VELY |
| Ev | 1=RESET_I, 2=RELAX_I, 3=SET_I |
| IBef / IAft | Integrator before and after event |
| Err | PID error at event |
| Limit | 1 if output was saturated (anti-windup active) |

Plot PTUN in Mission Planner alongside PIDR/PIDP/PIDA and PSCN/PSCD.

## Recommended LOG_BITMASK for tuning flights

Enable at minimum:

- **PID** (bit 12) — PIDR, PIDP, PIDY, PIDA, PIDN, PIDE
- **CTUN** (bit 4) — throttle in/out, angle boost
- **NTUN** (bit 5) — navigation tuning
- **ATTITUDE_FAST** (bit 0) — RATE, ATT at loop rate
- **RCOUT** (bit 10) — motor PWM

## What to monitor during PID tuning (checklist)

### Integrator health
- **PTUN events** — unexpected RESET/RELAX/SET during flight (spool, land, mode change)
- **PID*.I** vs **PID*.Err** — I building while saturated (`Limit=1`)
- **I jumps** in PTUN (IBef → IAft) at takeoff, mode changes, EKF resets

### Rate loops (ATC_RAT_*)
- **RATE.R**, **RATE.P**, **RATE.Y** — target vs actual body rates
- **PIDR/PIDP/PIDY** — P, I, D, FF, Dmod, Limit
- Oscillation: high **D** or **P** with growing **I**

### Attitude / angle (ATC_ANG_*)
- **ATT.Roll/Pitch/Yaw** vs **DesRoll/DesPitch/DesYaw**
- Thrust vector error before yaw correction kicks in

### Vertical (PSC_* / PIDA)
- **PSCD** — pos, vel, accel targets vs achieved
- **PIDA** — accel-Z PID (throttle path)
- **CTUN.ThO**, **CTUN.ThIn**, **CTUN.DAlt**
- **land_complete** transitions vs PTUN on ACCZ/VELZ

### Horizontal (PIDN/PIDE, PSCN/PSCE)
- **PSCN/PSCE** — position/velocity/accel NE
- **PIDN/PIDE** — XY velocity loop I and limit flags
- Crosstrack during WP/Loiter

### Actuator / plant
- **RCOU** — PWM saturation, asymmetry across motors
- **MOTB** — throttle average max, limiting
- **VIBE** — noise driving D and false I buildup

### State / gating (explains I resets)
- **MODE**, **EV** — mode changes
- **ARM** — arm/disarm
- Motor spool: **RCOU** flat periods + **PTUN** RELAX on ACCZ at takeoff

### Environment
- **BARO/GPS/RFND** — altitude source steps
- **EKF** status / **NKF*/XKF*** innovations — EKF resets → pos I re-init

## Future extensions (not yet implemented)

- Log **LIMIT_ON** edge events every frame saturation toggles
- Hook **AC_AttitudeControl** rate I reset_smoothly
- **init_z_controller** / **relax_z_controller** high-level events
- MAVLink **NAMED_VALUE_FLOAT** stream for live GCS panels
- AutoTune / System ID correlation tags on PTUN
