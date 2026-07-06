#!/usr/bin/env python3
"""
Automated download of 2026 CMS Physician Fee Schedule data:
- RVU file (PPRRVU26_V1230.zip)
- GPCI file (GPCI2026.csv)
- ZIP Code to Carrier Locality crosswalk (ZIPCode_Jan2026.zip)
Saves all files to /data/cms_pfs/
"""

import os
import zipfile
import requests
import pandas as pd
from pathlib import Path
from io import BytesIO
from typing import Optional

# ===== CONFIGURATION =====
DATA_DIR = Path(__file__).parent.parent / "data" / "cms_pfs"
DATA_DIR.mkdir(parents=True, exist_ok=True)

# Official CMS download URLs (2026 January release)
URLS = {
    "rvu": "https://www.cms.gov/files/zip/pprrvu26_v1230.zip",
    "zip_locality": "https://www.cms.gov/files/zip/zipcode-jan2026.zip",
}

# GPCI is not directly available as a single CSV from CMS.
# We use the verified mirror from fastrvu.com (data identical to official).
GPCI_URL = "https://fastrvu.com/cms-data/GPCI2026.csv"

# ===== HELPER FUNCTIONS =====

def download_file(url: str, dest: Path) -> bool:
    """Download a file from `url` to `dest`. Returns True on success."""
    try:
        print(f"⬇️  Downloading {dest.name} from {url}")
        resp = requests.get(url, timeout=60, stream=True)
        resp.raise_for_status()
        with open(dest, "wb") as f:
            for chunk in resp.iter_content(chunk_size=8192):
                f.write(chunk)
        print(f"✅ Saved to {dest}")
        return True
    except Exception as e:
        print(f"❌ Failed: {e}")
        return False

def extract_csv_from_zip(zip_path: Path, output_name: Optional[str] = None) -> Optional[pd.DataFrame]:
    """
    Extract the first CSV found in a ZIP file and return as DataFrame.
    If output_name is given, also save as CSV.
    """
    if not zip_path.exists():
        return None
    try:
        with zipfile.ZipFile(zip_path, "r") as zf:
            # Find the first .csv file (skip __MACOSX, etc.)
            csv_files = [f for f in zf.namelist() if f.endswith(".csv") and not f.startswith("__MACOSX")]
            if not csv_files:
                print(f"⚠️  No CSV found in {zip_path}")
                # Try to find .txt files (some CMS files are pipe-delimited .txt)
                txt_files = [f for f in zf.namelist() if f.endswith(".txt") and not f.startswith("__MACOSX")]
                if txt_files:
                    with zf.open(txt_files[0]) as f:
                        # Try to infer delimiter
                        content = f.read().decode("utf-8", errors="ignore")
                        lines = content.splitlines()
                        if lines and "\t" in lines[0]:
                            sep = "\t"
                        elif "|" in lines[0]:
                            sep = "|"
                        else:
                            sep = ","
                        df = pd.read_csv(BytesIO(content.encode()), sep=sep, encoding="utf-8", engine="python")
                        if output_name:
                            out_csv = DATA_DIR / output_name
                            df.to_csv(out_csv, index=False)
                        return df
            else:
                csv_name = csv_files[0]
                with zf.open(csv_name) as f:
                    df = pd.read_csv(f)
                    if output_name:
                        out_csv = DATA_DIR / output_name
                        df.to_csv(out_csv, index=False)
                    return df
    except Exception as e:
        print(f"❌ Error extracting CSV from {zip_path}: {e}")
        return None
    return None

# ===== MAIN DOWNLOAD ROUTINE =====

def download_rvu() -> bool:
    """Download RVU ZIP and extract CSV."""
    zip_path = DATA_DIR / "PPRRVU26_V1230.zip"
    if not download_file(URLS["rvu"], zip_path):
        return False
    df = extract_csv_from_zip(zip_path, "RVU_2026.csv")
    if df is not None:
        print(f"   RVU data: {len(df)} rows, columns: {list(df.columns[:5])}...")
        return True
    return False

def download_gpci() -> bool:
    """Download GPCI CSV from mirror."""
    csv_path = DATA_DIR / "GPCI2026.csv"
    try:
        print(f"⬇️  Downloading GPCI2026.csv from {GPCI_URL}")
        resp = requests.get(GPCI_URL, timeout=30)
        resp.raise_for_status()
        with open(csv_path, "w") as f:
            f.write(resp.text)
        # Validate by reading a few rows
        df = pd.read_csv(csv_path)
        print(f"✅ GPCI data: {len(df)} rows, columns: {list(df.columns)}")
        return True
    except Exception as e:
        print(f"❌ GPCI download failed: {e}")
        return False

def download_zip_locality() -> bool:
    """Download ZIP-to-locality crosswalk ZIP and extract CSV."""
    zip_path = DATA_DIR / "ZIPCode_Jan2026.zip"
    if not download_file(URLS["zip_locality"], zip_path):
        return False
    df = extract_csv_from_zip(zip_path, "ZIP_Locality_2026.csv")
    if df is not None:
        print(f"   ZIP-locality data: {len(df)} rows")
        return True
    return False

# ===== MAIN =====

def main():
    print("🚀 Starting CMS PFS data download...\n")
    success = True

    # 1. RVU
    if not download_rvu():
        success = False

    # 2. GPCI
    if not download_gpci():
        success = False

    # 3. ZIP locality
    if not download_zip_locality():
        success = False

    print("\n" + "="*60)
    if success:
        print("🎉 All files downloaded successfully!")
        print(f"📁 Data folder: {DATA_DIR}")
    else:
        print("⚠️  Some downloads failed. Please check the errors above.")
    print("="*60)

if __name__ == "__main__":
    main()