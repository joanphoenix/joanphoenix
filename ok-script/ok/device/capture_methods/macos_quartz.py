import threading
import time
import numpy as np

from ok.device.capture_methods.base import BaseWindowsCaptureMethod
from ok.device.capture_methods.bitblt_utils import get_crop_point
from ok.util.logger import Logger

logger = Logger.get_logger(__name__)

try:
    import Quartz
except Exception as e:
    Quartz = None
    logger.warning(f"Failed to import Quartz in macos_quartz: {e}")


class MacOSQuartzCaptureMethod(BaseWindowsCaptureMethod):
    name = "macOS Quartz Window Capture"
    short_description = "native macOS CGWindowListCreateImage"
    description = (
        "\nCaptures the game window directly using macOS CoreGraphics (Quartz). "
        "\nSupports background/occluded windows and Retina displays."
    )

    def __init__(self, hwnd_window):
        super().__init__(hwnd_window)
        self.lock = threading.Lock()
        self._warned_permission = False
        self.exit_event = getattr(hwnd_window, "app_exit_event", None)

    def do_get_frame(self):
        if Quartz is None or self.hwnd_window is None:
            return None

        hwnd = self.hwnd_window.hwnd
        if hwnd <= 0:
            return None

        with self.lock:
            try:
                image_options = (
                    Quartz.kCGWindowImageBoundsIgnoreFraming
                    | Quartz.kCGWindowImageBestResolution
                )
                cg_img = Quartz.CGWindowListCreateImage(
                    Quartz.CGRectNull,
                    Quartz.kCGWindowListOptionIncludingWindow,
                    hwnd,
                    image_options,
                )
                if cg_img is None:
                    if not self._warned_permission:
                        self._warned_permission = True
                        logger.warning(
                            "CGWindowListCreateImage returned None. Ensure Screen Recording permission is granted in System Settings -> Privacy & Security -> Screen & System Audio Recording."
                        )
                    return None

                width = Quartz.CGImageGetWidth(cg_img)
                height = Quartz.CGImageGetHeight(cg_img)
                if width <= 10 or height <= 10:
                    return None

                bytes_per_row = Quartz.CGImageGetBytesPerRow(cg_img)
                provider = Quartz.CGImageGetDataProvider(cg_img)
                if provider is None:
                    return None
                data = Quartz.CGDataProviderCopyData(provider)
                if data is None:
                    return None

                buf = np.frombuffer(data, dtype=np.uint8)
                row_pixels = bytes_per_row // 4
                if buf.size < height * bytes_per_row:
                    return None

                img = buf[: height * bytes_per_row].reshape((height, row_pixels, 4))
                img = img[:, :width, :3].copy()

                # Crop title bar or borders if window frame is larger than client area
                target_w = self.hwnd_window.real_width or self.hwnd_window.width
                target_h = self.hwnd_window.real_height or self.hwnd_window.height

                if target_w > 0 and target_h > 0 and (width > target_w or height > target_h):
                    if self.hwnd_window.real_x_offset != 0 or self.hwnd_window.real_y_offset != 0:
                        x = self.hwnd_window.real_x_offset
                        y = self.hwnd_window.real_y_offset
                    else:
                        x, y = get_crop_point(width, height, target_w, target_h)
                    x = max(0, min(x, width - target_w))
                    y = max(0, min(y, height - target_h))
                    img = img[y : y + target_h, x : x + target_w]

                return img
            except Exception as e:
                logger.error(f"MacOSQuartzCaptureMethod.do_get_frame error: {e}")
                return None

    def get_frame_for_probe(self, timeout=1.0):
        return self.do_get_frame()

    def start_or_stop(self):
        return self.connected()
