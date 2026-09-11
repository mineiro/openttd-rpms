%global upstream_version 1.0.5

Name:           catcodec
Version:        1.0.5
Release:        1%{?dist}
Summary:        Encode and decode OpenTTD sound catalogs
License:        GPL-2.0-only
URL:            https://www.openttd.org/downloads/catcodec-releases/latest
Source0:        https://cdn.openttd.org/catcodec-releases/%{upstream_version}/catcodec-%{upstream_version}-source.tar.xz
Source1:        check-catcodec.py
# License for the package-local validation script (source only).
Source2:        LICENSE
BuildRequires:  gcc-c++
BuildRequires:  make
BuildRequires:  python3

%description
Catcodec converts between OpenTTD sound catalogs and their individual PCM
WAVE samples. It is used to build the OpenSFX sound set from source.

%prep
%autosetup -n catcodec-%{upstream_version}
cp -p %{SOURCE2} packaging-test.LICENSE

%build
%make_build CXX=g++ CXXFLAGS="%{build_cxxflags} -Wno-multichar" LDFLAGS="%{build_ldflags}"

%install
install -Dpm 0755 catcodec %{buildroot}%{_bindir}/catcodec
install -Dpm 0644 docs/catcodec.1 %{buildroot}%{_mandir}/man1/catcodec.1

%check
python3 %{SOURCE1} ./catcodec

%files
%license COPYING
%doc docs/readme.txt
%{_bindir}/catcodec
%{_mandir}/man1/catcodec.1*

%changelog
* Fri Sep 11 2026 Jose Tiburcio Ribeiro Netto <jnetto@mineiro.io> - 1.0.5-1
- Package the encoder needed to build OpenSFX from source
