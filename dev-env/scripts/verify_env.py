#!/usr/bin/env python3
"""
Verify an installed E3SM development environment.

Checks that:
1. Python is running from the expected installation prefix.
2. All required modules can be imported.
3. netCDF4 is linked against the environment's own libraries rather
   than libraries on LD_LIBRARY_PATH.
"""

import importlib
import json
import sys
from pathlib import Path
from typing import List, Optional


def get_packaged_version(prefix: Path, package_name: str) -> Optional[str]:
    """Find the installed version of a package from conda-meta metadata."""
    conda_meta = prefix / "conda-meta"
    for meta_file in conda_meta.glob(f"{package_name}-*.json"):
        meta = json.loads(meta_file.read_text())
        if meta.get("name") == package_name:
            return meta.get("version")
    return None


def verify_netcdf_libraries(prefix: Path) -> None:
    """
    Ensure netCDF4 runs against the environment's own NetCDF/HDF5 libraries
    even if host module stacks placed same-soname libraries on LD_LIBRARY_PATH.
    """
    import netCDF4

    checks = [
        ("libnetcdf", netCDF4.__netcdf4libversion__),
        ("hdf5", netCDF4.__hdf5libversion__),
    ]
    for lib_name, loaded_version in checks:
        packaged = get_packaged_version(prefix, lib_name)
        if loaded_version != packaged:
            sys.exit(
                f"netCDF4 is using {lib_name} {loaded_version}, "
                f"not the environment's {packaged}"
            )


def verify_imports(modules: List[str]) -> None:
    """Import each required module, exiting on failure."""
    for name in modules:
        try:
            importlib.import_module(name)
        except ImportError as exc:
            sys.exit(f"Failed to import required module '{name}': {exc}")


def main() -> None:
    if len(sys.argv) < 2:
        sys.exit(f"Usage: {sys.argv[0]} <environment_prefix> [required_modules...]")

    expected_prefix = Path(sys.argv[1]).resolve()
    actual_prefix = Path(sys.prefix).resolve()

    if actual_prefix != expected_prefix:
        sys.exit(
            f"Interpreter prefix mismatch:\n"
            f"  expected: {expected_prefix}\n"
            f"  actual:   {actual_prefix}"
        )

    required_modules = sys.argv[2:]
    verify_imports(required_modules)

    if "netCDF4" in required_modules:
        verify_netcdf_libraries(expected_prefix)

    # Print python version for deploy.py verification logging
    print(sys.version.split()[0])


if __name__ == "__main__":
    main()

