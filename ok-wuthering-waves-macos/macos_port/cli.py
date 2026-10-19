"""Explicit CLI for native capture diagnostics and upstream game tasks."""
from __future__ import annotations

import argparse
from dataclasses import asdict
import json
import logging
import math
import os
from pathlib import Path
import platform
import sys
import time

from .backend import BackendError, MacOSBackend, normalize_key
from .geometry import Insets

ROOT = Path(__file__).resolve().parents[1]


def nonnegative(text):
    value = float(text)
    if not math.isfinite(value) or value < 0:
        raise argparse.ArgumentTypeError("Must be finite and nonnegative")
    return value


def positive(text):
    value = nonnegative(text)
    if value == 0:
        raise argparse.ArgumentTypeError("Must be positive")
    return value


def crop_insets(text):
    try:
        return Insets(*(float(value) for value in text.split(","))) if len(text.split(",")) == 4 else _bad_crop()
    except ValueError as exc:
        raise argparse.ArgumentTypeError(str(exc)) from exc


def _bad_crop():
    raise ValueError("Use TOP,RIGHT,BOTTOM,LEFT in logical desktop points")


def parser():
    root = argparse.ArgumentParser(description="Experimental native Apple silicon OK-WW runner")
    root.add_argument("--debug", action="store_true", help="Show exception tracebacks")
    commands = root.add_subparsers(dest="command", required=True)
    doctor = commands.add_parser("doctor", help="Check platform, dependencies and macOS permissions; sends no input")
    doctor.add_argument("--request-permissions", action="store_true")
    commands.add_parser("windows", help="List visible windows and IDs; sends no input")
    listing = commands.add_parser("list-tasks", help="List configured task classes; sends no input")
    listing.add_argument("--language", choices=("en_US", "zh_CN", "zh_TW"), default="en_US")
    for command in ("capture", "input-test", "run"):
        sub = commands.add_parser(command)
        sub.add_argument("--window-id", type=int)
        sub.add_argument("--pid", type=int)
        sub.add_argument("--bundle-id")
        sub.add_argument("--title", default="Wuthering Waves")
        sub.add_argument("--crop", type=crop_insets, default=Insets(), metavar="T,R,B,L")
        sub.add_argument("--countdown", type=nonnegative, default=5, help="Seconds to focus the game before starting")
        if command == "capture":
            sub.add_argument("--output", type=Path, default=Path("screenshots/macos-capture.png"))
        elif command == "input-test":
            sub.add_argument("--key", required=True, help="One physical key, e.g. b to toggle the bag")
        else:
            sub.add_argument("--task", help="One-time task class from list-tasks")
            sub.add_argument("--trigger", action="append", default=[], help="Trigger class; repeat to enable several")
            sub.add_argument("--duration", type=positive, help="Stop after this many seconds; strongly recommended initially")
            sub.add_argument("--language", choices=("en_US", "zh_CN", "zh_TW"), default="en_US")
            sub.add_argument("--settings", type=Path, help='JSON {"tasks": {"Class": {...}}, "globals": {"Group": {...}}}')
    return root


def read_settings(path):
    if path is None:
        return {}, {}
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or set(data) - {"tasks", "globals"}:
        raise ValueError("Settings must be an object containing only tasks and/or globals")
    groups = (data.get("tasks", {}), data.get("globals", {}))
    if any(not isinstance(group, dict) or any(not isinstance(value, dict) for value in group.values())
           for group in groups):
        raise ValueError("Each settings group must map names to configuration objects")
    return groups


def doctor(request=False):
    import importlib.util
    result = {"system": platform.system(), "macos": platform.mac_ver()[0],
              "architecture": platform.machine(), "python": platform.python_version(),
              "dependencies": {name: importlib.util.find_spec(name) is not None for name in
                               ("numpy", "cv2", "PIL", "psutil", "requests", "onnxruntime",
                                "onnxocr", "AppKit", "Quartz", "ApplicationServices", "ScreenCaptureKit")}}
    version = result["macos"].split(".")[0]
    result["supported_platform"] = (result["system"] == "Darwin" and result["architecture"] == "arm64"
                                     and bool(version) and int(version) >= 14)
    if result["supported_platform"]:
        try:
            result["permissions"] = MacOSBackend().check_permissions(request=request)
        except BackendError as exc:
            result["error"] = str(exc)
    print(json.dumps(result, indent=2))
    return 0 if (result["supported_platform"] and all(result["dependencies"].values())
                 and all(result.get("permissions", {"missing": False}).values())) else 1


def countdown(seconds):
    print(f"Focus the selected game window now. Starting in {seconds:g} seconds. Physical Escape stops automation.", flush=True)
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        time.sleep(min(0.1, max(0, deadline - time.monotonic())))


def execute(args):
    if args.command == "doctor":
        return doctor(args.request_permissions)
    if args.command == "list-tasks":
        from .config import build_config
        config = build_config(args.language)
        for kind in ("onetime", "trigger"):
            for _, name in config[kind + "_tasks"]:
                print(f"{kind:8} {name}")
        return 0
    if platform.system() != "Darwin" or platform.machine() != "arm64":
        raise BackendError("Use this launcher with native arm64 Python on macOS 14 or newer")
    if args.command == "windows":
        print(json.dumps([asdict(window) for window in MacOSBackend().list_windows()], indent=2, ensure_ascii=False))
        return 0
    if args.command == "run" and not args.task and not args.trigger:
        raise ValueError("run requires --task or --trigger; no tasks are enabled automatically")
    if args.command == "input-test":
        normalize_key(args.key)  # validate before countdown or input
    backend = MacOSBackend(window_id=args.window_id, pid=args.pid, bundle_id=args.bundle_id,
                           title_contains=args.title, crop=args.crop)
    runtime = None
    try:
        required = backend.check_permissions()
        if not required.get("screen_recording") or (args.command != "capture" and not required.get("accessibility")):
            raise BackendError("Required macOS permissions are missing. Run doctor --request-permissions, grant permissions in System Settings, then restart Terminal.")
        window = backend.select_window()
        print(f"Selected window {window.window_id}: {window.title or window.owner_name}", flush=True)
        if args.command == "run":
            from .config import build_config
            from .framework import Runtime
            task_settings, global_settings = read_settings(args.settings)
            runtime = Runtime(build_config(args.language), backend,
                              task_config=task_settings, global_config=global_settings)
        countdown(args.countdown)
        frame = backend.capture()
        if args.command == "capture":
            import cv2
            args.output.parent.mkdir(parents=True, exist_ok=True)
            if not cv2.imwrite(str(args.output), frame):
                raise BackendError(f"Could not write {args.output}")
            print(f"Saved {frame.shape[1]}x{frame.shape[0]} capture to {args.output}")
        elif args.command == "input-test":
            backend.send_key(args.key, down_time=0.05)
            print(f"Posted one {args.key!r} key press. Check whether the game responded; posting success alone cannot confirm acceptance.")
        else:
            runtime.run(args.task, triggers=args.trigger, duration=args.duration)
            print("Selected run ended.")
        return 0
    finally:
        if runtime is not None:
            runtime.close()
        backend.stop()


def main(argv=None):
    args = parser().parse_args(argv)
    # Resolve user paths before switching to the upstream asset-relative working directory.
    for name in ("output", "settings"):
        value = getattr(args, name, None)
        if value is not None:
            setattr(args, name, value.expanduser().resolve())
    os.chdir(ROOT)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    try:
        return execute(args)
    except KeyboardInterrupt:
        print("Stopped.", file=sys.stderr)
        return 130
    except Exception as exc:
        if args.debug:
            logging.exception("macOS runner failed")
        else:
            print(f"Error: {exc}", file=sys.stderr)
        return 1
