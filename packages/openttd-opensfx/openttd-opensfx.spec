%global upstream_version 1.0.3

Name:           openttd-opensfx
Version:        1.0.3
Release:        1%{?dist}
Summary:        Free sound effects for OpenTTD
# Individual samples retain their CC licenses. Choose GPL for the remaining
# files that upstream offers under GPL-2.0-or-later OR CDDL-1.1.
License:        CC-BY-SA-3.0 AND CC-BY-3.0 AND CC0-1.0 AND GPL-2.0-or-later
URL:            https://www.openttd.org/downloads/opensfx-releases/latest
Source0:        https://cdn.openttd.org/opensfx-releases/%{upstream_version}/opensfx-%{upstream_version}-source.tar.xz
Source1:        check-baseset.py
# License for the package-local validation script (source only).
Source2:        LICENSE
BuildArch:      noarch
BuildRequires:  catcodec >= 1.0.5
BuildRequires:  make
BuildRequires:  which
BuildRequires:  python3

%description
OpenSFX provides free sound effects for OpenTTD, replacing the original
Transport Tycoon Deluxe sound files. It contains sounds for vehicles,
industries and game events.

%prep
%autosetup -n opensfx-%{upstream_version}-source
cp -p %{SOURCE2} packaging-test.LICENSE
# Force generation from the source samples and attribution manifest.
rm -f opensfx.cat opensfx.obs src/opensfx.sfo

%build
%make_build sound doc CATCODEC=catcodec UNIX2DOS=

%install
install -d %{buildroot}%{_datadir}/openttd/baseset/opensfx
install -pm 0644 opensfx.cat opensfx.obs %{buildroot}%{_datadir}/openttd/baseset/opensfx/

%check
python3 %{SOURCE1} %{buildroot}%{_datadir}/openttd/baseset/opensfx/opensfx.obs OpenSFX %{version} 73 --sample-source .

%files
%license docs/license.txt docs/readme.txt docs/digifish_music_grant.txt src/opensfx.sfo
%doc docs/changelog.txt
%dir %{_datadir}/openttd
%dir %{_datadir}/openttd/baseset
%{_datadir}/openttd/baseset/opensfx/

%changelog
* Fri Sep 11 2026 Jose Tiburcio Ribeiro Netto <jnetto@mineiro.io> - 1.0.3-1
- Build the sound set from source and preserve sample-specific attribution
