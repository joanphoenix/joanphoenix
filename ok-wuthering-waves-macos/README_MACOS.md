# OK-WW native macOS preview

This is an **experimental source port** for the native macOS edition of Wuthering Waves on Apple silicon, including M5 Pro. It reuses the upstream task logic, recognition assets and task engine, with a new foreground-only macOS capture/input backend and command-line launcher.

**It has not been run on a Mac or against the live game.** Automated tests and model smoke checks pass on Linux, and dependency resolution succeeds for macOS arm64. Actual ScreenCaptureKit frames, input acceptance and combat timing still need testing on your machine. This is not a signed `.app` or a finished replacement for the Windows release.

## Install

Requirements: macOS 14 or newer, native **arm64 Python 3.12**, the native Mac game, and an internet connection for Python dependencies. Install Python 3.12 from python.org or with `brew install python@3.12` if you already use Homebrew. Do not run Terminal/Python under Rosetta.

Extract the archive, open Terminal in its `ok-ww-macos-preview` directory, and run:

```bash
bash install_macos.sh
.venv/bin/python main_macos.py doctor --request-permissions
```

The installer creates a project-local `.venv`; it does not install Windows `ok-script`, Qt or OpenVINO. Original recognition assets are included and checked against the pinned Git tree. Missing or damaged assets are downloaded and verified before replacement.

In **System Settings → Privacy & Security**, grant Screen Recording (called Screen & System Audio Recording on some macOS versions) and Accessibility to the application macOS identifies for this command, typically Terminal or your Python host. Quit and reopen that host after changing permissions. Run `doctor` again. The app captures only the selected window and does not capture audio.

## Validate capture first

Open the game yourself. Start with a visible, borderless/windowed **16:9 game content area**, at least 1280×720 captured pixels. The screen's overall resolution is not the same as the game content resolution. Close overlays and dialogs over the game.

```bash
.venv/bin/python main_macos.py windows
.venv/bin/python main_macos.py capture --window-id 123 --output screenshots/mac.png
```

Replace `123` with the game window ID from `windows`. After issuing the command, switch focus to the game during the five-second countdown. The capture command sends no input. Inspect `screenshots/mac.png`: it should contain the rendered game, be correctly oriented, and have no title bar, borders or letterboxing in the gameplay area.

If needed, trim using **desktop points**, not Retina image pixels:

```bash
.venv/bin/python main_macos.py capture --window-id 123 --crop 28,0,0,0 --output screenshots/mac.png
```

Insets are top,right,bottom,left. `28` is only an example, not an automatic title-bar measurement. Supply the same crop to subsequent input/run commands. The backend maps actual captured pixels to desktop points, including Retina scaling and displays with negative origins. Moving/resizing the window stops the session; capture again after changing its geometry.

## Validate one key, then one short task

While in the game world, test a single known key such as your Bag binding:

```bash
.venv/bin/python main_macos.py input-test --window-id 123 --key b
```

Check whether the bag actually opens. A successful event-post message **does not prove** the game accepted the input. If it does not respond, stop here and retain the `doctor` output for investigation.

List the available task class names:

```bash
.venv/bin/python main_macos.py list-tasks
```

Close the bag and begin with a short pickup trial near a normal pickup prompt:

```bash
.venv/bin/python main_macos.py run --window-id 123 --trigger AutoPickTask --duration 15
```

No task or trigger runs unless selected explicitly. Repeat `--trigger` to enable several. A one-time task uses `--task`, for example:

```bash
.venv/bin/python main_macos.py run --window-id 123 --task FarmEchoTask --duration 60 --settings settings.example.json
```

Task-specific starting conditions remain those of the upstream project. The example limits the repeat count to one; it does not automatically choose a boss. Duration bounds the session, so it may interrupt a task before completion. Use `--language zh_CN` or `--language zh_TW` when appropriate; the default is English. `ChangeEchoTask` is Simplified-Chinese-only; `EnhanceEchoTask` supports Simplified and Traditional Chinese as in upstream.

**Physical Escape stops automation.** Switching to another app also stops it and releases held keys/buttons. Ctrl-C in Terminal stops the process. A stopped session does not auto-resume. In-game Escape events sent by the tool use the session event stream, while the emergency check reads hardware key state; confirm this behavior on your Mac during the first trial. Changing game resolution or display scaling also requires a new capture/session.

## Configuration and scope

`settings.example.json` shows task/global overrides. Names must match upstream configuration keys. User overrides and defaults are stored in `configs-macos/`. Keys use physical US-layout positions; remapped game controls need matching `Game Hotkey` settings. Text entry/account switching is not implemented.

Included: original daily/farming/combat/dialog/pickup task classes where compatible with the selected language, original templates and echo model, ONNX Runtime CPU OCR/inference, explicit window selection, crop/scaling, permission checks, input cleanup, and a command-line runner.

Not included: Windows GUI/custom character editor, background or minimized automation, Windows multi-account login controls, Windows mouse-restoration task, automatic game launch/close, scheduled jobs, tray controls, overlays, Windows updater, `.app` signing/notarization, or CoreML/Metal acceleration. Runtime disables task-triggered exit and related Windows options. CPU inference runs natively on arm64; M5 Pro-specific performance has not been measured.

ScreenCaptureKit's screenshot API is used for each requested frame, with lossless conversion to BGR for the original OpenCV logic. This favors a straightforward initial implementation; throughput and high-frequency combat responsiveness remain unmeasured. A streaming ScreenCaptureKit backend may be needed after profiling. Mac rendering or UI differences may also require new templates.

## Verification performed

- 29 automated tests passed: coordinate/crop validation, focus/resize/occlusion/Escape stops, held input cleanup, asset integrity, app compatibility, CLI validation, original task initialization, executor success/error propagation, explicit trigger selection, and an original AutoPickTask run against a blank simulated capture.
- All 51 bundled recognition asset files match the pinned upstream Git blob hashes and sizes.
- Actual ONNX echo detection and OCR models loaded and inferred on blank images using CPU on Linux.
- Python 3.12 arm64 macOS wheels resolved for all pinned direct dependencies and their transitive dependencies.
- Python compilation and installer shell syntax passed.
- No native Mac API, permission prompt, actual game rendering, M5 Pro performance or live gameplay test was performed.

Run the automated suite after installation with:

```bash
.venv/bin/python -m unittest discover -s tests_macos -v
```

For a failing command, put `--debug` before the subcommand to display a traceback. Save the diagnostic output and capture locally; those are the next evidence needed for Mac-specific fixes.

## Source and license

Game source: https://github.com/ok-oldking/ok-wuthering-waves at `f9d808e6e3c60cb65c6e0535fc9fa9eac7e779d3`.

Vendored engine core: https://github.com/ok-oldking/ok-script at `428bcd563292ac6451c84c0222e6b790d468215f`. `vendor/README.md` describes the focused engine changes. The Mac adapter avoids loading the Windows DeviceManager or GUI; it uses the original TaskManager, TaskExecutor and FeatureSet.

Original licenses are preserved in `LICENSE.txt` and `vendor/OK_SCRIPT_LICENSE.txt`. New port code is provided under the same AGPL-3.0 license as the game tool. This preview is an independent modification, not an official upstream release. Source files for unavailable Windows features remain in the archive but are excluded from the Mac task configuration.
