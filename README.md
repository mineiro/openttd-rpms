# openttd-rpms

Fedora RPM packaging for [OpenTTD](https://www.openttd.org/), tracking official
**testing and stable releases**. The [release lock](packages/openttd/release.json)
records the tracked version. Nightly builds are excluded.

Fedora already ships the current stable OpenTTD 15.3. This repository provides
an opt-in route to newer betas and release candidates, then their final releases.

## Install

[COPR: mineiro/openttd](https://copr.fedorainfracloud.org/coprs/mineiro/openttd/)

```sh
sudo dnf copr enable mineiro/openttd
sudo dnf install openttd
# If already installed:
sudo dnf upgrade openttd
```

Targets: Fedora 43/44, Fedora 45 prerelease, and Rawhide; x86_64 and aarch64.
See COPR for the result on your target before installing.

This replaces Fedora's `openttd` package and shares its configuration and saves.
Back up saves before testing: saves written by a newer release may not load in
older releases. Multiplayer servers generally require a compatible game version.
Graphics come from Fedora's `openttd-opengfx` package. This COPR supplies
`openttd-opensfx` (sound effects) and `openttd-openmsx` (MIDI music). A fresh
`dnf install openttd` installs them through the game's recommendations when
weak dependencies are enabled (DNF's default).

For an existing installation that displayed the silent-fallback warning:

```sh
sudo dnf install --refresh openttd-opensfx openttd-openmsx
```

Restart the game and choose **Game Options → Base sounds set → OpenSFX** if
`NoSound` was previously saved. Choose **OpenMSX** as the base music set if
needed. Package installation preserves your existing configuration.

OpenGFX2 Classic is a distinct, newer graphics family. Install it as an option
alongside Fedora's original OpenGFX:

```sh
sudo dnf install --refresh openttd-opengfx2-classic
```

Select **Game Options → Graphics → Base graphics set → OpenGFX2 Classic**.
Existing graphics choices are preserved. This package contains Classic, the
complete 8-bit set, and excludes the separate High Def variant and gameplay
NewGRFs. Upstream recommended OpenGFX2 during the
[OpenTTD 15 release candidates](https://www.openttd.org/news/2025/12/08/openttd-15-0-rc1).

To return to Fedora's package:

```sh
sudo dnf copr disable mineiro/openttd
sudo dnf distro-sync 'openttd*'
```

## Build locally

```sh
sudo dnf install rpm-build rpmdevtools rpmlint mock make python3-pyyaml python3-rpm
make check
make srpm PACKAGE=openttd-opensfx
make srpm-all
make mock PACKAGE=openttd CHROOT=fedora-44-x86_64
```

The optional `openttd-docs` subpackage preserves upgrades from Fedora installations
that include technical documentation.

Your user must be allowed to run mock. SRPMs go to `dist/srpm/`, and mock RPMs
and logs to `dist/mock/<chroot>/`. The build runs upstream unit tests and checks
the executable version, desktop file and AppStream metadata.

## Packages

- `openttd`: official testing and stable game releases.
- `openttd-opengfx2-classic`: Classic graphics, rebuilt from pinned artwork and font sources.
- `python3-blend-modes`: a build dependency for graphics generation (source package `python-blend-modes`).
- `openttd-opensfx`: stable sound sets, encoded from WAV sources.
- `openttd-openmsx`: stable MIDI music sets, with regenerated descriptors.
- `catcodec`: the source-built encoder used to build OpenSFX; it is not required
  at runtime by the sound package.

OpenSFX builds need Catcodec; OpenGFX2 builds need python3-blend-modes. Both are
available from this COPR or a local mock chain repository.
The CI workflow builds the tool first, then the assets and game, and verifies
that installing the game alone pulls in usable audio sets.

## Updates

An hourly GitHub Actions workflow discovers official releases, verifies source
checksums, records package updates, and builds missing COPR targets. Failed
builds are retried, even when the version has not changed. The game tracks testing and stable releases; the tool and assets track stable
releases. Changes to bundled libraries, font files, or asset license/attribution
notices pause the affected package for review.

- [Automation and setup](docs/automation.md)
- [Packaging policy](docs/packaging-policy.md)
- [Upstream and Fedora research](docs/packaging-research.md)
- [Sound/music source and license research](docs/sound-packaging-research.md)
- [OpenGFX2 source and license research](docs/opengfx2-research.md)

Repository: [mineiro/openttd-rpms](https://github.com/mineiro/openttd-rpms).
Packaging maintained at [mineiro.io](https://mineiro.io).

Packaging scripts are MIT-licensed. AppStream metadata is CC0-1.0. OpenTTD and
its bundled components retain their upstream licenses, recorded in the spec.

The first graphics source preparation downloads about 900 MB of upstream artwork,
including editable originals, and creates a complete source RPM. The validated
source bundle is cached for subsequent builds. The graphics build also generates
its font inputs from SFD sources with FontForge. None of those build tools are
runtime requirements of the graphics data package.
