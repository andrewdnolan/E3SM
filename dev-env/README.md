# E3SM Development Environment (`e3sm-dev-env`)

Python runtime environment for E3SM CIME workflow commands, component configuration scripts (`buildnml`/`buildlib`), and EVV testing infrastructure.

---

## Quick Start (Using the Environment)

To use the pre-installed development environment on a supported machine, source the loader script for your shell.

### Supported Machines

| Machine | Facility | Loader Path (`load_latest.sh` / `.csh`) |
| :--- | :--- | :--- |
| **Chrysalis** | LCRC | `/lcrc/soft/climate/e3sm-dev-env/load_latest.sh` |
| **Perlmutter** | NERSC | `/global/common/software/e3sm/e3sm-dev-env/load_latest.sh` |
| **Frontier** | OLCF | `/lustre/orion/cli115/world-shared/e3sm-dev-env/load_latest.sh` |

There is only one installation per facility. 
For facilities where multiple machines share a file system (e.g. `pm-cpu` and `pm-gpu` at NERSC),
the common installation can be safely used across machines.

### Activating

**Bash / Zsh**:
```bash
source /lcrc/soft/climate/e3sm-dev-env/load_latest.sh
```

**C-Shell (csh / tcsh)**:
```csh
source /lcrc/soft/climate/e3sm-dev-env/load_latest.csh
```

Once sourced, your prompt will display `(e3sm-dev-env)`. You can verify the active installation with:
```bash
echo $E3SM_DEV_ENV_VERSION
which python3
```

> [!TIP]
> It's often convenient to start a subshell (e.g. `bash`) before sourcing the load script so that you can cleanly exit the environment, without closing the terminal.

---

## Deploying the Environment

`deploy.py` installs and configures the environment using only Python's standard library (Python >= 3.6). Loading an installed environment requires neither Pixi nor internet connectivity.

### Prerequisites
[Pixi](https://pixi.sh) is required on the machine performing the deployment:
```bash
curl -fsSL https://pixi.sh/install.sh | bash
```

### Local / Custom Installation
To install into a personal directory (e.g. for testing or isolated development):
```bash
./deploy.py --prefix ~/e3sm-dev-env
source ~/e3sm-dev-env/<version>/load.sh
```
Use `--recreate` to overwrite an existing local installation of the same version.

### Shared Production Deployment (Maintainers)
To publish a shared, read-only installation on a cluster:
```bash
./deploy.py --prefix /lcrc/soft/climate/e3sm-dev-env --shared \
    --group cels --set-latest
```

---

## Developer Guide & Architecture

### Repository Structure
```
dev-env/
├── deploy.py          # Main deployment CLI script (stdlib only)
├── deploy.cfg         # Configuration for exposed binaries and verification imports
├── pixi.toml          # Package specifications and constraints
├── pixi.lock          # Fully resolved, cross-platform dependency lockfile
├── scripts/
│   └── verify_env.py  # Standalone environment verification script
└── templates/
    ├── load.sh.in     # Template for bash/POSIX shell loader
    └── load.csh.in    # Template for C-shell loader
```

### How Deployment Works
1. **Isolated Install**: `deploy.py` invokes `pixi install --locked` into `<prefix>/<version>/.pixi`.
2. **Selective `PATH` (`python-bin`)**: Only binaries listed in `deploy.cfg` under `[deploy] exposed` (typically `python3`, `python`) are symlinked into `python-bin/`. Build tools and libraries (`nc-config`, `h5dump`) stay off `PATH` so they cannot shadow host compiler module stacks.
3. **Loader Generation**: Templates in `templates/*.in` are rendered into `load.sh` and `load.csh`. Any `##` comments are stripped, and `@var@` tokens are replaced with installation paths and metadata.
4. **Verification**: `scripts/verify_env.py` checks that:
   - The interpreter runs from the target installation prefix.
   - All modules listed in `deploy.cfg` (`[verification] required_imports`) can be imported.
   - `netCDF4` is linked against the environment's bundled NetCDF/HDF5 libraries rather than host libraries on `LD_LIBRARY_PATH`.
5. **Permissions (Shared)**: If `--shared` is specified, the installation is recursively made group-owned and read-only (`chmod -R a+rX,a-w`).

### Updating Dependencies or Python Version
1. Update constraints in `pixi.toml` (and bump `version` in `[workspace]`):
   ```toml
   [dependencies]
   python = "3.14.*"
   ```
2. Update the lockfile:
   ```bash
   pixi update
   ```
3. Commit both `pixi.toml` and `pixi.lock`.

### Customizing Exposed Tools
To expose additional tools (e.g., `pytest`), add them to `deploy.cfg`:
```ini
[deploy]
exposed = python3, python, pytest
```
