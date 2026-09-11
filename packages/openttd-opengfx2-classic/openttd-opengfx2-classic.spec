%global upstream_version 0.8.1
%global font_commit 0fc6324b32ce49b1eb3f37bf8ad36b598f044e79

Name:           openttd-opengfx2-classic
Version:        0.8.1
Release:        1%{?dist}
Summary:        Updated classic-style base graphics for OpenTTD
License:        GPL-2.0-only AND OFL-1.1
URL:            https://github.com/OpenTTD/OpenGFX2
# Generated from the immutable release commit and verified LFS objects recorded
# in release.json. Includes editable artwork; see packaging-source.json inside.
Source0:        opengfx2_classic-%{upstream_version}-source.tar.xz
Source1:        https://api.github.com/repos/OpenTTD/OpenTTD-TTF/tarball/%{font_commit}#/openttd-ttf-%{font_commit}.tar.gz
Source2:        build-opengfx2-fonts.py
Source3:        check-graphics.py
Source4:        LICENSE
Patch0:         0001-offline-reproducible-linux-build.patch
BuildArch:      noarch
BuildRequires:  make
BuildRequires:  patch
BuildRequires:  zip
BuildRequires:  fontforge
BuildRequires:  grfcodec
BuildRequires:  nml >= 0.8.1
BuildRequires:  python3
BuildRequires:  python3-numpy
BuildRequires:  python3-pillow
BuildRequires:  python3-scikit-image
BuildRequires:  python3-tqdm
BuildRequires:  python3-blend-modes >= 2.2.0

%description
OpenGFX2 Classic is a revised base graphics set for OpenTTD with updated
pixel artwork. It provides the classic 8-bit style and can be installed
alongside the original OpenGFX set. Select it in OpenTTD's Game Options.

%prep
%autosetup -p1 -n opengfx2_classic-%{upstream_version}-source
mkdir -p graphics/fonts/openttd-ttf
tar -xzf %{SOURCE1} --strip-components=1 -C graphics/fonts/openttd-ttf
cp -p %{SOURCE4} packaging-test.LICENSE
cp graphics/fonts/openttd-ttf/LICENSE font-repository-LICENSE
cp graphics/fonts/openttd-ttf/readme.md font-repository-readme.md
# These are generated font files/previews (or LFS pointers to them). Rebuild the
# four required fonts from their preferred SFD source files, never from Git HEAD.
find graphics/fonts/openttd-ttf -name '*.ttf' -delete

%build
export PYTHONHASHSEED=0 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
export OPENGFX2_WORKERS=%{_smp_build_ncpus}
fontforge -lang=py -script %{SOURCE2} graphics/fonts/openttd-ttf
%make_build baseset

%install
install -d %{buildroot}%{_datadir}/openttd/baseset/opengfx2-classic
install -pm 0644 baseset/opengfx2_8.obg baseset/*_8.grf %{buildroot}%{_datadir}/openttd/baseset/opengfx2-classic/

%check
%{python3} %{SOURCE3} %{buildroot}%{_datadir}/openttd/baseset/opengfx2-classic %{version}

%files
%license LICENSE credits.md font-license.txt font-repository-LICENSE font-repository-readme.md
%doc README.md CHANGELOG.md packaging-source.json
%dir %{_datadir}/openttd
%dir %{_datadir}/openttd/baseset
%{_datadir}/openttd/baseset/opengfx2-classic/

%changelog
* Fri Sep 11 2026 Jose Tiburcio Ribeiro Netto <jnetto@mineiro.io> - 0.8.1-1
- Build Classic graphics from complete pinned sources and source-built fonts
