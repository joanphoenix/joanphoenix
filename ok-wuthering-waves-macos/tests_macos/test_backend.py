import unittest
from dataclasses import replace
import numpy as np

from macos_port.backend import MacOSBackend, WindowInfo, BackendError, SafetyStop, WindowSelectionError
from macos_port.geometry import Rect, Insets, FrameGeometry


class FakeNative:
    def __init__(self):
        self.window = WindowInfo(7, 42, "Wuthering Waves", "Wuthering Waves", "test.game", Rect(-960, 30, 960, 540))
        self.windows = [self.window]
        self.focus = 42
        self.escape = False
        self.covered = False
        self.accessibility = True
        self.events = []
        self.frame = np.zeros((1080, 1920, 3), dtype=np.uint8)

    def list_windows(self): return self.windows
    def get_window(self, window_id): return next((w for w in self.windows if w.window_id == window_id), None)
    def frontmost_pid(self): return self.focus
    def is_front_window(self, window): return not self.covered
    def physical_escape_pressed(self): return self.escape
    def permissions(self, request=False): return dict(screen_recording=True, accessibility=self.accessibility)
    def capture_window(self, window): return self.frame
    def post_key(self, code, down, held): self.events.append(("key", code, down, frozenset(held)))
    def post_move(self, point, dragging): self.events.append(("move", point, dragging))
    def post_button(self, point, button, down): self.events.append(("button", point, button, down))
    def post_scroll(self, delta): self.events.append(("scroll", delta))


class GeometryTests(unittest.TestCase):
    def test_retina_negative_desktop_origin_and_titlebar_crop(self):
        geometry = FrameGeometry.from_capture(Rect(-960, 30, 960, 568), 1920, 1136, Insets(top=28))
        self.assertEqual((geometry.width, geometry.height), (1920, 1080))
        self.assertEqual(geometry.to_desktop(960, 540), (-480, 328))
        self.assertEqual(geometry.to_desktop(0, 0), (-960, 58))

    def test_invalid_coordinate_never_maps_outside_content(self):
        geometry = FrameGeometry.from_capture(Rect(0, 0, 960, 540), 1920, 1080)
        for point in [(-1, 0), (1920, 1), (0, 1080), (float("nan"), 0)]:
            with self.subTest(point=point), self.assertRaises(ValueError):
                geometry.to_desktop(*point)
        with self.assertRaises(ValueError):
            FrameGeometry.from_capture(Rect(0, 0, 100, 100), 100, 100, Insets(top=100))


class BackendTests(unittest.TestCase):
    def setUp(self):
        self.native = FakeNative()
        self.backend = MacOSBackend(native=self.native, start_watchdog=False)
        self.backend.select_window()
        self.addCleanup(self.backend.stop)

    def test_input_requires_a_successful_capture(self):
        with self.assertRaisesRegex(BackendError, "Capture a valid"):
            self.backend.key_down("w")
        self.assertEqual(self.native.events, [])

    def test_focus_loss_releases_all_and_latches_stop(self):
        self.backend.capture()
        self.backend.key_down("w")
        self.backend.mouse_down(960, 540)
        self.native.focus = 999
        with self.assertRaises(SafetyStop): self.backend.check_guard()
        self.assertIn(("key", 13, False, frozenset()), self.native.events)
        self.assertIn(("button", (-480, 300), "left", False), self.native.events)
        self.native.focus = 42
        with self.assertRaises(SafetyStop): self.backend.key_down("a")

    def test_resize_stop_prevents_stale_coordinates(self):
        self.backend.capture()
        self.native.windows = [replace(self.native.window, bounds=Rect(0, 0, 1000, 600))]
        with self.assertRaises(SafetyStop): self.backend.click(100, 100)
        self.assertEqual(self.native.events, [])

    def test_covered_window_stops(self):
        self.backend.capture()
        self.native.covered = True
        with self.assertRaises(SafetyStop): self.backend.send_key("b")
        self.assertEqual(self.native.events, [])

    def test_escape_releases_held_input(self):
        self.backend.capture()
        self.backend.key_down("shift")
        self.native.escape = True
        with self.assertRaises(SafetyStop): self.backend.check_guard()
        self.assertEqual(self.native.events[-1], ("key", 56, False, frozenset()))

    def test_chord_keeps_preexisting_held_modifier(self):
        self.backend.capture()
        self.backend.key_down("shift")
        self.backend.send_key("shift+w", down_time=0)
        self.assertIn("shift", self.backend._held_keys)
        self.assertNotIn("w", self.backend._held_keys)
        self.backend.key_up("shift")

    def test_permission_revocation_stops(self):
        self.backend.capture()
        self.native.accessibility = False
        with self.assertRaises(SafetyStop): self.backend.send_key("b")
        self.assertEqual(self.native.events, [])

    def test_ambiguous_window_requires_selection(self):
        self.native.windows.append(replace(self.native.window, window_id=8))
        with self.assertRaises(WindowSelectionError): self.backend.select_window()

    def test_capture_scale_change_stops(self):
        self.backend.capture()
        self.native.frame = np.zeros((540, 960, 3), dtype=np.uint8)
        with self.assertRaises(SafetyStop): self.backend.capture()

    def test_failed_key_post_attempts_release(self):
        self.backend.capture()
        original = self.native.post_key
        def post(code, down, held):
            original(code, down, held)
            if down: raise RuntimeError("native failure")
        self.native.post_key = post
        with self.assertRaises(RuntimeError): self.backend.key_down("w")
        self.assertEqual(self.native.events[-1], ("key", 13, False, frozenset()))
        self.assertTrue(self.backend.stopped)


if __name__ == "__main__": unittest.main()
