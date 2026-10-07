# E3SM Development Environment (`e3sm-dev-env`)

A ready-made Python environment for working with E3SM. Load it and CIME commands
(e.g. `create_newcase`, `case.setup`, `case.build`, `case.submit`, `create_test`)
and the [EVV](https://github.com/LIVVkit/evv4esm) testing tool will have the Python packages they need.

**Load it before you run any CIME command.** Loading it afterwards is too late:
CIME reads your Python setup when it starts, so a case created without the
environment can fail with errors like `ModuleNotFoundError: No module named 'yaml'`.

```bash
source <installation root>/load_latest.sh   # roots are listed below
```

Loading only changes which `python3` you get. It does not touch your compilers,
MPI, or the NetCDF/HDF5 the model builds against, so it is safe to leave loaded
while you build and run.

---

## Loading the environment

### Where it is installed

One installation serves a whole facility, so every machine that shares a
filesystem shares it (`pm-cpu` and `pm-gpu` at NERSC, Chrysalis and Improv at
LCRC).

| Facility | Machines | Installation root | Status |
| :--- | :--- | :--- | :--- |
| LCRC | Chrysalis, Improv | `/lcrc/soft/climate/e3sm-dev-env` | proposed |
| NERSC | Perlmutter | `/global/common/software/e3sm/e3sm-dev-env` | proposed |
| OLCF | Frontier | `/lustre/orion/cli115/world-shared/e3sm-dev-env` | proposed |

> [!NOTE]
> Nothing has been published yet. These roots are proposed locations and are
> still open for discussion. Until one exists, build your own with
> *Deploying the environment*, below.

### Sourcing the loader

Append `load_latest.sh` for bash/zsh, or `load_latest.csh` for csh/tcsh, to
your facility's root:

```bash
source /lcrc/soft/climate/e3sm-dev-env/load_latest.sh
```

```csh
source /lcrc/soft/climate/e3sm-dev-env/load_latest.csh
```

`load_latest` follows the current recommended version. You can source a
specific version, which might need to reproduce and older workflow, by running:

```bash
source /lcrc/soft/climate/e3sm-dev-env/<version>/load.sh
```
where `<version>` should be replaced with the desired version.

> [!TIP]
> There is no `unload`. If you want to step out of the environment again, start
> a subshell (`bash`) before sourcing the loader and `exit` when you are done.

### Checking it worked

Your prompt gains an `(e3sm-dev-env)` marker. To confirm:

```bash
echo $E3SM_DEV_ENV_VERSION
which python3
```

---

## Deploying the Environment

`deploy.py` installs and configures the environment using only Python's standard library (Python >= 3.6). Loading an installed environment requires neither Pixi nor internet connectivity.

### Prerequisites
[Pixi](https://pixi.sh) is required on the machine performing the deployment:
```bash
curl -fsSL https://pixi.sh/install.sh | bash
```
`deploy.py` finds it on `PATH` or at `~/.pixi/bin/pixi`; use `--pixi` to point at
another copy. Pixi is only needed to *install*; loading an installed
environment does not use it.

### Local / Custom Installation
To install into a personal directory (e.g. for testing or isolated development):
```bash
./deploy.py --prefix ~/e3sm-dev-env
source ~/e3sm-dev-env/<version>/load.sh
```
The version comes from `pixi.toml`, not the command line. Use `--recreate` to
rebuild an existing local installation of the same version.

### Shared Production Deployment (Maintainers)
To publish a shared, read-only installation on a cluster:
```bash
./deploy.py --prefix /lcrc/soft/climate/e3sm-dev-env --shared \
    --group cels --set-latest
```
A published version is never replaced: bump `version` in `pixi.toml` and deploy
again. `--set-latest` repoints `load_latest.{sh,csh}` at the new version; omit it
to publish without changing what users get by default.

---

## Developer Guide & Architecture

### Repository Structure
```
dev-env/
├── deploy.py          # Main deployment CLI script (stdlib only)
├── deploy.cfg         # Configuration for exposed binaries and verification imports
├── pixi.toml          # Package specifications and constraints
├── pixi.lock          # Fully resolved, cross-platform dependency lockfile
├── README.md          # This file
├── scripts/
│   └── verify_env.py  # Standalone environment verification script
└── templates/
    ├── load.sh.in     # Template for bash/POSIX shell loader
    └── load.csh.in    # Template for C-shell loader
```

### What an Installation Looks Like
```
<prefix>/
├── load_latest.sh     -> 1.0.0/load.sh      # repointed by --set-latest
├── load_latest.csh    -> 1.0.0/load.csh
└── 1.0.0/
    ├── pixi.toml, pixi.lock                 # copies of exactly what was installed
    ├── .pixi/envs/default/                  # the full environment; never on PATH
    ├── python-bin/python3, python           # symlinks; the only thing added to PATH
    └── load.sh, load.csh                    # rendered from templates/
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
