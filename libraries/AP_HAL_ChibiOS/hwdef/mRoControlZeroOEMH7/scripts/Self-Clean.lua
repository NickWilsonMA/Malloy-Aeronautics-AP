local completed_mission_clear = false
local completed_set_home = false
local current_location
function self_clean()
    gcs:send_text(2, string.format("Location Scrubber: Started."))
    completed_mission_clear = mission:clear()
    if ahrs:home_is_set()
    then
        current_location = ahrs:get_location()
        completed_set_home = ahrs:set_home(current_location)
    elseif not ahrs:home_is_set()
        then
            completed_set_home = true
    end
    if completed_mission_clear
    then
        if completed_set_home
        then
            gcs:send_text(2, string.format("Location Scrubber: Complete."))
        end
    end
end
return self_clean()