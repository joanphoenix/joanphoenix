"""Window/image coordinates, independent of macOS and the vision framework.

Quartz window bounds and mouse events both use desktop points, with the origin
at the top left of the main display. Captured images use pixels. Never multiply
desktop coordinates by the Retina scale: scale only the image-local offset.
"""

from dataclasses import dataclass
import math


@dataclass(frozen=True)
class Rect:
    x: float
    y: float
    width: float
    height: float

    def __post_init__(self):
        if not all(math.isfinite(value) for value in (self.x, self.y, self.width, self.height)):
            raise ValueError("Rectangle values must be finite")
        if self.width <= 0 or self.height <= 0:
            raise ValueError("Rectangle dimensions must be positive")

    def same_as(self, other, tolerance=0.01):
        return all(abs(a - b) <= tolerance for a, b in zip(
            (self.x, self.y, self.width, self.height),
            (other.x, other.y, other.width, other.height),
        ))


@dataclass(frozen=True)
class Insets:
    """Explicit top/right/bottom/left content trim in desktop points."""

    top: float = 0
    right: float = 0
    bottom: float = 0
    left: float = 0

    def __post_init__(self):
        if not all(math.isfinite(value) and value >= 0 for value in
                   (self.top, self.right, self.bottom, self.left)):
            raise ValueError("Crop insets must be finite and nonnegative")


@dataclass(frozen=True)
class FrameGeometry:
    """Mapping for the actual returned pixels, including rounded crop edges."""

    bounds: Rect
    full_width: int
    full_height: int
    left: int
    top: int
    right: int
    bottom: int

    @classmethod
    def from_capture(cls, bounds, image_width, image_height, crop=Insets()):
        if image_width <= 0 or image_height <= 0:
            raise ValueError("Captured image dimensions must be positive")
        if crop.left + crop.right >= bounds.width or crop.top + crop.bottom >= bounds.height:
            raise ValueError("Crop removes the entire window")
        sx, sy = image_width / bounds.width, image_height / bounds.height
        left, top = round(crop.left * sx), round(crop.top * sy)
        right = image_width - round(crop.right * sx)
        bottom = image_height - round(crop.bottom * sy)
        if right <= left or bottom <= top:
            raise ValueError("Crop removes the entire captured image")
        return cls(bounds, image_width, image_height, left, top, right, bottom)

    @property
    def width(self):
        return self.right - self.left

    @property
    def height(self):
        return self.bottom - self.top

    @property
    def scale_x(self):
        return self.full_width / self.bounds.width

    @property
    def scale_y(self):
        return self.full_height / self.bounds.height

    def to_desktop(self, x, y):
        if not math.isfinite(x) or not math.isfinite(y):
            raise ValueError("Input coordinates must be finite")
        if not (0 <= x < self.width and 0 <= y < self.height):
            raise ValueError(f"Input ({x}, {y}) is outside captured content {self.width}x{self.height}")
        return (self.bounds.x + (self.left + x) / self.scale_x,
                self.bounds.y + (self.top + y) / self.scale_y)
