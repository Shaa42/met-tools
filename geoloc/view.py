#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Generate a world map with trajectories from CSV files using folium.

- Reads every CSV in assets/csv/
- Each CSV must contain columns: ip,latitude,longitude (header row required)
- For each CSV, draws the trajectory from the first to the last point in a unique color
- Saves both an interactive HTML map and a PNG snapshot to assets/img/

PNG export tries Selenium (headless Chrome/Firefox) first, then imgkit (wkhtmltoimage).
If neither is available, only the HTML is produced.

Usage:
    python geoloc/view.py
    python geoloc/view.py --width 1920 --height 1080 --html-name trajectories.html --png-name trajectories.png

Dependencies:
    - folium (required)
    - selenium (optional, for PNG export)
      and one of Chrome/Firefox headless + respective webdriver (chromedriver/geckodriver) in PATH
    - OR imgkit + wkhtmltoimage (optional, for PNG export)
"""

from __future__ import annotations

import argparse
import csv

import sys
import time
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

try:
    import folium
    from folium import Map, FeatureGroup, PolyLine, LayerControl, CircleMarker
except ImportError:
    print(
        "Missing dependency: folium is required. Install with: pip install folium",
        file=sys.stderr,
    )
    raise

try:
    from branca.element import Element
except Exception:
    Element = None  # legend is optional if branca.element is unavailable


LatLng = Tuple[float, float]


def ensure_dirs(*paths: Path) -> None:
    for p in paths:
        p.mkdir(parents=True, exist_ok=True)


def find_csv_files(csv_dir: Path) -> List[Path]:
    if not csv_dir.exists():
        return []
    return sorted([p for p in csv_dir.glob("*.csv") if p.is_file()])


def parse_float(value: str) -> Optional[float]:
    try:
        v = float(value.strip())
        if v != v:  # NaN
            return None
        return v
    except Exception:
        return None


def load_csv_points(csv_path: Path) -> List[LatLng]:
    """
    Loads a CSV file and returns an ordered list of (lat, lon).
    Expects header with columns including latitude, longitude OR
    rows in format: ip,latitude,longitude.
    """
    points: List[LatLng] = []

    with csv_path.open("r", newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        header = next(reader, None)
        lat_idx, lon_idx = None, None

        if header:
            cols = [c.strip().lower() for c in header]
            # try standard names
            lat_candidates = ["latitude", "lat", "y"]
            lon_candidates = ["longitude", "lon", "lng", "x"]

            for i, c in enumerate(cols):
                if lat_idx is None and c in lat_candidates:
                    lat_idx = i
                if lon_idx is None and c in lon_candidates:
                    lon_idx = i

            # fallback: assume ip,lat,lon (3 columns)
            if lat_idx is None or lon_idx is None:
                if len(cols) >= 3:
                    lat_idx, lon_idx = 1, 2
                elif len(cols) >= 2:
                    lat_idx, lon_idx = 0, 1
        else:
            # empty file
            return points

        if lat_idx is None or lon_idx is None:
            # As a last resort, try to infer from rows
            lat_idx, lon_idx = 1, 2

        for row in reader:
            if not row:
                continue
            # Some rows may be "ip,lat,lon" or already just "lat,lon"
            if len(row) <= max(lat_idx, lon_idx):
                # Try to split a potential loc string "lat,lon" in row[1]
                if len(row) == 2 and "," in row[1]:
                    loc_parts = row[1].split(",", 1)
                    row = [row[0], loc_parts[0], loc_parts[1]]
                else:
                    continue
            lat = parse_float(row[lat_idx])
            lon = parse_float(row[lon_idx])
            if lat is None or lon is None:
                continue
            # Keep only valid geographic coordinates
            if -90.0 <= lat <= 90.0 and -180.0 <= lon <= 180.0:
                points.append((lat, lon))

    return points


def generate_palette(n: int) -> List[str]:
    """
    Generate n distinct colors as hex strings using HLS.
    """
    if n <= 0:
        return []
    # HLS to RGB conversion, to generate distinct hues
    colors: List[str] = []
    for i in range(n):
        h = (i / max(1, n)) % 1.0
        l = 0.5
        s = 0.8
        r, g, b = hls_to_rgb(h, l, s)
        colors.append(rgb_to_hex(r, g, b))
    return colors


def hls_to_rgb(h: float, l: float, s: float) -> Tuple[int, int, int]:
    # Local copy to avoid importing colorsys at module top (keep deps minimal)
    import colorsys

    r, g, b = colorsys.hls_to_rgb(h, l, s)
    return int(r * 255), int(g * 255), int(b * 255)


def rgb_to_hex(r: int, g: int, b: int) -> str:
    return f"#{r:02x}{g:02x}{b:02x}"


def fit_bounds_from_points(
    points_by_file: Dict[str, List[LatLng]],
) -> Optional[List[LatLng]]:
    lats: List[float] = []
    lons: List[float] = []
    for pts in points_by_file.values():
        for lat, lon in pts:
            lats.append(lat)
            lons.append(lon)
    if not lats or not lons:
        return None
    return [(min(lats), min(lons)), (max(lats), max(lons))]


def add_legend(m: Map, legend_items: Sequence[Tuple[str, str]]) -> None:
    if not legend_items or Element is None:
        return

    # Build a simple HTML legend
    # Escape names lightly for HTML rendering
    def esc(s: str) -> str:
        return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    items_html = "\n".join(
        f'<div style="display:flex;align-items:center;margin-bottom:4px;">'
        f'<span style="display:inline-block;width:14px;height:14px;background:{color};'
        f'border:1px solid #333;margin-right:6px;"></span>'
        f'<span style="font-size:12px;">{esc(name)}</span></div>'
        for name, color in legend_items
    )
    legend_html = f"""
<div style="
    position: fixed;
    bottom: 18px;
    left: 18px;
    z-index: 9999999;
    background: rgba(255,255,255,0.95);
    padding: 10px 12px;
    border: 1px solid #999;
    border-radius: 6px;
    box-shadow: 0 1px 4px rgba(0,0,0,0.2);
">
    <div style="font-weight:600;margin-bottom:6px;">Trajectoires (CSV)</div>
    {items_html}
</div>
    """
    m.get_root().html.add_child(Element(legend_html))


def snapshot_html_to_png(
    html_path: Path, png_path: Path, width: int, height: int
) -> bool:
    """
    Try to export an HTML map to PNG using Selenium (Chrome/Firefox) or imgkit.
    Returns True on success, False on failure.
    """
    abs_html = html_path.resolve().as_uri()

    # Try selenium with Chrome first
    try:
        from selenium import webdriver
        from selenium.common.exceptions import WebDriverException

        # Chrome
        try:
            from selenium.webdriver.chrome.options import Options as ChromeOptions

            chrome_opts = ChromeOptions()
            # older selenium/chrome use '--headless', newer support '--headless=new'
            chrome_opts.add_argument("--headless=new")
            chrome_opts.add_argument(f"--window-size={width},{height}")
            chrome_opts.add_argument("--hide-scrollbars")
            driver = webdriver.Chrome(options=chrome_opts)
            try:
                driver.get(abs_html)
                time.sleep(2.0)
                driver.save_screenshot(str(png_path))
                return True
            finally:
                driver.quit()
        except Exception:
            # Try Firefox
            try:
                from selenium.webdriver.firefox.options import Options as FirefoxOptions

                ff_opts = FirefoxOptions()
                ff_opts.add_argument("--headless")
                driver = webdriver.Firefox(options=ff_opts)
                try:
                    driver.set_window_size(width, height)
                    driver.get(abs_html)
                    time.sleep(2.5)
                    driver.save_screenshot(str(png_path))
                    return True
                finally:
                    driver.quit()
            except Exception:
                pass
    except Exception:
        pass

    # Try imgkit (wkhtmltoimage)
    try:
        import imgkit

        options = {
            "width": str(width),
            "height": str(height),
            "enable-local-file-access": None,  # required by some wkhtmltoimage builds
            "quiet": "",
        }
        imgkit.from_file(str(html_path), str(png_path), options=options)
        return True
    except Exception:
        return False


def build_map(
    points_by_file: Dict[str, List[LatLng]],
    colors_by_file: Dict[str, str],
    tiles: str = "CartoDB positron",
) -> Map:
    # Default center
    m = folium.Map(location=[20, 0], zoom_start=2, tiles=tiles, control_scale=True)
    legend_items: List[Tuple[str, str]] = []

    for name, points in points_by_file.items():
        if not points:
            continue
        color = colors_by_file.get(name, "#3388ff")
        legend_items.append((name, color))

        group = FeatureGroup(name=name, show=True)

        # Polyline for trajectory
        PolyLine(
            locations=points,
            color=color,
            weight=3,
            opacity=0.9,
            dash_array=None,
            tooltip=f"Trajectoire: {name}",
        ).add_to(group)

        # Start and End markers
        start = points[0]
        end = points[-1]

        CircleMarker(
            location=start,
            radius=6,
            color="#1a7f37",  # dark green border
            weight=2,
            fill=True,
            fill_color="#34c759",  # green
            fill_opacity=1.0,
            tooltip=f"Départ: {name}",
            popup=f"Départ ({name})",
        ).add_to(group)

        CircleMarker(
            location=end,
            radius=6,
            color="#7f1a1a",  # dark red border
            weight=2,
            fill=True,
            fill_color="#ff3b30",  # red
            fill_opacity=1.0,
            tooltip=f"Arrivée: {name}",
            popup=f"Arrivée ({name})",
        ).add_to(group)

        group.add_to(m)

    LayerControl(collapsed=False).add_to(m)

    # Fit bounds
    bounds = fit_bounds_from_points(points_by_file)
    if bounds:
        m.fit_bounds(bounds, padding=(30, 30))

    # Legend
    add_legend(m, legend_items)

    return m


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Generate folium map trajectories from CSV files."
    )
    parser.add_argument(
        "--csv-dir",
        default=str(Path(__file__).resolve().parent / "assets" / "csv"),
        help="Directory containing CSV files (default: assets/csv)",
    )
    parser.add_argument(
        "--out-dir",
        default=str(Path(__file__).resolve().parent / "assets" / "img"),
        help="Directory to write outputs (default: assets/img)",
    )
    parser.add_argument(
        "--html-name", default="trajectories.html", help="Output HTML filename"
    )
    parser.add_argument(
        "--png-name", default="trajectories.png", help="Output PNG filename"
    )
    parser.add_argument(
        "--width", type=int, default=1600, help="PNG width (default: 1600)"
    )
    parser.add_argument(
        "--height", type=int, default=900, help="PNG height (default: 900)"
    )
    args = parser.parse_args(argv)

    base_dir = Path(__file__).resolve().parent
    csv_dir = Path(args.csv_dir)
    out_dir = Path(args.out_dir)
    ensure_dirs(csv_dir, out_dir)

    csv_files = find_csv_files(csv_dir)
    if not csv_files:
        print(f"Aucun fichier CSV trouvé dans: {csv_dir}", file=sys.stderr)
        print(
            "Assurez-vous que vos fichiers sont placés dans assets/csv/ et contiennent 'ip,latitude,longitude'."
        )
        return 1

    points_by_file: Dict[str, List[LatLng]] = {}
    for p in csv_files:
        pts = load_csv_points(p)
        if not pts:
            print(
                f"Avertissement: aucun point valide dans {p.name}. Ignoré.",
                file=sys.stderr,
            )
            continue
        points_by_file[p.name] = pts

    if not points_by_file:
        print("Aucun point valide trouvé dans les CSV fournis.", file=sys.stderr)
        return 1

    # Colors for each file
    colors = generate_palette(len(points_by_file))
    colors_by_file = {name: color for name, color in zip(points_by_file.keys(), colors)}

    # Build map
    m = build_map(points_by_file, colors_by_file)

    # Save HTML
    html_path = out_dir / args.html_name
    m.save(str(html_path))
    print(f"Carte HTML générée: {html_path}")

    # Save PNG snapshot
    png_path = out_dir / args.png_name
    ok = snapshot_html_to_png(html_path, png_path, width=args.width, height=args.height)
    if ok:
        print(f"Image PNG générée: {png_path}")
    else:
        print(
            "Impossible de générer le PNG automatiquement.\n"
            "Installez soit:\n"
            "  - selenium + un navigateur headless (Chrome/Firefox) et leur webdriver (chromedriver/geckodriver)\n"
            "  - ou imgkit + wkhtmltoimage\n"
            "Puis relancez le script.\n"
            f"L'HTML reste disponible ici: {html_path}"
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
