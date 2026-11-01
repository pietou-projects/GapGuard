"""Candidate.6 SignalTests retained verbatim; only recovery test retired."""
import unittest
from gapguard import Machine,Motion,Native
from test_support import settings,session

class RetainedSignalTests(unittest.TestCase):
    def test_all_initial_couples_are_acquisition(self):
        for mask in range(4):
            m = Machine(settings()); m.start_ready(0., 7)
            m.gpio(.2, mask, 5.)
            self.assertEqual((m.motion.pd3, m.motion.pd4), (mask&1, mask>>1))
            self.assertIsNone(m.motion.last_edge_position)
            self.assertEqual(m.motion.count, 0)

    def test_no_baseline_at_half_second(self):
        m = Machine(settings()); m.start_ready(0., 99)
        m.observe(.5, Native(), 0.)
        self.assertIsNone(m.motion.pd4)
        m.observe(2.739, Native(), 0.)
        self.assertIsNone(m.motion.pd3)
        m.observe(2.740, Native(), 0.)
        self.assertEqual((m.motion.pd3, m.motion.pd4), (0, 0))
        self.assertIsNone(m.motion.last_edge_position)

    def test_unknown_during_initialization_does_not_pause(self):
        m = Machine(settings()); m.start_ready(0., 5); m.reset(.01, pending_new=True)
        m.observe(.5, Native('printing', True, '/j'), 0.)
        m.observe(.6, Native('printing', True, '/j'), 60.)
        self.assertFalse(m.pause_requested)
        self.assertEqual(m.motion.state, 'ARMING')

    def test_known_absent_print_pauses_without_new_edge(self):
        m, p = session()
        m.motion.pd4 = 0
        m.observe(1., p.n, 1.)
        self.assertTrue(m.pause_requested)
        self.assertEqual(m.reason, 'PD4_ABSENT')

    def test_duplicate_level_not_a_transition(self):
        m, p = session()
        m.gpio(1., 2, 10.)
        self.assertIsNone(m.motion.last_edge_position)

    def test_nine_only_warns_and_retraction_does_not_add_e(self):
        m, p = session()
        m.observe(1., p.n, 9.)
        self.assertEqual(m.motion.state, 'SUSPECT')
        self.assertFalse(m.pause_requested)
        m.observe(2., p.n, -4.)
        self.assertEqual(m.motion.position, -4.)
        self.assertFalse(m.pause_requested)

    def test_front_at_fifty_wins_both_delivery_orders(self):
        for timer_first in (True, False):
            motion = Motion(settings()); motion.acquire(2); motion.arm(0.)
            if timer_first: motion.observe(50., True)
            motion.edge(50.)
            motion.observe(50., True)
            self.assertEqual(motion.state, 'NORMAL')
            self.assertEqual(motion.reference, 50.)

    def test_window_fixed_when_tick_is_late(self):
        motion = Motion(settings()); motion.acquire(2); motion.arm(0.)
        motion.observe(50.4, True)
        self.assertEqual((motion.verify_start, motion.verify_end), (50., 62.))
        motion.edge(51.)
        self.assertEqual(motion.state, 'VERIFY_50')

    def test_sixth_edge_at_sixty_two_is_inclusive(self):
        motion = Motion(settings()); motion.acquire(2); motion.arm(0.)
        motion.observe(50.4, True)
        for pos in (52., 54., 56., 58., 60., 62.): motion.edge(pos)
        self.assertIsNone(motion.observe(62., True))
        self.assertEqual(motion.state, 'NORMAL')

    def test_late_queued_boundary_edge_cancels_unissued_sensor_pause(self):
        m, p = session()
        m.observe(1., p.n, 50.4)
        for pos in (52., 54., 56., 58., 60.): m.motion.edge(pos)
        m.observe(2., p.n, 62.)
        self.assertTrue(m.pause_requested)
        m.motion.edge(62.)
        p.tick()
        self.assertEqual(m.motion.state, 'NORMAL')
        self.assertFalse(any(c[0]=='native_pause' for c in p.calls))

    def test_five_edges_fail_without_sliding(self):
        motion = Motion(settings()); motion.acquire(2); motion.arm(0.)
        motion.observe(50.4, True)
        for pos in (52., 54., 56., 58., 60.): motion.edge(pos)
        self.assertEqual(motion.observe(62., True), 'VERIFY_FAIL')

    def test_unknown_no_signal_only_after_init(self):
        motion = Motion(settings()); motion.arm(0.)
        self.assertIsNone(motion.observe(50., False))
        self.assertEqual(motion.observe(50., True), 'PD3_NO_SIGNAL')

