# OpenTTD sound and music packaging research

Checked 2026-09-11 against upstream release pages, CDN manifests, and the released source archives. Build observations below are local experiments, not claims of COPR completion.

## Releases and source integrity

- [OpenSFX latest](https://www.openttd.org/downloads/opensfx-releases/latest): 1.0.3, released 2021-10-31. [Source archive](https://cdn.openttd.org/opensfx-releases/1.0.3/opensfx-1.0.3-source.tar.xz), unpacking to `opensfx-1.0.3-source`. [Manifest](https://cdn.openttd.org/opensfx-releases/1.0.3/manifest.yaml): 9,943,616 bytes; SHA256 `43cacb3ca2d86e5729d19c7fcf2533e1bb9c9a32a39f515cf6cbe665ec32635c`.
- [OpenMSX latest](https://www.openttd.org/downloads/openmsx-releases/latest): 0.4.2, released 2021-10-31. [Source archive](https://cdn.openttd.org/openmsx-releases/0.4.2/openmsx-0.4.2-source.tar.xz), unpacking to `openmsx-0.4.2-source`. [Manifest](https://cdn.openttd.org/openmsx-releases/0.4.2/manifest.yaml): 114,760 bytes; SHA256 `0f5196f9045c9123ed9207930a73871811654e46e7de2d079be8f8ee501ba840`.
- [Catcodec latest](https://www.openttd.org/downloads/catcodec-releases/latest): 1.0.5, released 2012-04-04. [Source archive](https://cdn.openttd.org/catcodec-releases/1.0.5/catcodec-1.0.5-source.tar.xz), unpacking to `catcodec-1.0.5`. [Manifest](https://cdn.openttd.org/catcodec-releases/1.0.5/manifest.yaml): 17,952 bytes; SHA256 `47ff4e6d663e19d529960c76f1e1bda5fe4cad97e2628381ec3a894ba260e0e1`.

Downloaded all three source archives and verified their sizes and SHA256 against the official manifests. Use source archives rather than wrapping the binary ZIP distributions. MD5 inside baseset descriptors is an upstream file-format requirement, not the source authenticity check.

## Source builds

Catcodec's released Makefile builds four C++ objects and one executable, respecting `CXX`, `CXXFLAGS`, and `LDFLAGS`. An unmodified build passed locally with GCC 16.2.1. No external codec library is needed. Install `catcodec`, `docs/catcodec.1`, and its license and documentation. Package it separately for the build dependency; the sound data RPM does not need a runtime dependency on this tool. Sources: Catcodec archive `Makefile`, `src/*.cpp`, `docs/readme.txt`.

OpenSFX's `Makefile.config` and `Makefile.in` implement `make sound doc`. Catcodec encodes `src/opensfx.sfo` and WAV sources into `opensfx.cat`, and the build regenerates `opensfx.obs` with that catalogue's MD5. The `.sfo` itself is generated from `src/opensfx.psfo` with the release title substituted. Set `UNIX2DOS=` to avoid host-dependent line endings; the helper lookup uses `which`, so declare its package. The release archive includes version metadata, so git is unnecessary. Install `opensfx.cat` and `opensfx.obs` under `%{_datadir}/openttd/baseset/opensfx/` as architecture-independent data. The local source build produced a catalogue byte-for-byte identical to the official binary release (MD5 `56edd8f20cfa7413b68b2f0fb8a27be1`).

OpenMSX's `Makefile.in` implements `make music doc`: Python scripts generate the descriptor from `src/themes.list`, MIDI files, and translations. Replace the scripts' `env python` shebangs with Python 3 and remove the shipped `openmsx.obm` before building so timestamps cannot bypass regeneration. Set `UNIX2DOS=`. This full regeneration passed locally under Python 3, and every one of the 31 MIDI checksums matched the generated descriptor. Install `openmsx.obm` and the 31 `src/*.mid` files together under `%{_datadir}/openttd/baseset/openmsx/`, with `BuildArch: noarch`. There is no executable MIDI compiler or runtime Python requirement. Sources: OpenMSX archive `Makefile.config`, `Makefile.in`, `scripts/*.py`, `src/themes.list`.

## Licenses and attribution

OpenSFX's `docs/readme.ptxt` says the sound set is CC-BY-SA-3.0 and the remaining files are dual-licensed GPL-2.0-or-later or CDDL-1.1. More specifically, `src/opensfx.psfo` labels the final 73 samples as 51 CC-BY-3.0, 21 CC0-1.0, and one CC-BY-SA-3.0. A conservative combined SPDX expression retaining those individual grants is `CC-BY-SA-3.0 AND CC-BY-3.0 AND CC0-1.0 AND (GPL-2.0-or-later OR CDDL-1.1)`. Ship upstream `docs/license.txt`, generated `docs/readme.txt`, and generated `src/opensfx.sfo` as license/attribution material. The README preserves original sound author names, links, editing credits, and license URLs; `.sfo` preserves sample-specific credits. Source: the OpenSFX source archive cited above, particularly `docs/readme.ptxt` sections 1.1 and 4 and `src/opensfx.psfo`.

OpenMSX is GPL-2.0-only, explicitly stated in `docs/readme.ptxt` and the source headers; the changelog records its switch to GPL v2 only. Keep generated `docs/license.txt`, `docs/readme.txt`, `src/themes.list` and `docs/redfarn_music_grant.txt`, which records permission for Jim Redfarn's tracks. README credits include the note that “Careless Love” is traditional/public domain and that “Moo Moo Boogie” was inspired by “Cow Cow Boogie”; retain these upstream notices without asserting independent composition provenance. Source: the OpenMSX source archive cited above.

Catcodec is GPL-2.0-only, stated in its source headers. Preserve `COPYING` with `%license` and ship the upstream readme. This source archive has no changelog file; the dated readme is kept as supplied. Source: the Catcodec source archive cited above.

## Checks to retain in packaging

Validate descriptor names, version, relative filenames, file existence, and every MD5. Check OpenSFX's catalogue is nonempty and its 73 sample entries decode correctly. Check the 31 music files start with MIDI's `MThd` signature. An installed-engine integration check should use an isolated empty home and verify OpenTTD discovers both real sets from the system baseset directory, without downloaded user assets masking a missing RPM. Catcodec needs to build successfully in COPR before OpenSFX is submitted; avoid submitting dependent builds concurrently into a repository where the tool is not available yet.
