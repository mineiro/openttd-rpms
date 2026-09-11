# Packaging policy

This project follows the `packages/<name>/`, shared scripts, root Makefile and
`.copr/Makefile` layout used by the other mineiro RPM projects. Package released
source archives only. The channel is opt-in testing: take the newest official
stable or testing version, never a nightly or branch snapshot.

## RPM conventions

- Keep `Name: openttd`, upstream desktop identity, paths and user data locations.
  Enabling this COPR upgrades Fedora's package; it is not a parallel installation.
- Map `16.0-beta2` to `16.0~beta2` and `16.0-RC1` to `16.0~rc1`.
  RPM ordering is beta < rc < final. Do not use an Epoch to force upgrades.
- Use integer `Release` plus `%{?dist}`; reset to 1 for a new upstream version.
  Bump it whenever anything under `packages/openttd/` changes. CI checks this.
  Do not overwrite a published NVR with changed package content.
- Keep Fedora compiler/hardening flags, build debuginfo normally, and use system
  shared libraries. No network access during binary builds. Source acquisition
  happens before building the SRPM.
- Run the upstream CTest suite, version smoke test, desktop-file validation and
  AppStream validation in `%check`. Clean mock builds are the packaging gate.
- Use Fedora's OpenGFX/OpenSFX/OpenMSX packages as recommendations. The game can
  also use its in-game content downloader or the user's own licensed base data.

## Source integrity and bundled libraries

`release.json` records the official CDN source URL, SHA256 and size. The updater
checks the downloaded archive before modifying package metadata. Every SRPM
build checks it again. A changed checksum for an existing version is an error;
do not accept it merely to get a build working. These hashes protect against
changed or damaged downloads, not compromise of the upstream CDN itself.

OpenTTD directly integrates bundled code. Squirrel is an OpenTTD-specific fork;
fmt is also used by the build tools. Keep these upstream integrations for this
COPR package, following Fedora's existing approach. This is not a claim that the
package has completed an official Fedora review. `Provides: bundled(...)`
records linked libraries and versions. The ICU scriptrun code is separate from
the system ICU libraries. Select the BSD-2-Clause option for Monocypher.
Catch2 is only in the non-installed test executable; build-tool licenses do not
belong in the runtime binary's `License` expression.

`bundled-sources.json` pins all files in `src/3rdparty/`. Any change stops the
updater before it changes the spec. This intentionally makes releases that
change bundled libraries require human review. To accept one:

1. Download and verify the new release against its official manifest.
2. Review the third-party diff, including license text, versions and new or
   removed components. Update `License`, bundled provides and license-file
   installation as needed; consider available system-library integration.
3. Regenerate `bundled-sources.json` with `bundle_inventory()` from
   `scripts/releases.py`, after reviewing the source. Never refresh blindly.
4. Run `make update`, `make check`, and a clean `make mock` before publishing.

Keep the upstream project URL/identity (`openttd.org`). Packaging contact and
personal project URLs use `mineiro.io`.
