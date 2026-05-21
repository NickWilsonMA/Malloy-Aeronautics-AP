'''
OAfastWP Phase 1 autotests: SITL-01..23 regression (copter).

Mixed into AutoTestCopter via OAfastWPPhase1Mixin.
'''

from pymavlink import mavutil

from common import NotAchievedException, AutoTestTimeoutException


class OAfastWPPhase1Mixin(object):
    '''SITL-01..23 fastWP + Dijkstra regression (Phase 1 autotest).'''

    def testsOAfastWPPhase1(self):
        return [
            self.SITL_01_PolygonExclusionMission,
            self.SITL_02_CircleExclusionMission,
            self.SITL_03_MultipleExclusionMission,
            self.SITL_04_InclusionFenceMission,
            self.SITL_05_OverlappingExclusionMission,
            self.SITL_06_NarrowCorridorMission,
            self.SITL_07_NoValidPathMission,
            self.SITL_08_AddFenceDuringMission,
            self.SITL_09_ChangeFenceDuringMission,
            self.SITL_10_DeleteFenceDuringMission,
            self.SITL_11_EnableFenceInAir,
            self.SITL_12_DisableFenceInAir,
            self.SITL_13_FenceBreachRecovery,
            self.SITL_14_RTLBlockedPath,
            self.SITL_15_RTLToRallyBlockedPath,
            self.SITL_16_FastWaypointsDisabled,
            self.SITL_17_FastWaypointsEnabled,
            self.SITL_18_DenseWaypointsNearFence,
            self.SITL_19_WaypointsCloseToMargin,
            self.SITL_20_AltitudeGeofenceCeiling,
            self.SITL_21_AltitudeAndHorizontalFence,
            self.SITL_22_OAOptionsToggleInFlight,
            self.SITL_23_ThreePointDogleg,
        ]

    def _oafastwp_phase1_auto(self, fence_setup_fn, mission='mission-around-west.txt', final_wp=5,
                                  oa_options=4, extra_params=None, timeout=180):
        self.context_collect('STATUSTEXT')
        self.clear_fence()
        self.oafastwp_setup_dijkstra(oa_options=oa_options, extra_params=extra_params)
        fence_setup_fn()
        self.do_fence_enable()
        self.assert_fence_enabled()
        self.oafastwp_run_auto_mission(mission, final_wp, timeout=timeout)

    # --- SITL-01 .. SITL-07 ---

    def SITL_01_PolygonExclusionMission(self):
        '''SITL-01: AUTO mission routes around polygon exclusion.'''
        self.context_push()
        try:
            def fences():
                self.oafastwp_load_asset_fence_by_type(
                    'poly-exclusion-west.txt',
                    mavutil.mavlink.MAV_CMD_NAV_FENCE_POLYGON_VERTEX_EXCLUSION)
            self._oafastwp_phase1_auto(fences)
            self.oafastwp_assert_no_fence_breach()
        finally:
            self.context_pop()
            self.clear_fence()
            self.disarm_vehicle(force=True)

    def SITL_02_CircleExclusionMission(self):
        '''SITL-02: AUTO mission routes around circular exclusion.'''
        self.context_push()
        try:
            def fences():
                self.oafastwp_load_asset_fence_by_type(
                    'circle-exclusion-main.txt',
                    mavutil.mavlink.MAV_CMD_NAV_FENCE_CIRCLE_EXCLUSION,
                    circle_radius=self.OAFASTWP_EXCLUSION_RADIUS_M)
            self._oafastwp_phase1_auto(fences)
            self.oafastwp_assert_no_fence_breach()
        finally:
            self.context_pop()
            self.clear_fence()
            self.disarm_vehicle(force=True)

    def SITL_03_MultipleExclusionMission(self):
        '''SITL-03: AUTO through corridor between two exclusion circles.'''
        self.context_push()
        try:
            def fences():
                self.oafastwp_load_multiple_asset_fences([
                    {
                        'filename': 'circle-exclusion-north.txt',
                        'fence_type': mavutil.mavlink.MAV_CMD_NAV_FENCE_CIRCLE_EXCLUSION,
                        'circle_radius': 15,
                    },
                    {
                        'filename': 'circle-exclusion-south.txt',
                        'fence_type': mavutil.mavlink.MAV_CMD_NAV_FENCE_CIRCLE_EXCLUSION,
                        'circle_radius': 15,
                    },
                ])
            self._oafastwp_phase1_auto(fences)
            self.oafastwp_assert_no_fence_breach()
        finally:
            self.context_pop()
            self.clear_fence()
            self.disarm_vehicle(force=True)

    def SITL_04_InclusionFenceMission(self):
        '''SITL-04: mission inside inclusion fence.'''
        self.context_push()
        try:
            self.clear_fence()
            self.oafastwp_setup_dijkstra()
            self.oafastwp_load_asset_fence_by_type(
                'circle-inclusion-home.txt',
                mavutil.mavlink.MAV_CMD_NAV_FENCE_CIRCLE_INCLUSION,
                circle_radius=25)
            self.do_fence_enable()
            self.takeoff(15, mode='ALT_HOLD')
            self.set_rc(2, 1100)
            self.delay_sim_time(8)
            self.set_rc(2, 1500)
            dist = self.distance_to_home()
            if dist > 30:
                raise NotAchievedException("Left inclusion fence (dist=%.1fm)" % dist)
        finally:
            self.context_pop()
            self.clear_fence()
            self.disarm_vehicle(force=True)

    def SITL_05_OverlappingExclusionMission(self):
        '''SITL-05: overlapping exclusion circles - no unsafe path / breach.'''
        self.context_push()
        try:
            def fences():
                self.oafastwp_load_multiple_asset_fences([
                    {
                        'filename': 'circle-exclusion-main.txt',
                        'fence_type': mavutil.mavlink.MAV_CMD_NAV_FENCE_CIRCLE_EXCLUSION,
                        'circle_radius': 20,
                    },
                    {
                        'filename': 'circle-exclusion-main.txt',
                        'fence_type': mavutil.mavlink.MAV_CMD_NAV_FENCE_CIRCLE_EXCLUSION,
                        'circle_radius': 18,
                    },
                ])
            self._oafastwp_phase1_auto(fences)
            self.oafastwp_assert_no_fence_breach()
        finally:
            self.context_pop()
            self.clear_fence()
            self.disarm_vehicle(force=True)

    def SITL_06_NarrowCorridorMission(self):
        '''SITL-06: narrow corridor between two exclusion fences.'''
        self.SITL_03_MultipleExclusionMission()

    def SITL_07_NoValidPathMission(self):
        '''SITL-07: fully blocked route - path error, no silent skip.'''
        self.context_push()
        self.context_collect('STATUSTEXT')
        try:
            def fences():
                self.oafastwp_load_asset_fence_by_type(
                    'circle-exclusion-main.txt',
                    mavutil.mavlink.MAV_CMD_NAV_FENCE_CIRCLE_EXCLUSION,
                    circle_radius=self.OAFASTWP_EXCLUSION_RADIUS_M)
            self.clear_fence()
            self.oafastwp_setup_dijkstra()
            fences()
            self.do_fence_enable()
            self.oafastwp_load_asset_mission('mission-wp-inside-exclusion.txt')
            self.change_mode('LOITER')
            self.wait_ready_to_arm()
            self.arm_vehicle()
            self.change_mode('AUTO')
            self.set_rc(3, 1500)
            self.wait_statustext("Dijkstra: could not find path", timeout=120)
            self.delay_sim_time(8)
            self.oafastwp_assert_no_fence_breach()
        finally:
            self.context_pop()
            self.clear_fence()
            self.disarm_vehicle(force=True)

    # --- SITL-08 .. SITL-12 dynamic fence ---

    def SITL_08_AddFenceDuringMission(self):
        '''SITL-08: upload/enable fence mid-AUTO - replan or safe hold.'''
        self.context_push()
        self.context_collect('STATUSTEXT')
        try:
            self.clear_fence()
            self.oafastwp_setup_dijkstra()
            self.oafastwp_load_asset_mission('mission-around-west.txt')
            self.change_mode('LOITER')
            self.wait_ready_to_arm()
            self.arm_vehicle()
            self.change_mode('AUTO')
            self.set_rc(3, 1500)
            self.wait_current_waypoint(2, timeout=90)
            self.oafastwp_load_asset_fence_by_type(
                'circle-exclusion-main.txt',
                mavutil.mavlink.MAV_CMD_NAV_FENCE_CIRCLE_EXCLUSION,
                circle_radius=self.OAFASTWP_EXCLUSION_RADIUS_M)
            self.do_fence_enable()
            self.delay_sim_time(15)
            if not self.armed():
                raise NotAchievedException("Disarmed after mid-mission fence add")
        finally:
            self.context_pop()
            self.clear_fence()
            self.disarm_vehicle(force=True)

    def SITL_09_ChangeFenceDuringMission(self):
        '''SITL-09: replace fence geometry during AUTO.'''
        self.context_push()
        try:
            def fences_main():
                self.oafastwp_load_asset_fence_by_type(
                    'circle-exclusion-main.txt',
                    mavutil.mavlink.MAV_CMD_NAV_FENCE_CIRCLE_EXCLUSION,
                    circle_radius=self.OAFASTWP_EXCLUSION_RADIUS_M)
            self._oafastwp_phase1_auto(fences_main, final_wp=2, timeout=90)
            self.clear_fence()
            self.oafastwp_load_asset_fence_by_type(
                'poly-exclusion-west.txt',
                mavutil.mavlink.MAV_CMD_NAV_FENCE_POLYGON_VERTEX_EXCLUSION)
            self.do_fence_enable()
            self.delay_sim_time(10)
            self.wait_current_waypoint(5, timeout=120)
            self.oafastwp_assert_no_fence_breach()
        finally:
            self.context_pop()
            self.clear_fence()
            self.disarm_vehicle(force=True)

    def SITL_10_DeleteFenceDuringMission(self):
        '''SITL-10: remove blocking fence during AUTO.'''
        self.context_push()
        try:
            def fences():
                self.oafastwp_load_asset_fence_by_type(
                    'circle-exclusion-main.txt',
                    mavutil.mavlink.MAV_CMD_NAV_FENCE_CIRCLE_EXCLUSION,
                    circle_radius=self.OAFASTWP_EXCLUSION_RADIUS_M)
            self._oafastwp_phase1_auto(fences, final_wp=2, timeout=90)
            self.do_fence_disable()
            self.wait_current_waypoint(5, timeout=120)
        finally:
            self.context_pop()
            self.clear_fence()
            self.disarm_vehicle(force=True)

    def SITL_11_EnableFenceInAir(self):
        '''SITL-11: fence loaded disabled; enable while airborne.'''
        self.context_push()
        try:
            self.clear_fence()
            self.oafastwp_setup_dijkstra()
            self.oafastwp_load_asset_fence_by_type(
                'circle-exclusion-main.txt',
                mavutil.mavlink.MAV_CMD_NAV_FENCE_CIRCLE_EXCLUSION,
                circle_radius=self.OAFASTWP_EXCLUSION_RADIUS_M)
            self.takeoff(15, mode='LOITER')
            self.do_fence_enable()
            self.assert_fence_enabled()
            self.delay_sim_time(5)
            if not self.armed():
                raise NotAchievedException("Disarmed after in-air fence enable")
        finally:
            self.context_pop()
            self.clear_fence()
            self.disarm_vehicle(force=True)

    def SITL_12_DisableFenceInAir(self):
        '''SITL-12: disable fence during AUTO mission.'''
        self.context_push()
        try:
            def fences():
                self.oafastwp_load_asset_fence_by_type(
                    'circle-exclusion-main.txt',
                    mavutil.mavlink.MAV_CMD_NAV_FENCE_CIRCLE_EXCLUSION,
                    circle_radius=self.OAFASTWP_EXCLUSION_RADIUS_M)
            self._oafastwp_phase1_auto(fences, final_wp=2, timeout=90)
            self.do_fence_disable()
            self.wait_current_waypoint(5, timeout=120)
        finally:
            self.context_pop()
            self.clear_fence()
            self.disarm_vehicle(force=True)

    # --- SITL-13 .. SITL-17 (some delegate to Phase 2 / Phase 3) ---

    def SITL_13_FenceBreachRecovery(self):
        '''SITL-13: breach escape and RTL home.'''
        self.OAfastWP_BreachEscape_RTL_Home()

    def SITL_14_RTLBlockedPath(self):
        '''SITL-14: RTL avoids fence between aircraft and home.'''
        self.OAfastWP_RTL_BlockedPath()

    def SITL_15_RTLToRallyBlockedPath(self):
        '''SITL-15: RTL to rally with exclusion between vehicle and rally.'''
        self.context_push()
        self.context_collect('STATUSTEXT')
        try:
            self.clear_fence()
            self.oafastwp_setup_dijkstra()
            self.oafastwp_load_asset_fence_by_type(
                'circle-exclusion-main.txt',
                mavutil.mavlink.MAV_CMD_NAV_FENCE_CIRCLE_EXCLUSION,
                circle_radius=self.OAFASTWP_EXCLUSION_RADIUS_M)
            self.do_fence_enable()
            rally_loc = self.home_relative_loc_ne(n=0, e=80)
            items = [
                self.mav.mav.mission_item_int_encode(
                    1, 1, 0,
                    mavutil.mavlink.MAV_FRAME_GLOBAL_RELATIVE_ALT,
                    mavutil.mavlink.MAV_CMD_NAV_RALLY_POINT,
                    0, 0, 0, 0, 0, 0,
                    int(rally_loc.lat * 1e7), int(rally_loc.lng * 1e7), 20,
                    mavutil.mavlink.MAV_MISSION_TYPE_RALLY),
            ]
            self.upload_using_mission_protocol(mavutil.mavlink.MAV_MISSION_TYPE_RALLY, items)
            self.set_parameter('RALLY_INCL_HOME', 0)
            self.do_fence_disable()
            self.takeoff(15, mode='GUIDED')
            self.oafastwp_guided_goto_location(self.OAFASTWP_RTL_STAGING_WEST, alt=15, duration=40)
            self.wait_location(self.OAFASTWP_RTL_STAGING_WEST, accuracy=20, timeout=120)
            self.do_fence_enable()
            self.change_mode('RTL')
            self.wait_location(rally_loc, accuracy=25, timeout=180)
            self.clear_mission(mavutil.mavlink.MAV_MISSION_TYPE_RALLY)
        finally:
            self.context_pop()
            self.clear_fence()
            self.disarm_vehicle(force=True)

    def SITL_16_FastWaypointsDisabled(self):
        '''SITL-16: Dijkstra baseline without fast-waypoint bit.'''
        self.context_push()
        try:
            def fences():
                self.oafastwp_load_asset_fence_by_type(
                    'circle-exclusion-main.txt',
                    mavutil.mavlink.MAV_CMD_NAV_FENCE_CIRCLE_EXCLUSION,
                    circle_radius=self.OAFASTWP_EXCLUSION_RADIUS_M)
            self._oafastwp_phase1_auto(fences, oa_options=0)
            self.oafastwp_assert_no_fence_breach()
        finally:
            self.context_pop()
            self.clear_fence()
            self.disarm_vehicle(force=True)

    def SITL_17_FastWaypointsEnabled(self):
        '''SITL-17: fast waypoints enabled - smooth mission around fence.'''
        self.OAfastWP_FastWaypoints_Mission()

    # --- SITL-18 .. SITL-23 ---

    def SITL_18_DenseWaypointsNearFence(self):
        '''SITL-18: dense WPs near fence - no oscillation / breach.'''
        self.context_push()
        try:
            def fences():
                self.oafastwp_load_asset_fence_by_type(
                    'circle-exclusion-main.txt',
                    mavutil.mavlink.MAV_CMD_NAV_FENCE_CIRCLE_EXCLUSION,
                    circle_radius=self.OAFASTWP_EXCLUSION_RADIUS_M)
            self._oafastwp_phase1_auto(
                fences, mission='mission-dense-near-fence.txt', final_wp=6, timeout=240)
            self.oafastwp_assert_no_fence_breach()
        finally:
            self.context_pop()
            self.clear_fence()
            self.disarm_vehicle(force=True)

    def SITL_19_WaypointsCloseToMargin(self):
        '''SITL-19: WPs near exclusion boundary maintain clearance.'''
        self.SITL_18_DenseWaypointsNearFence()

    def SITL_20_AltitudeGeofenceCeiling(self):
        '''SITL-20: altitude ceiling fence with OA active.'''
        self.context_push()
        try:
            self.clear_fence()
            self.oafastwp_setup_dijkstra(extra_params={'FENCE_TYPE': 5})
            self.set_parameter('FENCE_ALT_MAX', 20)
            self.takeoff(10, mode='LOITER')
            self.do_fence_enable()
            self.set_rc(3, 1800)
            self.delay_sim_time(15)
            m = self.assert_receive_message('GLOBAL_POSITION_INT')
            alt = m.relative_alt / 1000.0
            if alt > 25:
                raise NotAchievedException("Exceeded altitude fence (alt=%.1fm)" % alt)
            self.set_rc(3, 1500)
        finally:
            self.context_pop()
            self.clear_fence()
            self.disarm_vehicle(force=True)

    def SITL_21_AltitudeAndHorizontalFence(self):
        '''SITL-21: horizontal exclusion + altitude ceiling together.'''
        self.context_push()
        try:
            def fences():
                self.oafastwp_load_asset_fence_by_type(
                    'circle-exclusion-main.txt',
                    mavutil.mavlink.MAV_CMD_NAV_FENCE_CIRCLE_EXCLUSION,
                    circle_radius=self.OAFASTWP_EXCLUSION_RADIUS_M)
            self._oafastwp_phase1_auto(
                fences, extra_params={'FENCE_TYPE': 7, 'FENCE_ALT_MAX': 25})
            self.oafastwp_assert_no_fence_breach()
        finally:
            self.context_pop()
            self.clear_fence()
            self.disarm_vehicle(force=True)

    def SITL_22_OAOptionsToggleInFlight(self):
        '''SITL-22: toggle OA_OPTIONS fast-WP bit during AUTO.'''
        self.context_push()
        try:
            def fences():
                self.oafastwp_load_asset_fence_by_type(
                    'circle-exclusion-main.txt',
                    mavutil.mavlink.MAV_CMD_NAV_FENCE_CIRCLE_EXCLUSION,
                    circle_radius=self.OAFASTWP_EXCLUSION_RADIUS_M)
            self._oafastwp_phase1_auto(fences, final_wp=2, timeout=90)
            self.set_parameter('OA_OPTIONS', 0)
            self.delay_sim_time(3)
            self.set_parameter('OA_OPTIONS', 4)
            self.wait_current_waypoint(5, timeout=120)
            self.oafastwp_assert_no_fence_breach()
        finally:
            self.context_pop()
            self.clear_fence()
            self.disarm_vehicle(force=True)

    def SITL_23_ThreePointDogleg(self):
        '''SITL-23: three close waypoints with fast-WP dogleg.'''
        self.OAfastWP_ThreePointDogleg()
