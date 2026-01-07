#pragma once

#ifndef FORCE_VERSION_H_INCLUDE
#error version.h should never be included directly. You probably want to include AP_Common/AP_FWVersion.h
#endif

#include "ap_version.h"



<<<<<<< HEAD
<<<<<<< HEAD
#define THISFIRMWARE "MA_COPTER-V4.3.0.12-DEV-I2C"
=======
#define THISFIRMWARE "MA_Copter-V4.3.0.11_DEV_RTLACCEL"
>>>>>>> [NHW] Add RTL_ACCEL param
=======
#define THISFIRMWARE "MA_Copter-V4.3.0.12_DEV.2"
>>>>>>> [NHW] Update version number to reflect multiple Dev changes.

// the following line is parsed by the autotest scripts
#define FIRMWARE_VERSION 4,3,0,FIRMWARE_VERSION_TYPE_OFFICIAL

#define FW_MAJOR 4
#define FW_MINOR 3
#define FW_PATCH 0
#define FW_TYPE FIRMWARE_VERSION_TYPE_OFFICIAL

#include <AP_Common/AP_FWVersionDefine.h>