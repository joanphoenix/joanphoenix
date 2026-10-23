# ok-wuthering-waves-macos-port

Native **macOS Apple Silicon (M1/M2/M3/M4/M5 Pro)** port of the automation tool for *Wuthering Waves* (`ok-wuthering-waves` & `ok-script`). Fully synced with upstream **v3.7.7** (Suoming & Douling trigram combat).

---

## Highlights of the macOS Port

- **Native macOS UI Optimization**:
  - Apple San Francisco typography (`.AppleSystemUIFont`, `PingFang SC`, `Menlo`) across Qt and Web UI.
  - Native macOS Traffic Light window controls (Close, Minimize, Zoom) properly aligned and spaced in the unified title bar.
  - Native macOS Global Menu Bar integration with standard shortcuts:
    - **Preferences**: `Cmd + ,`
    - **Quit**: `Cmd + Q`
    - **Close Window**: `Cmd + W`
    - **Tab Navigation**: `Cmd + 1` through `Cmd + 5`
  - Dynamic System Accent Color support (reads your macOS accent preference via `NSColor.controlAccentColor`).
  - Native Dark/Light theme switching and Dock click reactivation.
  - Zero font alias resolution delays or DPI rounding policy warnings.

- **High-Performance macOS Capture & Inference**:
  - **Capture**: Native `CoreGraphics` / `Quartz` screen capture pipeline replacing Windows BitBlt/GDI/WGC.
  - **Inference**: YOLOv8 and PaddleOCR inference running natively on Apple Silicon Metal / CoreML.
  - **Process Detection**: Direct integration with the native macOS client (`Client-Mac-Shipping`).

- **Upstream Gameplay & Character Support (v3.7.7)**:
  - Full support for **Suoming (锁瞑)** with heavy attack rotation and burst sequences.
  - Dynamic Trigram (卦象栏) detection for **Douling (卜灵)** charged attacks.
  - Safe auto-combat state resets across disable/restart and healer switch lockout fallbacks.

---

## Requirements

- **Operating System**: macOS 13.0+ (Ventura, Sonoma, Sequoia, or later)
- **Architecture**: Apple Silicon (`arm64` — M1, M2, M3, M4, M5 Pro, Max, Ultra)
- **Python**: Python 3.10+ (Python 3.12 recommended)
- **Game**: *Wuthering Waves* installed at `/Applications/Wuthering Waves.app`

---

## Quick Start

1. **Clone the Repository**:
   ```bash
   git clone git@github.com:joanphoenix/ok-wuthering-waves-macos-port.git
   cd ok-wuthering-waves-macos-port
   ```

2. **Launch the Native Qt Application**:
   ```bash
   chmod +x run_macos.sh
   ./run_macos.sh
   ```
   *The launcher will automatically configure the Python virtual environment and native dependencies on first run.*

3. **Alternative Launch Modes**:
   - **Browser Web UI Mode**:
     ```bash
     ./run_macos.sh --web
     ```
   - **Debug Mode**:
     ```bash
     ./run_macos.sh --debug
     ```

---

## Permissions Notice

Because automation tools require reading the game window content and sending simulated inputs, macOS requires granting permissions:
1. **Screen Recording**: System Settings $\rightarrow$ Privacy & Security $\rightarrow$ Screen Recording $\rightarrow$ Enable Terminal (or your Python / IDE host).
2. **Accessibility**: System Settings $\rightarrow$ Privacy & Security $\rightarrow$ Accessibility $\rightarrow$ Enable Terminal.

---

## License

This project is licensed under the GPL-3.0 License. All original game assets, names, and trademarks belong to Kuro Games.
