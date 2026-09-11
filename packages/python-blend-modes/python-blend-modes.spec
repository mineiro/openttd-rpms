%global upstream_version 2.2.0

Name:           python-blend-modes
Version:        2.2.0
Release:        1%{?dist}
Summary:        Image blending functions for NumPy arrays
License:        MIT
URL:            https://github.com/flrs/blend_modes
Source0:        https://files.pythonhosted.org/packages/source/b/blend_modes/blend_modes-%{upstream_version}.tar.gz
Source1:        check-blend-modes.py
Source2:        LICENSE
BuildArch:      noarch
BuildRequires:  python3-devel
BuildRequires:  pyproject-rpm-macros
BuildRequires:  python3-setuptools
BuildRequires:  python3-wheel
BuildRequires:  python3-pip
BuildRequires:  python3-installer
BuildRequires:  python3-numpy

%description
Blend Modes implements image blending operations on NumPy RGBA arrays.
OpenGFX2 uses it to generate sprites from its source artwork.

%package -n python3-blend-modes
Summary:        %{summary}

%description -n python3-blend-modes
Blend Modes implements image blending operations on NumPy RGBA arrays.
OpenGFX2 uses it to generate sprites from its source artwork.

%prep
%autosetup -n blend_modes-%{upstream_version}
cp -p %{SOURCE2} packaging-test.LICENSE

%build
%pyproject_wheel

%install
%pyproject_install
%pyproject_save_files blend_modes

%check
%pyproject_check_import
# The sdist omits the PNG fixtures required by its upstream tests. Exercise
# actual blend operations on generated arrays instead of skipping validation.
PYTHONPATH="%{buildroot}%{python3_sitelib}" %{python3} %{SOURCE1}

%files -n python3-blend-modes -f %{pyproject_files}
%doc README.md CHANGELOG.md

%changelog
* Fri Sep 11 2026 Jose Tiburcio Ribeiro Netto <jnetto@mineiro.io> - 2.2.0-1
- Package the image-blending build dependency for OpenGFX2
