"""Run the pinned upstream task engine with a foreground macOS device.

The bundled engine retains upstream task scheduling, template matching, OCR,
configuration and task classes. This adapter replaces only platform services.
"""
from __future__ import annotations

import copy
import importlib
import logging
from pathlib import Path
import sys
import threading
import time
from types import SimpleNamespace


def load_framework():
    """Prefer the audited source snapshot over a globally installed ok-script."""
    vendor = Path(__file__).resolve().parents[1] / "vendor"
    existing = sys.modules.get("ok")
    if existing is not None:
        origin = Path(existing.__file__).resolve()
        if not origin.is_relative_to(vendor):
            raise RuntimeError("A different ok-script is already loaded; start a fresh Python process.")
    if str(vendor) not in sys.path:
        sys.path.insert(0, str(vendor))


class CaptureAdapter:
    name = "macOS foreground"

    def __init__(self, backend, exit_event):
        self.backend = backend
        self.exit_event = exit_event

    @property
    def width(self):
        return self.backend.width

    @property
    def height(self):
        return self.backend.height

    def get_frame(self):
        if self.exit_event.is_set():
            return None
        self.backend.check_guard()
        return self.backend.capture()

    def connected(self):
        return self.backend.window is not None and not self.exit_event.is_set()

    def clickable(self):
        self.backend.check_guard()
        return True

    def get_name(self):
        return self.name

    def close(self):
        self.backend.release_all()


class InteractionAdapter:
    """Translate upstream input names into backend calls in captured pixels."""

    def __init__(self, backend, capture):
        self.backend = backend
        self.capture = capture

    def should_capture(self):
        self.backend.check_guard()
        return True

    def on_run(self):
        self.backend.check_guard()

    def on_destroy(self):
        self.backend.release_all()

    def _position(self, x, y):
        # Upstream combat clicks use (-1, -1) for a click without relocation.
        # A known point inside the game is safer than the desktop cursor.
        if x == -1 and y == -1:
            return self.capture.width / 2, self.capture.height / 2
        if x < 0 or y < 0:
            raise ValueError("Both click coordinates must be inside the capture.")
        return x, y

    def click(self, x=-1, y=-1, move_back=False, name=None, down_time=0.02, move=True, key="left"):
        x, y = self._position(x, y)
        self.backend.click(x, y, button=key, down_time=down_time)

    def mouse_down(self, x=-1, y=-1, name=None, key="left"):
        x, y = self._position(x, y)
        self.backend.mouse_down(x, y, button=key)

    def mouse_up(self, key="left"):
        self.backend.mouse_up(button=key)

    def move(self, x, y):
        self.backend.move(x, y)

    def scroll(self, x, y, scroll_amount):
        self.backend.scroll(scroll_amount, x=x, y=y)

    def send_key(self, key, down_time=0.02):
        self.backend.send_key(str(key), down_time=down_time)

    def send_key_down(self, key):
        self.backend.key_down(str(key))

    def send_key_up(self, key):
        self.backend.key_up(str(key))

    def back(self):
        self.send_key("esc")

    def input_text(self, text):
        raise NotImplementedError("Text entry and account login are not supported by this macOS preview.")

    def swipe(self, from_x, from_y, to_x, to_y, duration, settle_time=0):
        seconds = max(0, duration / 1000)
        steps = max(1, int(seconds * 60))
        self.backend.mouse_down(from_x, from_y)
        try:
            for step in range(1, steps + 1):
                self.backend.move(from_x + (to_x - from_x) * step / steps,
                                  from_y + (to_y - from_y) * step / steps)
                time.sleep(seconds / steps)
        finally:
            self.backend.mouse_up()
        if settle_time:
            time.sleep(settle_time)


class WindowAdapter:
    """Compatibility metadata; it never activates or resizes another window."""

    def __init__(self, backend):
        self.backend = backend

    @property
    def exists(self):
        return self.backend.window is not None

    @property
    def visible(self):
        return self.is_foreground()

    @property
    def hwnd_title(self):
        return self.backend.window.title if self.backend.window else ""

    title = hwnd_title

    @property
    def width(self):
        return self.backend.width

    @property
    def height(self):
        return self.backend.height

    def is_foreground(self):
        self.backend.check_guard()
        return True

    def bring_to_front(self):
        return self.is_foreground()


class DeviceAdapter:
    supported_ratio = 16 / 9

    def __init__(self, backend, exit_event):
        self.backend = backend
        self.capture_method = CaptureAdapter(backend, exit_event)
        self.interaction = InteractionAdapter(backend, self.capture_method)
        self.hwnd_window = WindowAdapter(backend)

    def get_preferred_device(self):
        return {"device": "macos", "capture": "macos", "connected": self.capture_method.connected()}

    def update_resolution_for_hwnd(self):
        pass

    def stop_hwnd(self):
        raise RuntimeError("Closing the game is disabled in the macOS preview.")

    def ensure_capture(self, config):
        if config:
            raise RuntimeError("Changing capture devices from a task is unsupported on macOS.")

    update_capture = ensure_capture


class Runtime:
    """One explicit invocation of original tasks with fail-closed native input."""

    def __init__(self, config, backend, *, task_config=None, global_config=None):
        load_framework()
        from ok import og
        from ok.core.events import communicate
        from ok.core.task_manager import TaskManager
        from ok.feature.FeatureSet import FeatureSet
        from ok.task.TaskExecutor import TaskExecutor
        from ok.util.config import Config
        from ok.util.GlobalConfig import GlobalConfig
        from ok.util.handler import ExitEvent

        self.backend = backend
        self.exit_event = ExitEvent()
        self._closed = False
        self._failed = None
        self._done = set()
        self.config = copy.deepcopy(config)
        self.config.pop("blur_area", None)
        self.config["custom_tasks"] = False
        self.config["gui"] = None
        self.config["ocr_init_sync"] = True
        self.config["config_folder"] = self.config.get("config_folder", "configs-macos")
        self.config["locale"] = self.config.get("locale", "en_US")
        Config.config_folder = self.config["config_folder"]

        self.global_config = GlobalConfig(self.config.get("global_configs", []))
        for group, values in (global_config or {}).items():
            self._apply_overrides(self.global_config.get_config(group), values, group)
        basic = self.global_config.get_config("Basic Options")
        # These options remain visible in upstream config data but are not
        # available in the foreground runner, including when restored from disk.
        for key, value in {
            "Auto Start Game When App Starts": False,
            "Mute Game while in Background": False,
            "Auto Resize Game Window": False,
            "Kill Launcher After Start": False,
            "Exit App when Game Exits": False,
            "Use DirectML": "No",
            "Enable Blur": False,
        }.items():
            dict.__setitem__(basic, key, value)

        self.device_manager = DeviceAdapter(backend, self.exit_event)
        self.debug = False
        self.locale = self.config["locale"]
        self.start_controller = SimpleNamespace(start_device=self.backend.check_guard)
        self._events = communicate
        og.ok = self
        og.config = self.config
        og.app = self
        og.global_config = self.global_config
        og.device_manager = self.device_manager
        og.use_dml = False
        my_app = self.config.get("my_app")
        og.my_app = (getattr(importlib.import_module(my_app[0]), my_app[1])(self.exit_event)
                     if my_app else None)
        matching = self.config.get("template_matching")
        features = None
        if matching:
            features = FeatureSet(
                False, matching["coco_feature_json"],
                default_horizontal_variance=matching.get("default_horizontal_variance", 0.002),
                default_vertical_variance=matching.get("default_vertical_variance", 0.002),
                default_threshold=matching.get("default_threshold", 0.8),
                feature_processor=matching.get("feature_processor"),
                hcenter_features=matching.get("hcenter_features"),
                vcenter_features=matching.get("vcenter_features"))
        self.executor = TaskExecutor(
            self.device_manager, exit_event=self.exit_event,
            wait_until_settle_time=self.config.get("wait_until_settle_time", 0),
            feature_set=features, config_folder=Config.config_folder,
            global_config=self.global_config, config=self.config)
        og.executor = self.executor
        self.task_manager = TaskManager(
            self.executor, self,
            trigger_tasks=self.config.get("trigger_tasks", []),
            onetime_tasks=self.config.get("onetime_tasks", []),
            scene=self.config.get("scene"))
        og.task_manager = self.task_manager
        known = {task.__class__.__name__: task for task in self.executor.get_all_tasks()}
        for name, values in (task_config or {}).items():
            if name not in known:
                raise ValueError(f"Unknown task configuration: {name}")
            self._apply_overrides(known[name].config, values, name)
        for task in self.executor.get_all_tasks():
            task._enabled = False
            task.exit_after_task = False
            task.support_schedule_task = False
            if "Exit After Task" in task.config:
                dict.__setitem__(task.config, "Exit After Task", False)
        communicate.notification.connect(self._on_notification)
        communicate.task_done.connect(self._on_done)
        communicate.quit.connect(self._on_quit)

    @staticmethod
    def _apply_overrides(config, values, label):
        if not isinstance(values, dict):
            raise ValueError(f"Configuration for {label} must be an object.")
        for key, value in values.items():
            if key not in config or key.startswith("_"):
                raise ValueError(f"Unknown or private configuration key: {label}.{key}")
            if key == "Exit After Task" and value:
                raise ValueError("Exit After Task is unsupported on macOS.")
            # The upstream validator checks task-specific value constraints.
            validator = getattr(config, "validator", None)
            if validator:
                valid, message = validator(key, value)
                if not valid:
                    raise ValueError(message or f"Invalid configuration: {label}.{key}")
            config[key] = value

    def tr(self, message):
        return message

    def get_overlay_view(self):
        return None

    def _on_notification(self, message, title=None, error=False, *args):
        if error:
            self._failed = RuntimeError(f"{title or 'Task'}: {message}")
        logging.getLogger(__name__).log(logging.ERROR if error else logging.INFO, "%s: %s", title, message)

    def _on_done(self, task):
        self._done.add(task.__class__.__name__)

    def _on_quit(self, *args):
        self.exit_event.set()

    def list_tasks(self):
        return [{"class_name": task.__class__.__name__, "name": task.name,
                 "kind": "trigger" if task in self.executor.trigger_tasks else "onetime"}
                for task in self.executor.get_all_tasks()]

    def run(self, task=None, *, triggers=None, duration=None):
        if self._closed:
            raise RuntimeError("This runtime has already closed.")
        if duration is not None and duration <= 0:
            raise ValueError("Duration must be positive.")
        one = {t.__class__.__name__: t for t in self.executor.onetime_tasks}
        available_triggers = {t.__class__.__name__: t for t in self.executor.trigger_tasks}
        if not task and not triggers:
            raise ValueError("Select a task or at least one trigger explicitly.")
        if task and task not in one:
            raise ValueError(f"Unknown one-time task: {task}")
        selected_triggers = []
        for name in triggers or []:
            if name not in available_triggers:
                raise ValueError(f"Unknown trigger task: {name}")
            selected_triggers.append(available_triggers[name])
        self.backend.check_guard()
        frame = self.device_manager.capture_method.get_frame()
        height, width = frame.shape[:2]
        if width < 1280 or height < 720 or abs(width / height - 16 / 9) > 0.01:
            raise RuntimeError(f"Capture is {width}x{height}; use a 16:9 game content area of at least 1280x720.")
        self.executor._frame = frame
        deadline = time.monotonic() + duration if duration is not None else None
        disabled_since = None
        try:
            for trigger in selected_triggers:
                trigger._enabled = True
            if task:
                one[task].enable()
            self.executor.start()
            while not self.exit_event.is_set():
                self.backend.check_guard()
                if self._failed:
                    raise self._failed
                if task in self._done:
                    return
                if deadline is not None and time.monotonic() >= deadline:
                    return
                if not self.executor.thread.is_alive():
                    raise RuntimeError("The task executor stopped before completing the selected task.")
                if task and not one[task].enabled and task not in self._done:
                    disabled_since = disabled_since or time.monotonic()
                    if time.monotonic() - disabled_since > 0.2:
                        raise RuntimeError(f"{task} stopped without reporting completion.")
                else:
                    disabled_since = None
                time.sleep(0.05)
            if self._failed:
                raise self._failed
        finally:
            self.close()

    def close(self):
        if self._closed:
            return
        self._closed = True
        self.exit_event.set()
        self.backend.stop()
        if self.executor.thread and self.executor.thread is not threading.current_thread():
            self.executor.thread.join(timeout=2)
        self.executor.destroy()
        self._events.notification.disconnect(self._on_notification)
        self._events.task_done.disconnect(self._on_done)
        self._events.quit.disconnect(self._on_quit)
