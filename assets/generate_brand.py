"""Generate the Rudra Labs brand files.

Run:  python assets/generate_brand.py

Emits the vector sources plus the raster avatars GitHub and Google need - neither
accepts SVG for a profile picture. Geometry is defined once here and both the SVG
and the PNG are drawn from it, so the two can never drift apart.

The mark is an abstracted trishul - Rudra's weapon - built so that it survives
Google's circular avatar crop and still reads at 16 px. It is drawn from
polygons rather than type: a logo must never depend on a font being installed.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import List, Sequence, Tuple

ASSETS = Path(__file__).resolve().parent

INK = "#0A0A0A"
PAPER = "#FFFFFF"

#: Design space. Everything below is in 512x512 and scaled on export.
BOX = 512

#: How far from the centre the artwork may reach, as a fraction of the
#: inscribed circle's radius. Google crops avatars to that circle; 0.78 keeps a
#: visible margin without leaving the mark marooned in empty space.
SAFE_FRACTION = 0.78

Point = Tuple[float, float]
Polygon = List[Point]
#: (x, y, w, h, radius)
RoundRect = Tuple[float, float, float, float, float]


# --------------------------------------------------------------------------- #
# The trishul
# --------------------------------------------------------------------------- #
def _prong(cx: float, half: float, base: float, shoulder: float, tip: float) -> Polygon:
    """One pointed prong: straight sides up to a shoulder, then a point."""
    return [
        (cx - half, base),
        (cx - half, shoulder),
        (cx, tip),
        (cx + half, shoulder),
        (cx + half, base),
    ]


TRISHUL_POLYGONS: List[Polygon] = [
    _prong(cx=256, half=15, base=285, shoulder=125, tip=68),   # centre, tallest
    _prong(cx=163, half=13, base=285, shoulder=155, tip=108),  # left
    _prong(cx=349, half=13, base=285, shoulder=155, tip=108),  # right
]

TRISHUL_RECTS: List[RoundRect] = [
    (138, 278, 236, 32, 16),   # crossbar
    (241, 310, 30, 122, 15),   # shaft
]


# --------------------------------------------------------------------------- #
# Geometry helpers
# --------------------------------------------------------------------------- #
def _vertices(polygons: Sequence[Polygon], rects: Sequence[RoundRect]) -> List[Point]:
    points: List[Point] = [p for poly in polygons for p in poly]
    for x, y, w, h, _ in rects:
        points += [(x, y), (x + w, y), (x, y + h), (x + w, y + h)]
    return points


def _fit(polygons: Sequence[Polygon], rects: Sequence[RoundRect]):
    """Centre the artwork, then scale it to sit inside the safe circle."""
    points = _vertices(polygons, rects)
    min_x = min(p[0] for p in points)
    max_x = max(p[0] for p in points)
    min_y = min(p[1] for p in points)
    max_y = max(p[1] for p in points)

    # 1. move the bounding box centre onto the canvas centre
    dx = BOX / 2 - (min_x + max_x) / 2
    dy = BOX / 2 - (min_y + max_y) / 2

    moved_polys = [[(x + dx, y + dy) for x, y in poly] for poly in polygons]
    moved_rects = [(x + dx, y + dy, w, h, r) for x, y, w, h, r in rects]

    # 2. scale about that centre so the furthest vertex lands on the safe radius
    centre = BOX / 2
    target = centre * SAFE_FRACTION
    reach = max(
        ((px - centre) ** 2 + (py - centre) ** 2) ** 0.5
        for px, py in _vertices(moved_polys, moved_rects)
    )
    k = target / reach

    def sx(v: float) -> float:
        return centre + (v - centre) * k

    fitted_polys = [[(sx(x), sx(y)) for x, y in poly] for poly in moved_polys]
    fitted_rects = [
        (sx(x), sx(y), w * k, h * k, r * k) for x, y, w, h, r in moved_rects
    ]
    return fitted_polys, fitted_rects, reach * k


# --------------------------------------------------------------------------- #
# SVG
# --------------------------------------------------------------------------- #
def build_mark_svg(dark: bool = True) -> str:
    polys, rects, _ = _fit(TRISHUL_POLYGONS, TRISHUL_RECTS)
    background, mark = (INK, PAPER) if dark else (PAPER, INK)

    parts = [
        '    <polygon points="'
        + " ".join(f"{x:.1f},{y:.1f}" for x, y in poly)
        + '"/>'
        for poly in polys
    ]
    parts += [
        f'    <rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" '
        f'rx="{r:.1f}" ry="{r:.1f}"/>'
        for x, y, w, h, r in rects
    ]
    shapes = "\n".join(parts)

    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {BOX} {BOX}" \
width="{BOX}" height="{BOX}" role="img" aria-label="Rudra Labs">
  <title>Rudra Labs</title>
  <!-- Full-bleed background: GitHub rounds the corners and Google crops to a
       circle, so the artwork must not round them itself. -->
  <rect x="0" y="0" width="{BOX}" height="{BOX}" fill="{background}"/>
  <g fill="{mark}">
{shapes}
  </g>
</svg>
"""



def build_lockup_svg(dark: bool = False) -> str:
    """Horizontal mark + wordmark, for a site header or an org profile README."""
    background, ink, muted = (INK, PAPER, "#9A9A9A") if dark else (PAPER, INK, "#7A7A7A")

    polys, rects, _ = _fit(TRISHUL_POLYGONS, TRISHUL_RECTS)
    scale = 92 / BOX
    parts = [
        '      <polygon points="'
        + " ".join(f"{x * scale:.1f},{y * scale:.1f}" for x, y in poly)
        + '"/>'
        for poly in polys
    ]
    parts += [
        f'      <rect x="{x * scale:.1f}" y="{y * scale:.1f}" '
        f'width="{w * scale:.1f}" height="{h * scale:.1f}" '
        f'rx="{r * scale:.1f}" ry="{r * scale:.1f}"/>'
        for x, y, w, h, r in rects
    ]
    shapes = "\n".join(parts)

    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 640 150" \
width="640" height="150" role="img" aria-label="Rudra Labs">
  <title>Rudra Labs</title>
  <rect x="0" y="0" width="640" height="150" fill="{background}"/>
  <g fill="{ink}" transform="translate(40,29)">
{shapes}
  </g>
  <text x="172" y="82"
        font-family="Inter, 'Helvetica Neue', Helvetica, Arial, sans-serif"
        font-size="38" font-weight="800" letter-spacing="4" fill="{ink}">RUDRA LABS</text>
  <text x="174" y="106"
        font-family="Inter, 'Helvetica Neue', Helvetica, Arial, sans-serif"
        font-size="12" font-weight="500" letter-spacing="3.4" fill="{muted}">RUDRALABS.DEV</text>
</svg>
"""


# --------------------------------------------------------------------------- #
# PNG
# --------------------------------------------------------------------------- #
def write_pngs(sizes=(1024, 512, 256, 128, 64)) -> List[Path]:
    """Rasterise the avatars. PyQt6 is already a dependency of the UI."""
    try:
        from PyQt6.QtCore import QPointF, QRectF, Qt
        from PyQt6.QtGui import QColor, QImage, QPainter, QPolygonF
        from PyQt6.QtWidgets import QApplication
    except ImportError:
        print("PyQt6 is needed to write the PNGs:  pip install PyQt6")
        return []

    app = QApplication.instance() or QApplication([])
    polys, rects, _ = _fit(TRISHUL_POLYGONS, TRISHUL_RECTS)
    written: List[Path] = []

    for dark in (True, False):
        background, mark = (INK, PAPER) if dark else (PAPER, INK)
        theme = "" if dark else "-light"
        for size in sizes:
            image = QImage(size, size, QImage.Format.Format_ARGB32)
            image.fill(QColor(background))

            painter = QPainter(image)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(mark))
            k = size / BOX

            for poly in polys:
                painter.drawPolygon(QPolygonF([QPointF(x * k, y * k) for x, y in poly]))
            for x, y, w, h, r in rects:
                painter.drawRoundedRect(
                    QRectF(x * k, y * k, w * k, h * k), r * k, r * k
                )
            painter.end()

            path = ASSETS / f"rudralabs-trishul{theme}-{size}.png"
            if image.save(str(path), "PNG"):
                written.append(path)
            else:
                print(f"  failed to write {path.name}")
    del app
    return written


def main() -> int:
    (ASSETS / "rudralabs-trishul.svg").write_text(build_mark_svg(True), encoding="utf-8")
    (ASSETS / "rudralabs-trishul-light.svg").write_text(build_mark_svg(False), encoding="utf-8")
    (ASSETS / "rudralabs-logo.svg").write_text(build_lockup_svg(), encoding="utf-8")

    _, _, reach = _fit(TRISHUL_POLYGONS, TRISHUL_RECTS)
    inscribed = BOX / 2
    print(f"mark reaches {reach:.0f} px of the {inscribed:.0f} px inscribed circle "
          f"({reach / inscribed * 100:.0f}%) - circular crop is safe\n")

    written = write_pngs()
    for path in written:
        print(f"  {path.name:<34} {path.stat().st_size / 1024:6.1f} KiB")
    return 0


if __name__ == "__main__":
    sys.exit(main())
