# Validation record

This preview targets native arm64 Python 3.12 on macOS 14+. Validation below ran
in a Linux x86_64 workspace, without a Mac, game process or native input injection.

| Check | Result |
| --- | --- |
| `python -m unittest discover -s tests_macos -v` | 29 tests passed |
| Original task initialization | 13 English-enabled tasks initialized, all disabled by default |
| Original AutoPickTask on blank fake capture | Ran without input or task error |
| Original executor success/error paths | Synthetic task input routed to fake native device; failures propagated |
| OCR and echo ONNX model smoke inference | Models loaded and inferred on blank images using CPU |
| Bundled asset verification | All 51 files matched pinned upstream size and Git blob SHA-1 |
| macOS arm64 wheel resolution | All direct/transitive dependencies downloaded for CPython 3.12, macOS 14 arm64 |
| Python compilation / `bash -n install_macos.sh` | Passed |
| Native permissions / ScreenCaptureKit / Quartz / actual game / M5 Pro performance | Not tested |

The native boundary is mocked in automated tests. Passing those tests does not
establish that the game accepts synthetic input, that the Mac UI matches the
Windows templates, or that screenshot latency is suitable for combat.

The initial OCR initialization race discovered during validation was fixed by
using synchronous model initialization in the CLI. Engine failures now reach the
command before gameplay starts, and initialization cannot race process shutdown.

See README_MACOS.md for the ordered native acceptance checks: doctor, list
windows, inspect a capture, test one key, then run a short selected task.
