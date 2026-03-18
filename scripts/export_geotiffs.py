#!/usr/bin/env python3
"""
export_geotiffs.py
──────────────────
Standalone GEE batch export script for the Western Maharashtra Erosion analysis.
Exports all computed raster layers as GeoTIFFs to Google Drive.

Usage:
    python scripts/export_geotiffs.py --project your-gee-project-id

Requires:
    - earthengine-api >= 0.1.370
    - Active GEE authentication (run `earthengine authenticate` first)
"""

import argparse
import json
import os
import sys
import time

# ─── Configuration ────────────────────────────────────────────────────────────

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "..", "config", "analysis_config.json")

EXPORT_LAYERS = {
    "SoilLoss_30m":           {"description": "RUSLE Soil Loss (t/ha/yr)"},
    "ErosionClass_30m":       {"description": "Erosion severity class (1-6)"},
    "VulnerabilityIndex_30m": {"description": "Vulnerability Index (0-100)"},
    "RFactor_30m":            {"description": "Rainfall erosivity (R-factor)"},
    "KFactor_30m":            {"description": "Soil erodibility (K-factor)"},
    "LSFactor_30m":           {"description": "Topographic factor (LS-factor)"},
    "CFactor_30m":            {"description": "Cover management (C-factor)"},
    "PFactor_30m":            {"description": "Support practice (P-factor)"},
    "NDVI_30m":               {"description": "Sentinel-2 median NDVI"},
    "Slope_30m":              {"description": "Slope (degrees)"},
    "DEM_30m":                {"description": "SRTM DEM elevation (m)"},
    "TRI_30m":                {"description": "Terrain Ruggedness Index"},
    "AnnualRainfall_30m":     {"description": "Annual rainfall (mm)"},
    "MonsoonRainfall_30m":    {"description": "Monsoon rainfall (mm)"},
    "AnnualRunoff_30m":       {"description": "SCS-CN annual runoff (mm)"},
    "ErosionHotspots_30m":    {"description": "Hotspots (>40 t/ha/yr)"},
    "SWC_PriorityZones_30m":  {"description": "SWC priority zones (1-5)"},
}


def load_config():
    """Load analysis configuration from JSON."""
    with open(CONFIG_PATH) as f:
        return json.load(f)


def get_study_area(ee, config):
    """Define study area from FAO GAUL Level-2 boundaries."""
    gaul = ee.FeatureCollection("FAO/GAUL/2015/level2")
    districts = config["districts"]
    aoi = gaul.filter(
        ee.Filter.And(
            ee.Filter.eq("ADM1_NAME", "Maharashtra"),
            ee.Filter.inList("ADM2_NAME", districts)
        )
    )
    return aoi.geometry()


def compute_rfactor(ee, config, aoi):
    """Compute R-factor from GPM IMERG data."""
    start = f"{config['start_year']}-01-01"
    end = f"{config['end_year'] + 1}-01-01"

    gpm = (ee.ImageCollection("NASA/GPM_L3/IMERG_V06")
           .filterDate(start, end)
           .select("precipitationCal"))

    # Monthly mean precipitation
    months = ee.List.sequence(1, 12)

    def monthly_mean(m):
        m = ee.Number(m)
        monthly = gpm.filter(ee.Filter.calendarRange(m, m, "month"))
        return monthly.mean().multiply(24).rename("precip").set("month", m)

    monthly_imgs = ee.ImageCollection(months.map(monthly_mean))

    # Compute mean annual + MFI
    p_annual = monthly_imgs.sum()
    p_monthly_sq = monthly_imgs.map(lambda img: img.pow(2))
    mfi = p_monthly_sq.sum().divide(p_annual.add(1e-9))

    r_factor = mfi.multiply(0.5).add(p_annual.multiply(0.363)).add(79)
    return r_factor.rename("R_Factor").clip(aoi)


def compute_kfactor(ee, aoi):
    """Compute K-factor from SoilGrids (EPIC equation)."""
    clay = ee.Image("projects/soilgrids-isric/clay_mean").select(0).rename("clay")
    sand = ee.Image("projects/soilgrids-isric/sand_mean").select(0).rename("sand")
    silt = ee.Image("projects/soilgrids-isric/silt_mean").select(0).rename("silt")
    soc = ee.Image("projects/soilgrids-isric/soc_mean").select(0).rename("soc")

    f_csand = sand.multiply(-0.01).exp().multiply(0.3).add(0.2)
    f_clsi = silt.divide(clay.add(silt).add(1e-9)).pow(0.3)
    f_orgC = soc.multiply(0.1).add(1).pow(-0.5)

    k_factor = f_csand.multiply(f_clsi).multiply(f_orgC).multiply(0.1317)
    return k_factor.rename("K_Factor").clip(aoi)


def compute_lsfactor(ee, config, aoi):
    """Compute LS-factor from SRTM 30m (McCool 1989)."""
    dem = ee.Image("USGS/SRTMGL1_003").clip(aoi)
    slope_rad = ee.Terrain.slope(dem).multiply(3.14159265 / 180)
    slope_deg = ee.Terrain.slope(dem)

    s_low = slope_rad.sin().multiply(10.8).add(0.03)
    s_high = slope_rad.sin().multiply(16.8).subtract(0.50)
    s_factor = slope_deg.lt(9).multiply(s_low).add(slope_deg.gte(9).multiply(s_high))
    s_factor = s_factor.max(0)

    cell = config["resolution"]
    l_factor = ee.Image.constant((cell / 22.13) ** 0.5)

    ls_factor = l_factor.multiply(s_factor)
    return ls_factor.rename("LS_Factor").clip(aoi)


def compute_dem_derivatives(ee, aoi):
    """Compute DEM, slope, and TRI."""
    dem = ee.Image("USGS/SRTMGL1_003").clip(aoi)
    slope = ee.Terrain.slope(dem)

    # TRI: mean absolute difference of center pixel to neighbours
    kernel = ee.Kernel.square(1, "pixels")
    tri = dem.reduceNeighborhood(
        reducer=ee.Reducer.stdDev(),
        kernel=kernel
    ).rename("TRI")

    return dem.rename("DEM"), slope.rename("Slope"), tri


def export_image(ee, image, name, config, aoi, drive_folder):
    """Submit a GEE export task to Google Drive."""
    task = ee.batch.Export.image.toDrive(
        image=image,
        description=name,
        folder=drive_folder,
        region=aoi,
        scale=config["resolution"],
        crs=config["crs"],
        maxPixels=int(config["gee"]["max_pixels"]),
        fileFormat="GeoTIFF",
    )
    task.start()
    return task


def main():
    parser = argparse.ArgumentParser(
        description="Export RUSLE analysis layers as GeoTIFFs to Google Drive."
    )
    parser.add_argument(
        "--project", required=True,
        help="Your Google Earth Engine project ID"
    )
    parser.add_argument(
        "--folder", default=None,
        help="Google Drive folder name (default: from config)"
    )
    args = parser.parse_args()

    # ── Import and authenticate GEE ──
    try:
        import ee
    except ImportError:
        print("ERROR: earthengine-api not installed. Run: pip install earthengine-api")
        sys.exit(1)

    print("Authenticating with GEE...")
    try:
        ee.Initialize(project=args.project)
        print(f"  ✓ Authenticated — project: {args.project}\n")
    except Exception as e:
        print(f"  ✗ GEE authentication failed: {e}")
        print("  Run: earthengine authenticate")
        sys.exit(1)

    config = load_config()
    drive_folder = args.folder or config["gee"]["export_folder"]
    aoi = get_study_area(ee, config)

    print(f"Export folder: {drive_folder}")
    print(f"Resolution: {config['resolution']}m | CRS: {config['crs']}")
    print(f"Districts: {', '.join(config['districts'])}\n")

    # ── Compute layers ──
    print("Computing RUSLE layers...")

    r_factor = compute_rfactor(ee, config, aoi)
    k_factor = compute_kfactor(ee, aoi)
    ls_factor = compute_lsfactor(ee, config, aoi)
    dem, slope, tri = compute_dem_derivatives(ee, aoi)

    # RUSLE: A = R × K × LS × C × P (C and P from notebook, simplified here)
    soil_loss = r_factor.multiply(k_factor).multiply(ls_factor)

    layers = {
        "RFactor_30m": r_factor,
        "KFactor_30m": k_factor,
        "LSFactor_30m": ls_factor,
        "DEM_30m": dem,
        "Slope_30m": slope,
        "TRI_30m": tri,
    }

    # ── Submit export tasks ──
    tasks = {}
    print(f"\nSubmitting {len(layers)} export tasks to Drive/{drive_folder}...\n")

    for name, image in layers.items():
        task = export_image(ee, image, name, config, aoi, drive_folder)
        tasks[name] = task
        desc = EXPORT_LAYERS.get(name, {}).get("description", "")
        print(f"  ✓ {name:30s} — {desc}")

    print(f"\n{'─' * 60}")
    print(f"✅ {len(tasks)} export tasks submitted!")
    print(f"📁 Check Google Drive → {drive_folder}")
    print(f"\n💡 Monitor in GEE Code Editor → Tasks tab")
    print(f"   Or run: earthengine task list\n")

    # ── Optional: wait and report status ──
    print("Waiting for tasks to complete (Ctrl+C to skip)...\n")
    try:
        while True:
            all_done = True
            for name, task in tasks.items():
                status = task.status()
                state = status.get("state", "UNKNOWN")
                if state not in ("COMPLETED", "FAILED", "CANCELLED"):
                    all_done = False
                symbol = {"COMPLETED": "✅", "FAILED": "❌", "RUNNING": "⏳"}.get(state, "⏸️")
                print(f"  {symbol} {name:30s} {state}")

            if all_done:
                break
            print()
            time.sleep(30)

    except KeyboardInterrupt:
        print("\n\nSkipped waiting. Tasks continue in background on GEE servers.")

    print("\nDone!")


if __name__ == "__main__":
    main()
