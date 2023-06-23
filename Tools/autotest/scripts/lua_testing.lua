-- PHASE I: Motor Anomaly Detector - Vehicle Signature Logger based on GYRO - MG.
------------------------------------------------------------------------------------------------------------
-- Three different anomaly detection metrics => (SIG)
-- 1. gyro_sig_raw = gyrX * gyrY * gyrZ (gradients)
-- 2. gyro_sig_gain = (SIG_ROLL_GAIN * gyrX) * (SIG_PITCH_GAIN * gyrY) * (SIG_YAW_GAIN * gyrZ)
-- 3. gyro_sig_wAcc = gyro_sig_gain * 1/(1-(Kz|accelZ - g|/g)) (Impulse Rejection Factor)

--  SCR_USER1 PARAM to set the Threshold => 1 to 5
--  SCR_USER2 PARAM to enable or disable detection 
------------------------------------------------------------------------------------------------------------

local log_sig = {}
local sig1 = 1
local sig2 = 2
local sig3= 3

Interval = 10 --100hz
G = - 9.81

SIG_ROLL_GAIN = 0.5
SIG_PITCH_GAIN = 0.4
SIG_YAW_GAIN = 0.1

SIG_ACCEL_GAIN = 5

GyroX_prev = 0.0
GyroY_prev = 0.0
GyroZ_prev = 0.0

SIG_COEFF = assert(param:get("SCR_USER1"),"Script: Could not read param")
ANOM_ENABLE = assert(param:get("SCR_USER2"),"Script: Could not read param")

SIG_THR = (SIG_COEFF + 1) * 1e-5

function warning_to_gcs(msg)
	gcs:send_text(4, "[MA_Script] " .. msg)
end

function attention_to_gcs(msg)
	gcs:send_text(1, "[MA_Script] " .. msg)
end

local function write_to_dataflash()
    logger:write('SIG','gyro_sig_raw, gyro_sig_gain, gyro_sig_wAcc','fff','---','---', log_sig[sig1], log_sig[sig2], log_sig[sig3])
end

warning_to_gcs("ANOMALY LOGGER ACTIVE")

function calculate_signature()
    if not (ahrs == nil) then

        local rates = ahrs:get_gyro()
        local accels = ahrs:get_accel()

        if rates then
            local gyroX = rates:x()
            local gyroY = rates:y()
            local gyroZ = rates:z()

            local delta_gyroX = gyroX - GyroX_prev
            local delta_gyroY = gyroY - GyroY_prev
            local delta_gyroZ = gyroZ - GyroZ_prev

            local grad_gyroX = ((gyroX + delta_gyroX) - (gyroX-delta_gyroX)) / 2 * (delta_gyroX)
            local grad_gyroY = ((gyroY + delta_gyroY) - (gyroX-delta_gyroY)) / 2 * (delta_gyroY)
            local grad_gyroZ = ((gyroZ + delta_gyroZ) - (gyroX-delta_gyroZ)) / 2 * (delta_gyroZ)

            local accelZ = accels:z()
            local accelZ_N = 1 / (1 - (math.abs(accelZ - G) * SIG_ACCEL_GAIN / G))

            local gyro_sig_raw = math.abs(grad_gyroX * grad_gyroY * grad_gyroZ)
            local gyro_sig_gain = math.abs((SIG_ROLL_GAIN*grad_gyroX)*(SIG_PITCH_GAIN*grad_gyroY)*(SIG_YAW_GAIN*grad_gyroZ))
            local gyro_sig_wAcc = gyro_sig_gain * accelZ_N

            log_sig[sig1] = gyro_sig_raw
            log_sig[sig2] = gyro_sig_gain
            log_sig[sig3] = gyro_sig_wAcc

            SIG_COEFF = assert(param:get("SCR_USER1"),"Script: Could not read param")
            ANOM_ENABLE = assert(param:get("SCR_USER2"),"Script: Could not read param")
            SIG_THR = (SIG_COEFF + 1) * 1e-5

            if (gyro_sig_wAcc > SIG_THR) and ANOM_ENABLE == 1 then
                attention_to_gcs("MOTOR ANOMALY")
                SIG_COEFF = assert(param:get("SCR_USER1"),"Script: Could not read param")
                ANOM_ENABLE = assert(param:get("SCR_USER2"),"Script: Could not read param")
                SIG_THR = (SIG_COEFF + 1) * 1e-5
            end

            GyroX_prev = gyroX
            GyroY_prev = gyroY
            GyroZ_prev = gyroZ
        end
    else
        attention_to_gcs("ahrs was nil...")
    end
end

local cycle_count = 0

local function run_10Hz_loop()
    calculate_signature()
    write_to_dataflash()
end

function update()
    if (math.fmod(cycle_count, 10) == 0) then
        run_10Hz_loop()
    end
    cycle_count = cycle_count + 1
    if (cycle_count >= 100) then
		cycle_count = 0
	end
    return update, Interval
end

return update()