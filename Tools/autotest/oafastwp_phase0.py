'''
Phase 0 firmware-update regression (copter).

Curated subset of upstream ArduPilot autotest (CopterTests1a..2b, testsMA)
intended to run before OAfastWP Phase 1..3 on every new firmware build.

Each test is a thin wrapper (P0_XX_*) so buildlogs and visual evidence
map cleanly to P0-01..P0-22 IDs.
'''


class OAfastWPPhase0Mixin(object):
    '''Upstream + Malloy baseline regression gate (run on every fw update).'''

    def _run_upstream(self, asset_dir, upstream_method):
        '''Run upstream autotest using its ArduCopter_Tests asset directory.'''
        self.set_current_test_name(asset_dir)
        upstream_method()

    def testsOAfastWPPhase0(self):
        return [
            # --- Boot / config (common.py base) ---
            self.P0_01_Parameters,
            self.P0_02_ArmFeatures,
            self.P0_03_Logging,
            # --- Core flight modes ---
            self.P0_04_ModeAltHold,
            self.P0_05_ModeLoiter,
            self.P0_06_TakeoffCheck,
            self.P0_07_Landing,
            self.P0_08_CopterMission,
            self.P0_09_GuidedSubModeChange,
            self.P0_10_LoiterToAlt,
            # --- Fence / failsafe ---
            self.P0_11_HorizontalFence,
            self.P0_12_ThrottleFailsafe,
            self.P0_13_GCSFailsafe,
            # --- RTL / rally ---
            self.P0_14_SMART_RTL,
            self.P0_15_RTL_TO_RALLY,
            # --- Nav / logging ---
            self.P0_16_WPNAV_SPEED,
            self.P0_17_DataFlash,
            self.P0_18_ParameterChecks,
            # --- Malloy Dijkstra baseline (testsMA) ---
            self.P0_19_Dijkstra_OutsideInclusion,
            self.P0_20_Dijkstra_InsideExclusion,
            self.P0_21_Dijkstra_PathPlanningReturn,
            self.P0_22_RTL_BrakingDistance,
        ]

    # --- P0-01 .. P0-03: boot / config (ArduPilot common.py) ---

    def P0_01_Parameters(self):
        '''P0-01: parameter load and set (upstream Parameters).'''
        self._run_upstream('Parameters', self.Parameters)

    def P0_02_ArmFeatures(self):
        '''P0-02: arm/disarm and pre-arm checks (upstream ArmFeatures).'''
        self._run_upstream('ArmFeatures', self.ArmFeatures)

    def P0_03_Logging(self):
        '''P0-03: onboard logging (upstream Logging).'''
        self._run_upstream('Logging', self.Logging)

    # --- P0-04 .. P0-10: core flight (CopterTests1a/1c/1d) ---

    def P0_04_ModeAltHold(self):
        '''P0-04: ALT_HOLD mode (upstream ModeAltHold).'''
        self._run_upstream('ModeAltHold', self.ModeAltHold)

    def P0_05_ModeLoiter(self):
        '''P0-05: LOITER mode (upstream ModeLoiter).'''
        self._run_upstream('ModeLoiter', self.ModeLoiter)

    def P0_06_TakeoffCheck(self):
        '''P0-06: takeoff checks (upstream TakeoffCheck).'''
        self._run_upstream('TakeoffCheck', self.TakeoffCheck)

    def P0_07_Landing(self):
        '''P0-07: landing sequence (upstream Landing).'''
        self._run_upstream('Landing', self.Landing)

    def P0_08_CopterMission(self):
        '''P0-08: AUTO mission (upstream CopterMission).'''
        self._run_upstream('CopterMission', self.CopterMission)

    def P0_09_GuidedSubModeChange(self):
        '''P0-09: GUIDED sub-mode changes (upstream GuidedSubModeChange).'''
        self._run_upstream('GuidedSubModeChange', self.GuidedSubModeChange)

    def P0_10_LoiterToAlt(self):
        '''P0-10: LOITER altitude change (upstream LoiterToAlt).'''
        self._run_upstream('LoiterToAlt', self.LoiterToAlt)

    # --- P0-11 .. P0-13: fence / failsafe (CopterTests1b/1d) ---

    def P0_11_HorizontalFence(self):
        '''P0-11: horizontal geofence (upstream HorizontalFence).'''
        self._run_upstream('HorizontalFence', self.HorizontalFence)

    def P0_12_ThrottleFailsafe(self):
        '''P0-12: throttle failsafe (upstream ThrottleFailsafe).'''
        self._run_upstream('ThrottleFailsafe', self.ThrottleFailsafe)

    def P0_13_GCSFailsafe(self):
        '''P0-13: GCS failsafe (upstream GCSFailsafe).'''
        self._run_upstream('GCSFailsafe', self.GCSFailsafe)

    # --- P0-14 .. P0-15: RTL (CopterTests2b) ---

    def P0_14_SMART_RTL(self):
        '''P0-14: SMART_RTL (upstream SMART_RTL).'''
        self._run_upstream('SMART_RTL', self.SMART_RTL)

    def P0_15_RTL_TO_RALLY(self):
        '''P0-15: RTL to rally point (upstream RTL_TO_RALLY).'''
        self._run_upstream('RTL_TO_RALLY', self.RTL_TO_RALLY)

    # --- P0-16 .. P0-18: nav / params (CopterTests2b/1e) ---

    def P0_16_WPNAV_SPEED(self):
        '''P0-16: WP nav speed params (upstream WPNAV_SPEED).'''
        self._run_upstream('WPNAV_SPEED', self.WPNAV_SPEED)

    def P0_17_DataFlash(self):
        '''P0-17: dataflash log integrity (upstream DataFlash).'''
        self._run_upstream('DataFlash', self.DataFlash)

    def P0_18_ParameterChecks(self):
        '''P0-18: parameter validation (upstream ParameterChecks).'''
        self._run_upstream('ParameterChecks', self.ParameterChecks)

    # --- P0-19 .. P0-22: Malloy Dijkstra baseline (testsMA) ---

    def P0_19_Dijkstra_OutsideInclusion(self):
        '''P0-19: Dijkstra RTL outside inclusion fence (testsMA).'''
        self._run_upstream(
            'Dijkstra_FenceRecovery_OutsideInclusion',
            self.Dijkstra_FenceRecovery_OutsideInclusion)

    def P0_20_Dijkstra_InsideExclusion(self):
        '''P0-20: Dijkstra RTL from inside exclusion (testsMA).'''
        self._run_upstream(
            'Dijkstra_FenceRecovery_InsideExclusion',
            self.Dijkstra_FenceRecovery_InsideExclusion)

    def P0_21_Dijkstra_PathPlanningReturn(self):
        '''P0-21: Dijkstra path planning return (testsMA).'''
        self._run_upstream(
            'Dijkstra_FenceRecovery_PathPlanningReturn',
            self.Dijkstra_FenceRecovery_PathPlanningReturn)

    def P0_22_RTL_BrakingDistance(self):
        '''P0-22: RTL braking distance (testsMA).'''
        self.RTL_braking_distance()
