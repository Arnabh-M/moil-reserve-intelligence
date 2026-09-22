"""
MOIL Reserve Intelligence — Unified Google Earth Engine Authentication
========================================================================
Provides `get_ee(dry_run: bool = False)` for all remote sensing pipelines:
- gee_pipeline/gee_prep.py
- gis/ndvi_pull.py
- gis/ndvi_timeseries.py
- gee_pipeline/export_daily_features.py

Reuses `prospectivity.gee_features.initialize_ee` to ensure single-point
authentication logic across the entire repository.
"""

from __future__ import annotations

import os
import sys
import logging

logger = logging.getLogger(__name__)

# Attempt to load .env from workspace or gee_pipeline directory
try:
    from dotenv import load_dotenv
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    load_dotenv(os.path.join(base_dir, ".env"))
    load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))
except ImportError:
    pass


def get_ee(dry_run: bool = False):
    """
    Retrieves the initialized Earth Engine module.

    Parameters:
    - dry_run: If True, skips GEE network initialization and returns None with a warning.
               If False, authenticates via `prospectivity.gee_features.initialize_ee()`
               and validates connection with `ee.Number(1).getInfo()`.

    Returns:
    - Initialized `ee` module if successful, or None in dry-run mode.

    Raises:
    - RuntimeError / GEEUnavailableError if authentication or initialization fails in real mode.
      NEVER silently falls back to simulated output when dry_run is False.
    """
    if dry_run:
        print("\n" + "!" * 70)
        print("[WARN] Running in DRY-RUN mode — GEE network calls will be simulated.")
        print("[WARN] Any resulting outputs will be explicitly flagged 'simulated': true.")
        print("!" * 70 + "\n")
        return None

    # Add repository root to sys.path if not present so prospectivity can be imported
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)

    try:
        from prospectivity.gee_features import initialize_ee, GEEUnavailableError
    except ImportError as err:
        raise RuntimeError(
            f"Failed to import prospectivity.gee_features: {err}.\n"
            "Ensure the repository root is in PYTHONPATH."
        ) from err

    try:
        ee_module = initialize_ee()
        # Verify active connection with an explicit round-trip probe
        ee_module.Number(1).getInfo()
        project = os.environ.get("EE_PROJECT") or getattr(getattr(ee_module, "data", None), "_project", None)
        print(f"[GEE] Earth Engine successfully initialized (project: {project or '<default>'}).")
        return ee_module
    except GEEUnavailableError as exc:
        print("\n" + "=" * 70)
        print("[ERROR] Google Earth Engine is not available or credentials failed.")
        print(f"Details:\n{exc}")
        print("=" * 70 + "\n")
        raise
    except Exception as exc:
        print("\n" + "=" * 70)
        print(f"[ERROR] Failed to communicate with Earth Engine: {exc}")
        print("Setup Checklist:")
        print("  1. Run `earthengine authenticate` in your terminal.")
        print("  2. Set the Google Cloud project in your environment:")
        print("     PowerShell: $env:EE_PROJECT = 'your-gcp-project-id'")
        print("     Bash/Linux: export EE_PROJECT='your-gcp-project-id'")
        print("     Or define EE_PROJECT in a .env file.")
        print("  3. Alternatively, supply a service account via EE_SERVICE_ACCOUNT_JSON.")
        print("=" * 70 + "\n")
        raise RuntimeError(f"Earth Engine authentication failure: {exc}") from exc
