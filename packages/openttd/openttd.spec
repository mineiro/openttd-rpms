%global upstream_version 16.0-beta2

Name:           openttd
Version:        16.0~beta2
Release:        1%{?dist}
Summary:        Transport system simulation game

# Includes modified Squirrel, fmt, JSON, ICU scriptrun, MD5, OpenGL headers,
# and Monocypher (BSD option selected). Catch2 is used only by the test binary.
License:        GPL-2.0-only AND MIT AND Zlib AND Unicode-DFS-2016 AND BSD-2-Clause
URL:            https://www.openttd.org/
Source0:        https://cdn.openttd.org/openttd-releases/%{upstream_version}/openttd-%{upstream_version}-source.tar.xz
Source1:        org.openttd.OpenTTD.metainfo.xml

BuildRequires:  cmake
BuildRequires:  gcc-c++
BuildRequires:  ninja-build
BuildRequires:  desktop-file-utils
BuildRequires:  appstream
BuildRequires:  grfcodec
# Headless game regression tests need a graphics base set.
BuildRequires:  openttd-opengfx
BuildRequires:  pkgconfig(fontconfig)
BuildRequires:  pkgconfig(fluidsynth)
BuildRequires:  pkgconfig(freetype2)
BuildRequires:  pkgconfig(harfbuzz)
BuildRequires:  pkgconfig(icu-i18n)
BuildRequires:  pkgconfig(icu-uc)
BuildRequires:  pkgconfig(libcurl)
BuildRequires:  pkgconfig(liblzma)
BuildRequires:  pkgconfig(libpng)
BuildRequires:  pkgconfig(lzo2)
BuildRequires:  pkgconfig(opusfile)
BuildRequires:  pkgconfig(sdl2)
BuildRequires:  pkgconfig(gl)
BuildRequires:  pkgconfig(zlib)
Requires:       hicolor-icon-theme
Recommends:     openttd-opengfx >= 0.5.0
Recommends:     openttd-opensfx
Recommends:     openttd-openmsx
Recommends:     fluid-soundfont-gm

# Upstream integrates these directly; see docs/packaging-policy.md.
Provides:       bundled(squirrel) = 2.2.5~openttd
Provides:       bundled(fmt) = 11.1.4
Provides:       bundled(nlohmann_json) = 3.11.3
Provides:       bundled(monocypher) = 4.0.2
Provides:       bundled(icu-scriptrun)
Provides:       bundled(md5)

%description
OpenTTD is a transport simulation game inspired by Transport Tycoon Deluxe.
Build railways, roads, airports and shipping routes, and compete with other
transport companies in single-player and multiplayer games.

This package follows upstream testing and stable releases. It replaces the
Fedora openttd package and uses the same configuration and save directories.

%prep
%autosetup -n openttd-%{upstream_version}
mkdir bundled-licenses
cp src/3rdparty/squirrel/COPYRIGHT bundled-licenses/squirrel.txt
cp src/3rdparty/fmt/LICENSE.rst bundled-licenses/fmt.txt
cp src/3rdparty/nlohmann/LICENSE.MIT bundled-licenses/nlohmann-json.txt
cp src/3rdparty/icu/LICENSE bundled-licenses/icu-scriptrun.txt
cp src/3rdparty/monocypher/LICENCE.md bundled-licenses/monocypher.txt
cp src/3rdparty/openttd_social_integration_api/LICENSE bundled-licenses/social-api.txt
cp src/3rdparty/opengl/khrplatform.h bundled-licenses/opengl-khrplatform.h
cp src/3rdparty/md5/md5.cpp bundled-licenses/md5.cpp

%build
%cmake -G Ninja \
    -DCMAKE_BUILD_TYPE=RelWithDebInfo \
    -DCMAKE_INSTALL_BINDIR:PATH=%{_bindir} \
    -DCMAKE_INSTALL_DATADIR:PATH=%{_datadir} \
    -DCMAKE_INSTALL_DOCDIR:PATH=%{_docdir}/%{name} \
    -DGLOBAL_DIR:PATH=%{_datadir}/%{name} \
    -DOPTION_INSTALL_FHS=ON \
    -DOPTION_PACKAGE_DEPENDENCIES=OFF \
    -DOPTION_USE_ASSERTS=ON
%cmake_build

%install
%cmake_install
# RPM installs the license separately from documentation.
rm %{buildroot}%{_docdir}/%{name}/COPYING.md
install -Dpm 0644 media/openttd.svg %{buildroot}%{_datadir}/icons/hicolor/scalable/apps/openttd.svg
install -Dpm 0644 %{SOURCE1} %{buildroot}%{_metainfodir}/org.openttd.OpenTTD.metainfo.xml

%check
%ctest --output-on-failure
%{__cmake_builddir}/openttd --version | grep -F '%{upstream_version}'
desktop-file-validate %{buildroot}%{_datadir}/applications/openttd.desktop
appstreamcli validate --no-net %{buildroot}%{_metainfodir}/org.openttd.OpenTTD.metainfo.xml

%files
%license COPYING.md bundled-licenses
%doc %{_docdir}/%{name}
%{_bindir}/openttd
%{_datadir}/openttd/
%{_datadir}/applications/openttd.desktop
%{_metainfodir}/org.openttd.OpenTTD.metainfo.xml
%{_mandir}/man6/openttd.6*
%{_datadir}/icons/hicolor/*/apps/openttd.png
%{_datadir}/icons/hicolor/scalable/apps/openttd.svg
%{_datadir}/pixmaps/openttd.*.xpm

%changelog
* Fri Sep 11 2026 Jose Tiburcio Ribeiro Netto <jnetto@mineiro.io> - 16.0~beta2-1
- Package upstream testing release with tests and verified release sources
