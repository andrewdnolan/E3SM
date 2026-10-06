#!/usr/bin/env python3
"""
Install the E3SM development environment from the committed pixi.toml and
pixi.lock, and render shell loaders (sh and csh) using templates/ and deploy.cfg.

Only the standard library is used, running on any python3 >= 3.6. A pixi
executable is required for installation; loading requires neither pixi
nor network access.

Local installation:
    ./deploy.py --prefix ~/e3sm-dev-env

Shared publication (maintainers):
    ./deploy.py --prefix /lcrc/soft/climate/e3sm-dev-env --shared \
        --group cels --set-latest

Each version is installed in <prefix>/<version>. Shared versions are read-only;
use --recreate to replace a local build, or bump the version in pixi.toml.
"""

import argparse
import configparser
import os
import re
import shutil
import subprocess
import sys

from pathlib import Path
from typing import List

HERE = Path(__file__).resolve().parent


def main() -> None:
    """Deploy the E3SM development environment based on CLI arguments."""
    args = parse_args()
    version = read_version(HERE / "pixi.toml")
    prefix = Path(args.prefix).expanduser().resolve()
    dest = prefix / version
    pixi = find_pixi(args.pixi)

    if dest.exists():
        if args.shared or not args.recreate:
            hint = "" if args.shared else " or pass --recreate"
            sys.exit(
                f"{dest} already exists. Published versions are never changed in "
                f"place; bump the version in pixi.toml{hint}."
            )
        force_remove(dest)

    dest.mkdir(parents=True, exist_ok=True)

    config = configparser.ConfigParser()
    config.read(HERE / "deploy.cfg")
    execs_to_expose = get_config_list(config, "deploy", "exposed")
    required_imports = get_config_list(config, "verification", "required_imports")

    try:
        install(pixi, dest, version, execs_to_expose, args.environment)
        verify_installation(dest, required_imports, args.environment)

        if args.shared:
            set_shared_permissions(dest, args.group)

    except BaseException:
        print(f"removing incomplete installation {dest}")
        force_remove(dest)
        raise

    if args.set_latest:
        update_latest_symlinks(prefix, version)

    print(f"\nInstalled {version}. To use it:\n  source {dest / 'load.sh'}")


def install(
    pixi: Path,
    destination: Path,
    version: str, 
    execs_to_expose: List[str],
    environment: str = "default",
) -> None:
    """
    Install E3SM dev env into `destination` using the given `pixi` executable.

    Parameters:
    -----------
    pixi : Path
        Path to the pixi executable.
    destination : Path
        Path to the directory where the environment will be installed.
    version : str
        Version string to be used in the installation.
    execs_to_expose : list of str
        List of executable names to expose in the `python-bin` directory.
    environment : str, optional
        Name of the pixi environment to install (default is "default").
    """
    for name in ("pixi.toml", "pixi.lock"):
        shutil.copy2(HERE / name, destination)

    # A deployer working inside `pixi shell` must not redirect the install
    env = {
        k: v 
        for k, v in os.environ.items()
        if not k.startswith("PIXI_") or k == "PIXI_CACHE_DIR"
    }
    run([
        pixi, "install", 
        "--locked", 
        "--environment", environment,
        "--manifest-path", destination / "pixi.toml"
    ], env=env)

    env_bin = destination / ".pixi" / "envs" / environment / "bin"
    bin_dir = destination / "python-bin"
    bin_dir.mkdir(parents=True, exist_ok=True)
    for name in execs_to_expose:
        (bin_dir / name).symlink_to(env_bin / name)

    for template in (HERE / "templates").glob("*.in"):
        output_path = destination / template.stem
        mapping = {"version": version, "path": output_path, "bin": bin_dir}

        rendered = render(template.read_text(), mapping)
        output_path.write_text(rendered)


def verify_installation(
    destination: Path,
    required_imports: List[str],
    environment: str = "default",
) -> None:
    """
    Verify the installed environment by running the verification script.

    Parameters:
    -----------
    destination : Path
        Path to the directory where the environment was installed.
    required_imports : list of str
        Module names that must be importable in the installed environment.
    environment : str, optional
        Name of the pixi environment to verify (default is "default").
    """
    env = os.environ.copy()
    env.pop("PYTHONHOME", None)
    env.pop("PYTHONPATH", None)
    env["PYTHONNOUSERSITE"] = "1"

    env_prefix = destination / ".pixi" / "envs" / environment
    python_bin = destination / "python-bin" / "python3"
    verify_script = HERE / "scripts" / "verify_env.py"

    cmd = [python_bin, verify_script, env_prefix] + required_imports
    out = run(
        cmd,
        env=env,
        capture=True,
        echo=f"verifying environment imports: {', '.join(required_imports)}",
    )
    print(f"Verification passed (Python {out.strip()})")


def set_shared_permissions(destination: Path, group: str = None) -> None:
    """
    Make a shared installation group-owned, world-readable and immutable.

    Parameters:
    -----------
    destination : Path
        Path to the directory of the shared installation.
    group : str, optional
        Name of the group to own the shared installation.
    """
    if group:
        run(["chgrp", "-R", group, destination])
    run(["chmod", "-R", "a+rX,a-w", destination])
    print(f"Set shared read-only permissions in {destination}")


def update_latest_symlinks(prefix: Path, version: str) -> None:
    """
    Update load_latest symlinks to point to the newly installed version.

    Parameters:
    -----------
    prefix : Path
        Installation root directory containing version subdirectories.
    version : str
        Version string of the new target installation.
    """
    for name in ("load.sh", "load.csh"):
        link = prefix / f"load_latest{Path(name).suffix}"
        tmp = link.with_name(link.name + ".tmp")
        if tmp.is_symlink() or tmp.exists():
            tmp.unlink()
        tmp.symlink_to(Path(version) / name)
        tmp.replace(link)
        print(f"{link} -> {os.readlink(link)}")


def force_remove(path: Path) -> None:
    """
    Restore write permissions and delete a directory tree, ignoring errors.

    Parameters:
    -----------
    path : Path
        Path to the directory tree to remove.
    """
    if path.exists():
        run(["chmod", "-R", "u+w", path])
        shutil.rmtree(path, ignore_errors=True)


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description=__doc__.split("\n\n")[0],
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--prefix",
        required=True,
        help="root directory; each version is a subdirectory",
    )
    parser.add_argument(
        "--shared",
        action="store_true",
        help="publish read-only for other users",
    )
    parser.add_argument(
        "--group",
        help="group to own a shared installation",
    )
    parser.add_argument(
        "--set-latest",
        action="store_true",
        help="point load_latest.{sh,csh} at this version",
    )
    parser.add_argument(
        "--recreate",
        action="store_true",
        help="replace an existing local installation",
    )
    parser.add_argument(
        "--environment",
        default="default",
        help="pixi environment to install (default: default)",
    )
    parser.add_argument(
        "--pixi",
        help="path to the pixi executable",
    )

    args = parser.parse_args()
    if args.group and not args.shared:
        parser.error("--group requires --shared")

    return args


def get_config_list(
    config: configparser.ConfigParser, section: str, option: str
) -> List[str]:
    """
    Parse a comma-separated list of strings from a configuration section.

    Parameters:
    -----------
    config : configparser.ConfigParser
        Loaded configuration parser instance.
    section : str
        Section name in the configuration file.
    option : str
        Option name containing comma-separated items.

    Returns:
    --------
    list of str
        List of non-empty, stripped string values.
    """
    raw = config.get(section, option, fallback="")
    return [item.strip() for item in raw.split(",") if item.strip()]


def read_version(manifest_path: Path) -> str:
    """
    Read the version string from a pixi manifest file (pixi.toml).

    Parameters:
    -----------
    manifest_path : Path
        Path to the pixi manifest file.

    Returns:
    --------
    str
        Parsed version string.
    """
    match = re.search(
        r'^version\s*=\s*"([^"]+)"', manifest_path.read_text(), re.M
    )
    if not match:
        sys.exit(f"No version in {manifest_path}")
    return match.group(1)


def find_pixi(explicit: str = None) -> Path:
    """
    Find a pixi executable to use. Either use the explicitly provided path,
    search in PATH, or check the default location (~/.pixi/bin/pixi). If none
    are found, exit with an error message.

    Parameters:
    -----------
    explicit : str, optional
        Explicit path to the pixi binary provided via command-line arguments.

    Returns:
    --------
    Path
        Path to the found executable pixi binary.
    """
    candidates = []
    if explicit:
        candidates.append(Path(explicit).expanduser())

    which_pixi = shutil.which("pixi")
    if which_pixi:
        candidates.append(Path(which_pixi))

    candidates.append(Path("~/.pixi/bin/pixi").expanduser())

    for candidate in candidates:
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return candidate

    sys.exit(
        "pixi not found. Install it with\n"
        "  curl -fsSL https://pixi.sh/install.sh | bash\n"
        "or pass --pixi."
    )


def render(template_text: str, mapping: dict) -> str:
    """
    Render a template string by replacing @var@ with mapping[var].

    Parameters:
    -----------
    template_text : str
        The template string containing variables in the form @var@.
    mapping : dict
        A dictionary mapping variable names to their replacement values.

    Returns:
    --------
    str
        The rendered string with all template variables replaced.
    """
    # strip template comments (lines starting with ##)
    text = re.sub(r"^\s*##.*$\n?", "", template_text, flags=re.MULTILINE)

    def _replace_var(match):
        var_name = match.group(1)
        if var_name not in mapping:
            sys.exit(
                f"Missing replacement value for template variable: @{var_name}@"
            )
        return str(mapping[var_name])

    return re.sub(r"@(\w+)@", _replace_var, text)


def run(
    cmd: list,
    env: dict = None,
    capture: bool = False,
    echo: str = None,
) -> str:
    """
    Execute a shell command using subprocess and handle failures.

    Parameters:
    -----------
    cmd : list
        Command arguments list.
    env : dict, optional
        Environment variables dictionary.
    capture : bool, optional
        If True, capture and return stdout.
    echo : str, optional
        Custom description string to log instead of cmd.

    Returns:
    --------
    str
        Captured stdout if capture is True, otherwise None.
    """
    cmd_str = [str(c) for c in cmd]
    print("+ " + (echo or " ".join(cmd_str)))

    proc = subprocess.run(
        cmd_str,
        env=env, 
        stdout=subprocess.PIPE if capture else None,
        universal_newlines=True
    )
    if proc.returncode != 0:
        sys.exit(f"command failed with exit code {proc.returncode}")
    return proc.stdout


if __name__ == "__main__":
    main()
