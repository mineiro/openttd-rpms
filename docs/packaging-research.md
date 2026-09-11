# OpenTTD packaging implementation notes

Checked 2026-09-11 against upstream and Fedora sources.

## Release scope and discovery

Upstream testing is **16.0-beta2**, released 2026-07-12; stable is **15.3**. Fedora currently lists 15.3-1 for Fedora 43/44 and 15.3-3.fc45 for Rawhide. Consequently this repository fills the prerelease channel gap; official Fedora is current for stable. Sources: [upstream testing](https://www.openttd.org/downloads/openttd-releases/testing), [Fedora package](https://packages.fedoraproject.org/pkgs/openttd/openttd/).

Use [latest.yaml](https://cdn.openttd.org/latest.yaml): its `latest` array contains entries with `folder: openttd-releases`, `name: stable` or `testing`, and `version`. Upstream itself uses that feed and then `https://cdn.openttd.org/{folder}/{version}/manifest.yaml`; see [website generator](https://github.com/OpenTTD/website/blob/main/fetch_downloads/__main__.py). Ignore nightly folders. Sort recognized release versions rather than dates; encode `16.0-beta2` as RPM `16.0~beta2`, retaining the original upstream string for source paths. A final release must outrank its RCs and betas.

The [16.0-beta2 manifest](https://cdn.openttd.org/openttd-releases/16.0-beta2/manifest.yaml) has a `dev_files` array; select its exact `id: openttd-16.0-beta2-source.tar.xz`, using `sha256sum` and `size`. Its size is 8,655,636 bytes and SHA256 is `d0e48e522a780dac98519054ec7efd1bca31c7a015bb09e10fb397d5f407e074`. Source URL: `https://cdn.openttd.org/openttd-releases/16.0-beta2/openttd-16.0-beta2-source.tar.xz`. Extracted directory is `openttd-16.0-beta2`. Plain Python urllib requests encountered HTTP 403 in this environment while curl succeeded. Fail closed on missing manifest entries and mismatching hashes. GitHub's release API has releases but no uploaded source assets; do not depend on GitHub asset discovery.

## Build and package

Use Fedora's [existing spec](https://src.fedoraproject.org/rpms/openttd/raw/rawhide/f/openttd.spec) as a layout reference, with fresh upstream inspection instead of copying stale bundled-library versions or license metadata. [Upstream CMake](https://github.com/OpenTTD/OpenTTD/blob/16.0-beta2/CMakeLists.txt) requires C++20. Linux feature dependencies include SDL2, Freetype, Fontconfig, Harfbuzz, ICU, FluidSynth, OpusFile, OpenGL, curl, zlib, liblzma, LZO and PNG. grfcodec supports base-set generation. Doxygen is optional development documentation tooling.

Set `OPTION_INSTALL_FHS=ON`, `CMAKE_INSTALL_BINDIR=bin`, `CMAKE_INSTALL_DATADIR=share`, `GLOBAL_DIR=/usr/share/openttd`, and `OPTION_PACKAGE_DEPENDENCIES=OFF`. Upstream otherwise defaults to games paths. Retain `OPTION_USE_ASSERTS=ON` for betas/RCs. Sources: [options](https://github.com/OpenTTD/OpenTTD/blob/16.0-beta2/cmake/Options.cmake), [install rules](https://github.com/OpenTTD/OpenTTD/blob/16.0-beta2/cmake/InstallAndPackage.cmake).

The normal build creates a separate `openttd_test` target and registers its tests through `catch_discover_tests`; use `%ctest` in `%check`. Install rules supply the executable, language/base data, scripts, manual, icons and desktop file. Fedora packaging should provide AppStream metadata and validate it and the desktop file. Fedora's current spec recommends `openttd-opengfx` and `fluid-soundfont-gm`; upstream requires a separate graphics base set and recommends sound/music data, with in-game downloads also supported.

## Bundled code and licenses

[Upstream README licensing](https://github.com/OpenTTD/OpenTTD/blob/16.0-beta2/README.md#30-licensing) and archive headers identify:

- OpenTTD: GPL-2.0-only.
- fmt **11.1.4** (`FMT_VERSION 110104`), nlohmann-json **3.11.3**, OpenGL headers and social-integration API: MIT.
- Modified Squirrel **2.2.5~openttd** and MD5: Zlib.
- Monocypher **4.0.2**: BSD-2-Clause OR CC0-1.0. Its actual license filename is `src/3rdparty/monocypher/LICENCE.md`, despite README spelling it differently.
- ICU scriptrun: Unicode-DFS-2016, as evidenced by the actual bundled `src/3rdparty/icu/LICENSE` text (1991–2023 copyright, permission alternatives (a)/(b)).
- Catch2 **2.13.10**: BSL-1.0, used by the separate test executable.
- CMake CheckAtomic: Apache-2.0 build tooling, not linked into the installed game.

Declare bundled provides for linked copies; match versions to current headers. Fedora's existing fmt 7.1.3 provide is stale. Preserve all required license texts using `%license`; MD5 and Khronos notices live in source headers. The existing Fedora spec's LGPL/BSD-3 terms should not be assumed to describe this newer source. Refresh this inventory on future updates, especially major releases. Source tree: [third-party code](https://github.com/OpenTTD/OpenTTD/tree/16.0-beta2/src/3rdparty).

## COPR observations and automation

The [COPR project search API](https://copr.fedorainfracloud.org/api_3/project/search?query=openttd) returns various rebuild/testing repositories, `pemensik/games`, and `kraskaska/openttd-jgrpp`. The [games package configuration](https://copr.fedorainfracloud.org/api_3/package/list?ownername=pemensik&projectname=games) points OpenTTD at a Fedora `f41-stable` fork; the [JGR package](https://copr.fedorainfracloud.org/api_3/package/list?ownername=kraskaska&projectname=openttd-jgrpp) is a separate patch-pack project. These responses do not establish current binary versions; avoid claiming every COPR is outdated.

COPR supports source RPM uploads and source-control package builds; credentials belong in the CI secret store. See [COPR documentation](https://docs.copr.fedorainfracloud.org/user_documentation.html). Keep source download/hash validation and source-RPM creation before authenticated submission, make retries idempotent by version/release, and report build results. Scheduled discovery should also allow manual dispatch. Validate available Fedora chroots against COPR, and distinguish stable Fedora releases from branched prerelease/Rawhide targets in user documentation.
