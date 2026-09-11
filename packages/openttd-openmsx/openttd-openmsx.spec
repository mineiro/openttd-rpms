%global upstream_version 0.4.2

Name:           openttd-openmsx
Version:        0.4.2
Release:        1%{?dist}
Summary:        Free music for OpenTTD
License:        GPL-2.0-only
URL:            https://www.openttd.org/downloads/openmsx-releases/latest
Source0:        https://cdn.openttd.org/openmsx-releases/%{upstream_version}/openmsx-%{upstream_version}-source.tar.xz
Source1:        check-baseset.py
# License for the package-local validation script (source only).
Source2:        LICENSE
BuildArch:      noarch
BuildRequires:  make
BuildRequires:  which
BuildRequires:  python3

%description
OpenMSX provides free background music for OpenTTD, replacing the original
Transport Tycoon Deluxe music files. It includes a theme and three playlists
of MIDI tracks.

%prep
%autosetup -n openmsx-%{upstream_version}-source
cp -p %{SOURCE2} packaging-test.LICENSE
sed -i '1s@^#!.*python.*$@#!/usr/bin/python3@' scripts/*.py
# Rebuild the descriptor instead of trusting the pre-generated copy.
rm -f openmsx.obm

%build
%make_build music doc UNIX2DOS=

%install
install -d %{buildroot}%{_datadir}/openttd/baseset/openmsx
install -pm 0644 openmsx.obm src/*.mid %{buildroot}%{_datadir}/openttd/baseset/openmsx/

%check
python3 %{SOURCE1} %{buildroot}%{_datadir}/openttd/baseset/openmsx/openmsx.obm OpenMSX %{version} 31

%files
%license docs/license.txt docs/readme.txt docs/redfarn_music_grant.txt src/themes.list
%doc docs/changelog.txt
%dir %{_datadir}/openttd
%dir %{_datadir}/openttd/baseset
%{_datadir}/openttd/baseset/openmsx/

%changelog
* Fri Sep 11 2026 Jose Tiburcio Ribeiro Netto <jnetto@mineiro.io> - 0.4.2-1
- Package MIDI sources with a regenerated and verified music descriptor
