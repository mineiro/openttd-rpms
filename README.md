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
Graphics, sound and music are recommended from Fedora's OpenGFX/OpenSFX/OpenMSX
packages, and can also be installed with OpenTTD's content downloader.

To return to Fedora's package:

```sh
sudo dnf copr disable mineiro/openttd
sudo dnf distro-sync 'openttd*'
```

## Build locally

```sh
sudo dnf install rpm-build rpmdevtools rpmlint mock make python3-pyyaml python3-rpm
make check
make srpm
make mock CHROOT=fedora-44-x86_64
```

The optional `openttd-docs` subpackage preserves upgrades from Fedora installations
that include technical documentation.

Your user must be allowed to run mock. SRPMs go to `dist/srpm/`, and mock RPMs
and logs to `dist/mock/<chroot>/`. The build runs upstream unit tests and checks
the executable version, desktop file and AppStream metadata.

## Updates

An hourly GitHub Actions workflow discovers official releases, verifies source
checksums, records package updates, and builds missing COPR targets. Failed
builds are retried, even when the version has not changed. Changes to bundled
libraries pause publication for license/version review.

- [Automation and setup](docs/automation.md)
- [Packaging policy](docs/packaging-policy.md)
- [Upstream and Fedora research](docs/packaging-research.md)

Repository: [mineiro/openttd-rpms](https://github.com/mineiro/openttd-rpms).
Packaging maintained at [mineiro.io](https://mineiro.io).

Packaging scripts are MIT-licensed. AppStream metadata is CC0-1.0. OpenTTD and
its bundled components retain their upstream licenses, recorded in the spec.
