# Pinned ok-script core

These files are from https://github.com/ok-oldking/ok-script at commit
`428bcd563292ac6451c84c0222e6b790d468215f`.

The subset includes the original task executor, task classes, template matching,
configuration, event bus, and supporting utilities. Qt, browser, Windows capture,
and Windows input runtime packages are not included. The app's macOS entry point
loads this subset through `macos_port.framework.load_framework()`.

Three portability changes are applied:

1. `ok/task/TaskExecutor.py` imports the ratio helper from the platform-neutral
   `ok.util.collection` module instead of importing Windows window APIs.
2. `ok/util/process.py` only calls `SetThreadExecutionState` on Windows.
3. `ok/task/TaskExecutor.py` supports synchronous OCR initialization, enabled by
   the Mac adapter, so initialization errors propagate before input and native
   ONNX Runtime initialization cannot race Python process shutdown.

The upstream license is retained as `OK_SCRIPT_LICENSE.txt`. This is a source
subset for the macOS preview, not a general replacement installation of ok-script.
