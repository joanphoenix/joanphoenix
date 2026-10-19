"""Foreground-only native macOS capture and input.

Native imports are deliberately deferred: geometry and safety behavior can be
tested on other platforms. Requires macOS 14+, Screen Recording, Accessibility,
and a visible, focused game window. This module never launches or activates an
application and never uses the removed CGWindowListCreateImage API.
"""

from dataclasses import dataclass
import math
import platform
import threading
import time

from .geometry import FrameGeometry, Insets, Rect


class BackendError(RuntimeError):
    pass


class PermissionDenied(BackendError):
    pass


class SafetyStop(BackendError):
    pass


class WindowSelectionError(BackendError):
    pass


@dataclass(frozen=True)
class WindowInfo:
    window_id: int
    pid: int
    title: str
    owner_name: str
    bundle_id: str
    bounds: Rect


# Physical US-layout key positions, matching the game's default key bindings.
KEY_CODES = {
    "a": 0, "s": 1, "d": 2, "f": 3, "h": 4, "g": 5, "z": 6,
    "x": 7, "c": 8, "v": 9, "b": 11, "q": 12, "w": 13, "e": 14,
    "r": 15, "y": 16, "t": 17, "1": 18, "2": 19, "3": 20, "4": 21,
    "6": 22, "5": 23, "=": 24, "9": 25, "7": 26, "-": 27, "8": 28,
    "0": 29, "]": 30, "o": 31, "u": 32, "[": 33, "i": 34, "p": 35,
    "enter": 36, "l": 37, "j": 38, "'": 39, "k": 40, ";": 41,
    "\\": 42, ",": 43, "/": 44, "n": 45, "m": 46, ".": 47,
    "tab": 48, "space": 49, "`": 50, "backspace": 51, "esc": 53,
    "command": 55, "shift": 56, "capslock": 57, "alt": 58, "ctrl": 59,
    "rightshift": 60, "rightalt": 61, "rightctrl": 62,
    "f1": 122, "f2": 120, "f3": 99, "f4": 118, "f5": 96,
    "f6": 97, "f7": 98, "f8": 100, "f9": 101, "f10": 109,
    "f11": 103, "f12": 111, "home": 115, "end": 119,
    "pageup": 116, "pagedown": 121, "delete": 117,
    "left": 123, "right": 124, "down": 125, "up": 126,
}
KEY_ALIASES = {
    "escape": "esc", "return": "enter", "control": "ctrl", "lctrl": "ctrl",
    "rctrl": "rightctrl", "option": "alt", "lalt": "alt", "ralt": "rightalt",
    "cmd": "command", "meta": "command", "lshift": "shift", "rshift": "rightshift",
    "spacebar": "space", " ": "space", "arrowleft": "left", "arrowright": "right",
    "arrowup": "up", "arrowdown": "down", "pgup": "pageup", "pgdn": "pagedown",
}


def normalize_key(key):
    name = str(key).lower()
    name = KEY_ALIASES.get(name, name)
    if name not in KEY_CODES:
        raise ValueError(f"Unsupported macOS physical key: {key!r}")
    return name


def normalize_button(button):
    name = {0: "left", 1: "right", 2: "middle"}.get(button, str(button).lower())
    if name not in ("left", "right", "middle"):
        raise ValueError(f"Unsupported mouse button: {button!r}")
    return name


class MacOSBackend:
    def __init__(self, window_id=None, pid=None, bundle_id=None,
                 title_contains="Wuthering Waves", crop=None, *, native=None,
                 watchdog_interval=0.05, start_watchdog=True):
        self.window_id = window_id
        self.pid = pid
        self.bundle_id = bundle_id
        self.title_contains = title_contains
        self.crop = crop or Insets()
        self._native_instance = native
        self.window = None
        self._geometry = None
        self._held_keys = set()
        self._held_buttons = set()
        self._last_point = None
        self._lock = threading.RLock()
        self._stopped = threading.Event()
        self._stop_reason = None
        self._watchdog_interval = max(0.01, watchdog_interval)
        self._start_watchdog = start_watchdog
        self._watchdog = None

    @property
    def native(self):
        if self._native_instance is None:
            self._native_instance = _NativeMacOS()
        return self._native_instance

    @property
    def width(self):
        return self._geometry.width if self._geometry else 0

    @property
    def height(self):
        return self._geometry.height if self._geometry else 0

    @property
    def stopped(self):
        return self._stopped.is_set()

    def check_permissions(self, request=False):
        return self.native.permissions(request=request)

    def list_windows(self):
        return self.native.list_windows()

    def select_window(self):
        """Select one unambiguous visible window; do not bring it to the front."""
        with self._lock:
            if self.stopped:
                raise SafetyStop(self._stop_reason or "Backend has stopped; create a new session")
            if self._held_keys or self._held_buttons:
                raise BackendError("Cannot select a window while input is held")
            windows = self.list_windows()
            if self.window_id is not None:
                windows = [w for w in windows if w.window_id == self.window_id]
            if self.pid is not None:
                windows = [w for w in windows if w.pid == self.pid]
            if self.bundle_id:
                windows = [w for w in windows if w.bundle_id == self.bundle_id]
            if self.window_id is None and self.pid is None and not self.bundle_id:
                terms = [self.title_contains.casefold()] if self.title_contains else []
                if self.title_contains == "Wuthering Waves":
                    terms.extend(("鸣潮", "鳴潮"))
                if not terms:
                    raise WindowSelectionError("Provide a window ID, PID, bundle ID, or title filter")
                windows = [w for w in windows if any(
                    term in f"{w.title} {w.owner_name}".casefold() for term in terms)]
            if not windows:
                raise WindowSelectionError("No matching visible game window. Use the windows command, then --window-id.")
            if len(windows) != 1:
                choices = ", ".join(f"{w.window_id}: {w.title or w.owner_name}" for w in windows)
                raise WindowSelectionError(f"Multiple matching windows ({choices}); select --window-id explicitly")
            self.window = windows[0]
            self._geometry = None
            self._last_point = None
            return self.window

    def _fail(self, reason):
        self._stop_reason = reason
        self._stopped.set()
        self.release_all()
        raise SafetyStop(reason)

    def check_guard(self):
        """Fail closed on Escape, focus loss, disappearance, or geometry changes."""
        with self._lock:
            if self.stopped:
                raise SafetyStop(self._stop_reason or "Automation stopped")
            if self.window is None:
                raise BackendError("Select a game window first")
            try:
                if self.native.physical_escape_pressed():
                    self._fail("Physical Escape pressed; automation stopped")
                if self.native.frontmost_pid() != self.window.pid:
                    self._fail("Game lost foreground focus; automation stopped")
                current = self.native.get_window(self.window.window_id)
                if current is None or current.pid != self.window.pid:
                    self._fail("Selected game window disappeared; automation stopped")
                if not self.window.bounds.same_as(current.bounds):
                    self._fail("Game window moved or resized; restart and capture a fresh frame")
                if not self.native.is_front_window(self.window):
                    self._fail("Another window covers the selected game window; automation stopped")
            except SafetyStop:
                raise
            except Exception as exc:
                self._fail(f"Cannot verify game window safety: {exc}")
            return True

    def _ensure_input(self):
        self.check_guard()
        if self._geometry is None:
            raise BackendError("Capture a valid frame before sending input")
        permissions = self.check_permissions()
        if not permissions.get("accessibility"):
            self._fail("Accessibility permission is missing or was revoked")

    def capture(self):
        """Capture BGR pixels, trimmed by explicit logical-point content insets."""
        if self.window is None:
            self.select_window()
        self.check_guard()
        if not self.check_permissions().get("screen_recording"):
            with self._lock:
                self._fail("Screen Recording permission is missing or was revoked")
        # Do not hold the input lock while waiting for an asynchronous screenshot:
        # the watchdog must still release keys during a stalled capture.
        try:
            frame = self.native.capture_window(self.window)
            with self._lock:
                self.check_guard()
                if frame is None or frame.ndim != 3 or frame.shape[2] != 3:
                    self._fail("Capture returned no valid BGR frame")
                geometry = FrameGeometry.from_capture(
                    self.window.bounds, frame.shape[1], frame.shape[0], self.crop)
                if self._geometry and (geometry.full_width, geometry.full_height) != (
                        self._geometry.full_width, self._geometry.full_height):
                    self._fail("Capture pixel scale changed; restart and capture a fresh frame")
                self._geometry = geometry
                result = frame[geometry.top:geometry.bottom, geometry.left:geometry.right].copy()
                self._ensure_watchdog()
                return result
        except (KeyboardInterrupt, SystemExit):
            self.stop()
            raise
        except SafetyStop:
            raise
        except Exception as exc:
            with self._lock:
                self._fail(f"Screen capture failed: {exc}")

    def _ensure_watchdog(self):
        if self._start_watchdog and self._watchdog is None:
            self._watchdog = threading.Thread(target=self._watch, name="macos-input-guard", daemon=True)
            self._watchdog.start()

    def _watch(self):
        while not self._stopped.wait(self._watchdog_interval):
            try:
                self.check_guard()
            except Exception:
                # check_guard has already released held input and latched stop.
                return

    def move(self, x, y):
        with self._lock:
            self._ensure_input()
            point = self._geometry.to_desktop(x, y)
            dragging = next(iter(self._held_buttons), None)
            self.native.post_move(point, dragging)
            self._last_point = point

    def mouse_down(self, x=None, y=None, button="left"):
        button = normalize_button(button)
        with self._lock:
            self._ensure_input()
            if (x is None) != (y is None):
                raise ValueError("Specify both x and y")
            if x is not None:
                self.move(x, y)
            if self._last_point is None:
                raise BackendError("Move to a captured-image coordinate before pressing a mouse button")
            if button not in self._held_buttons:
                # Track before posting so cleanup covers an interrupted native call.
                self._held_buttons.add(button)
                try:
                    self.native.post_button(self._last_point, button, True)
                except BaseException:
                    self.stop()
                    raise

    def mouse_up(self, x=None, y=None, button="left"):
        button = normalize_button(button)
        with self._lock:
            try:
                if (x is None) != (y is None):
                    raise ValueError("Specify both x and y")
                if x is not None:
                    self.move(x, y)
            finally:
                if button in self._held_buttons:
                    self._held_buttons.remove(button)
                    self.native.post_button(self._last_point, button, False)

    def click(self, x, y, button="left", down_time=0.02):
        try:
            self.mouse_down(x, y, button)
            self._wait(down_time)
        finally:
            self.mouse_up(button=button)

    def scroll(self, delta, x=None, y=None):
        if not math.isfinite(delta):
            raise ValueError("Scroll delta must be finite")
        with self._lock:
            self._ensure_input()
            if (x is None) != (y is None):
                raise ValueError("Specify both x and y")
            if x is not None:
                self.move(x, y)
            if self._last_point is None:
                raise BackendError("Move to the game window before scrolling")
            self.native.post_scroll(round(delta))

    def key_down(self, key):
        key = normalize_key(key)
        with self._lock:
            self._ensure_input()
            if key not in self._held_keys:
                self._held_keys.add(key)
                try:
                    self.native.post_key(KEY_CODES[key], True, self._held_keys)
                except BaseException:
                    self.stop()
                    raise

    def key_up(self, key):
        key = normalize_key(key)
        with self._lock:
            if key in self._held_keys:
                self._held_keys.remove(key)
                self.native.post_key(KEY_CODES[key], False, self._held_keys)

    def send_key(self, key, down_time=0.02):
        keys = [normalize_key(part) for part in str(key).split("+")]
        pressed = []
        try:
            for name in keys:
                # A temporary chord must not release a key held by the caller.
                with self._lock:
                    was_held = name in self._held_keys
                    self.key_down(name)
                    if not was_held:
                        pressed.append(name)
            self._wait(down_time)
        finally:
            for name in reversed(pressed):
                self.key_up(name)

    def _wait(self, seconds):
        if not math.isfinite(seconds) or seconds < 0:
            raise ValueError("Input duration must be finite and nonnegative")
        deadline = time.monotonic() + seconds
        while True:
            self.check_guard()
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return
            self._stopped.wait(min(remaining, self._watchdog_interval))

    def release_all(self):
        """Best-effort releases are allowed after focus loss, with no new downs."""
        with self._lock:
            keys, buttons = tuple(self._held_keys), tuple(self._held_buttons)
            self._held_keys.clear()
            self._held_buttons.clear()
            for key in keys:
                try:
                    self.native.post_key(KEY_CODES[key], False, set())
                except Exception:
                    pass  # Continue releasing the remaining held inputs.
            for button in buttons:
                try:
                    self.native.post_button(self._last_point, button, False)
                except Exception:
                    pass

    def stop(self):
        with self._lock:
            self._stopped.set()
            self.release_all()

    close = stop

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.stop()


class _NativeMacOS:
    """Small PyObjC boundary; tests substitute a fake implementation."""

    def __init__(self):
        if platform.system() != "Darwin":
            raise BackendError("The native backend runs only on macOS 14 or newer")
        version = platform.mac_ver()[0]
        if not version or int(version.split(".")[0]) < 14:
            raise BackendError("ScreenCaptureKit screenshot capture requires macOS 14 or newer")
        try:
            import AppKit
            import ApplicationServices
            import Quartz
            import ScreenCaptureKit
        except ImportError as exc:
            raise BackendError("Install requirements-macos.txt in the arm64 Python environment") from exc
        self.appkit = AppKit
        self.ax = ApplicationServices
        self.q = Quartz
        self.sc = ScreenCaptureKit
        self._filters = {}
        self._event_source = Quartz.CGEventSourceCreate(Quartz.kCGEventSourceStatePrivate)

    def permissions(self, request=False):
        screen = bool(self.q.CGPreflightScreenCaptureAccess())
        if request and not screen:
            self.q.CGRequestScreenCaptureAccess()
            screen = bool(self.q.CGPreflightScreenCaptureAccess())
        accessibility = bool(self.ax.AXIsProcessTrustedWithOptions(
            {self.ax.kAXTrustedCheckOptionPrompt: bool(request)}))
        return {"screen_recording": screen, "accessibility": accessibility}

    def list_windows(self):
        q = self.q
        items = q.CGWindowListCopyWindowInfo(
            q.kCGWindowListOptionOnScreenOnly | q.kCGWindowListExcludeDesktopElements,
            q.kCGNullWindowID) or []
        windows = []
        for item in items:
            bounds = item.get(q.kCGWindowBounds, {})
            if (int(item.get(q.kCGWindowLayer, -1)) != 0 or
                    float(item.get(q.kCGWindowAlpha, 1)) <= 0 or
                    bounds.get("Width", 0) < 100 or bounds.get("Height", 0) < 100):
                continue
            pid = int(item[q.kCGWindowOwnerPID])
            app = self.appkit.NSRunningApplication.runningApplicationWithProcessIdentifier_(pid)
            bundle_id = str(app.bundleIdentifier() or "") if app else ""
            windows.append(WindowInfo(
                int(item[q.kCGWindowNumber]), pid, str(item.get(q.kCGWindowName, "")),
                str(item.get(q.kCGWindowOwnerName, "")), bundle_id,
                Rect(float(bounds["X"]), float(bounds["Y"]),
                     float(bounds["Width"]), float(bounds["Height"]))))
        return windows

    def get_window(self, window_id):
        return next((w for w in self.list_windows() if w.window_id == window_id), None)

    def frontmost_pid(self):
        app = self.appkit.NSWorkspace.sharedWorkspace().frontmostApplication()
        return int(app.processIdentifier()) if app else None

    def is_front_window(self, target):
        # WindowServer returns windows front-to-back. Stop if an ordinary window
        # intersects our target, including another window from the same process.
        for window in self.list_windows():
            if window.window_id == target.window_id:
                return True
            a, b = window.bounds, target.bounds
            if a.x < b.x + b.width and b.x < a.x + a.width and a.y < b.y + b.height and b.y < a.y + a.height:
                return False
        return False

    def physical_escape_pressed(self):
        return bool(self.q.CGEventSourceKeyState(self.q.kCGEventSourceStateHIDSystemState, KEY_CODES["esc"]))

    @staticmethod
    def _await_completion(invoke, timeout=8):
        completed = threading.Event()
        result = {}

        def callback(value, error):
            result["value"], result["error"] = value, error
            completed.set()

        invoke(callback)
        if not completed.wait(timeout):
            raise BackendError("ScreenCaptureKit timed out waiting for macOS")
        if result.get("error") is not None:
            raise BackendError(f"ScreenCaptureKit: {result['error']}")
        if result.get("value") is None:
            raise BackendError("ScreenCaptureKit returned an empty result")
        return result["value"]

    def capture_window(self, window):
        import numpy as np
        import cv2

        sc = self.sc
        content_filter = self._filters.get(window.window_id)
        if content_filter is None:
            content = self._await_completion(lambda cb: sc.SCShareableContent.
                getShareableContentExcludingDesktopWindows_onScreenWindowsOnly_completionHandler_(True, True, cb))
            target = next((w for w in content.windows() if int(w.windowID()) == window.window_id), None)
            if target is None:
                raise BackendError("The selected window is not available to ScreenCaptureKit")
            content_filter = sc.SCContentFilter.alloc().initWithDesktopIndependentWindow_(target)
            self._filters[window.window_id] = content_filter

        scale = float(content_filter.pointPixelScale())
        config = sc.SCStreamConfiguration.alloc().init()
        config.setWidth_(round(window.bounds.width * scale))
        config.setHeight_(round(window.bounds.height * scale))
        config.setShowsCursor_(False)
        config.setCapturesAudio_(False)
        config.setScalesToFit_(False)
        config.setIgnoreShadowsSingleWindow_(True)
        image = self._await_completion(lambda cb: sc.SCScreenshotManager.
            captureImageWithFilter_configuration_completionHandler_(content_filter, config, cb))

        # Encoding through NSBitmapImageRep preserves CGImage color/row order
        # without guessing BGRA layout or bytes-per-row. cv2 decodes to BGR.
        bitmap = self.appkit.NSBitmapImageRep.alloc().initWithCGImage_(image)
        data = bitmap.representationUsingType_properties_(self.appkit.NSBitmapImageFileTypePNG, {})
        if data is None:
            raise BackendError("Could not convert the captured CGImage")
        frame = cv2.imdecode(np.frombuffer(bytes(data), dtype=np.uint8), cv2.IMREAD_COLOR)
        if frame is None:
            raise BackendError("Could not decode the captured image")
        return frame

    def _post(self, event):
        if event is None:
            raise BackendError("macOS could not create an input event")
        # Session events leave hardware key state separate for the Escape guard.
        self.q.CGEventPost(self.q.kCGSessionEventTap, event)

    def post_key(self, code, down, held_keys):
        q = self.q
        event = q.CGEventCreateKeyboardEvent(self._event_source, code, down)
        flags = 0
        for names, flag in (
            (("shift", "rightshift"), q.kCGEventFlagMaskShift),
            (("ctrl", "rightctrl"), q.kCGEventFlagMaskControl),
            (("alt", "rightalt"), q.kCGEventFlagMaskAlternate),
            (("command",), q.kCGEventFlagMaskCommand),
        ):
            if any(name in held_keys for name in names):
                flags |= flag
        if event is not None:
            q.CGEventSetFlags(event, flags)
        self._post(event)

    def _mouse_constants(self, button):
        q = self.q
        return {
            "left": (q.kCGMouseButtonLeft, q.kCGEventLeftMouseDown, q.kCGEventLeftMouseUp, q.kCGEventLeftMouseDragged),
            "right": (q.kCGMouseButtonRight, q.kCGEventRightMouseDown, q.kCGEventRightMouseUp, q.kCGEventRightMouseDragged),
            "middle": (q.kCGMouseButtonCenter, q.kCGEventOtherMouseDown, q.kCGEventOtherMouseUp, q.kCGEventOtherMouseDragged),
        }[button]

    def post_move(self, point, dragging=None):
        q = self.q
        button, _, _, drag_type = self._mouse_constants(dragging or "left")
        event = q.CGEventCreateMouseEvent(self._event_source, drag_type if dragging else q.kCGEventMouseMoved, point, button)
        self._post(event)

    def post_button(self, point, button, down):
        q = self.q
        number, down_type, up_type, _ = self._mouse_constants(button)
        event = q.CGEventCreateMouseEvent(self._event_source, down_type if down else up_type, point, number)
        if event is not None:
            q.CGEventSetIntegerValueField(event, q.kCGMouseEventClickState, 1)
        self._post(event)

    def post_scroll(self, delta):
        q = self.q
        self._post(q.CGEventCreateScrollWheelEvent(self._event_source, q.kCGScrollEventUnitLine, 1, delta))
