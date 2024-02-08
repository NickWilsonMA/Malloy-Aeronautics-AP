 -- Motor ramp test 
-- SCR_USER1 = pwm_min 1100 pwm                
-- SCR_USER2 = pwm_max 1300 pwm                
-- SCR_USER3 = climb_rate 1100 pwm/s     
-- SCR_USER4 = time at pwm_max 0 (ms)       
-- SCR_HEAP_SIZE = script_mem 600000                   
-- RC8_OPTION = 300     -- set CH8 on RC      
-- RC?_OPTION = 31      -- set emeregency motor stop      
-- script only starts if the script switch is high and Estops are low

local frequency = 10  -- loop sleep in ms actually
gcs:send_text(1, string.format("MOTOR_PWM_RAMP_SCRIPT: ACTIVE! NOT FOR FLIGHT!"))
gcs:send_text(5, string.format("Set SCR_USER1 (pwm_min), SCR_USER2 (pwm_max) and SCR_USER3 (climb rate)"))
local pwm_min = assert(param:get("SCR_USER1"),"Script: Could not read SCR_USER1")
local pwm_max = assert(param:get("SCR_USER2"),"Script: Could not read SCR_USER2")
local rate = assert(param:get("SCR_USER3"),"Script: Set SCR_USER3 param - pwm change rate")
local delay = assert(param:get("SCR_USER4"),"Script: Set SCR_USER4 param - t at pwm_max (ms)")
local switch = assert(rc:find_channel_for_option(300),"Script: Could not find RC switch")
local e_stop = assert(rc:find_channel_for_option(31),"Script: Could not find motor emergency stop")
local start_time = 0
local timeout = 100 --frequency*15
local ramp_T = (2*(pwm_max-pwm_min) / rate) *1000 -- ms


function wait_for_arm()
  -- gcs:send_text( 1 ,  string.format("channel value: " .. switch:get_aux_switch_pos()))
  if ramp_T == 0.0 or pwm_min == 0.0 or pwm_max == 0.0 then -- do not check for SCR_USER4
    pwm_min = assert(param:get("SCR_USER1"),"Script: Could not read SCR_USER1")
    pwm_max = assert(param:get("SCR_USER2"),"Script: Could not read SCR_USER2")
    rate = assert(param:get("SCR_USER3"),"Script: Set ramp-up time in ms on param: SCR_USER3")
    delay = assert(param:get("SCR_USER4"),"Script: Set SCR_USER4 param - t at pwm_max (ms)")
    return wait_for_arm, 100*frequency
  elseif (switch:get_aux_switch_pos() ~= 2) or (e_stop:get_aux_switch_pos() ~= 0) then
    return wait_for_arm, 100*frequency -- rerun until armed
  else
    pwm_min = assert(param:get("SCR_USER1"),"Script: Could not read SCR_USER1")
    pwm_max = assert(param:get("SCR_USER2"),"Script: Could not read SCR_USER2")
    rate = assert(param:get("SCR_USER3"),"Script: Set ramp-up time in ms on param: SCR_USER3")
    delay = assert(param:get("SCR_USER4"),"Script: Set SCR_USER4 param - t at pwm_max (ms)")
    gcs:send_text( 4 ,  string.format("T = " .. (ramp_T+delay)/1000 .. ' seconds'))
    gcs:send_text( 4 ,  "SWITCH ENGAGED - Starting in 3 sec")
    return reset_timer, 1000
  end
end

function reset_timer()
  start_time = millis():tofloat()
  return motor_control, frequency
end

function motor_control()
  local time = millis():tofloat() - start_time
  local func = 0
  if time <= ramp_T/2 then
    func = math.abs( ( (time + ramp_T/2) % ramp_T) - ramp_T/2 ) / (ramp_T/2)
  elseif (time > ramp_T/2) and (time < ramp_T/2 + delay) then
    func = 1
  else
    func = math.abs( ( (time - delay + ramp_T/2) % ramp_T) - ramp_T/2 ) / (ramp_T/2)
  end

  output = math.floor( pwm_min + (func * (pwm_max-pwm_min)) ) -- remap to PWM range

  SRV_Channels:set_output_pwm_chan_timeout(0, output, timeout)
  SRV_Channels:set_output_pwm_chan_timeout(1, output, timeout)
  SRV_Channels:set_output_pwm_chan_timeout(2, output, timeout)
  SRV_Channels:set_output_pwm_chan_timeout(3, output, timeout)
  SRV_Channels:set_output_pwm_chan_timeout(4, output, timeout)
  SRV_Channels:set_output_pwm_chan_timeout(5, output, timeout)
  SRV_Channels:set_output_pwm_chan_timeout(6, output, timeout)
  SRV_Channels:set_output_pwm_chan_timeout(7, output, timeout)

  if (switch:get_aux_switch_pos() ~= 2) or (time >= ramp_T + delay) or (e_stop:get_aux_switch_pos() ~= 0) then
    SRV_Channels:set_output_pwm_chan_timeout(0, pwm_min, timeout)
    SRV_Channels:set_output_pwm_chan_timeout(1, pwm_min, timeout)
    SRV_Channels:set_output_pwm_chan_timeout(2, pwm_min, timeout)
    SRV_Channels:set_output_pwm_chan_timeout(3, pwm_min, timeout)
    SRV_Channels:set_output_pwm_chan_timeout(4, pwm_min, timeout)
    SRV_Channels:set_output_pwm_chan_timeout(5, pwm_min, timeout)
    SRV_Channels:set_output_pwm_chan_timeout(6, pwm_min, timeout)
    SRV_Channels:set_output_pwm_chan_timeout(7, pwm_min, timeout)
    interrupt_time = 0.0
    return wait_for_arm, 4000 -- return to wait
  end
  return motor_control, frequency -- reschedule
end

return wait_for_arm, 1000 -- start by waiting for arm state aftr 1s delay