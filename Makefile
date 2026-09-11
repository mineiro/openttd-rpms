SHELL := /bin/bash
PACKAGE ?= openttd
PACKAGES := catcodec openttd-opensfx openttd-openmsx openttd
OUTDIR ?= $(CURDIR)/dist/srpm
CHROOT ?= fedora-44-x86_64
.PHONY: list check check-specs check-sources update update-all srpm srpm-all mock
list:
	@printf '%s\n' $(PACKAGES)
check: check-specs
	python3 -m unittest discover -s tests -v
check-specs:
	@set -e; for package in $(PACKAGES); do rpmspec -P "packages/$$package/$$package.spec" >/dev/null; done
	rpmlint -c rpmlint.toml packages/*/*.spec
check-sources:
	python3 scripts/releases.py fetch --package "$(PACKAGE)"
update:
	python3 scripts/releases.py update --package "$(PACKAGE)"
update-all:
	@set -e; for package in $(PACKAGES); do $(MAKE) update PACKAGE="$$package"; done
srpm:
	python3 scripts/releases.py srpm --package "$(PACKAGE)" --outdir "$(OUTDIR)"
srpm-all:
	@set -e; for package in $(PACKAGES); do $(MAKE) srpm PACKAGE="$$package"; done
mock: srpm
	mock -r "$(CHROOT)" --rebuild "$$(python3 scripts/releases.py srpm-path --package "$(PACKAGE)" --outdir "$(OUTDIR)")" --resultdir "$(CURDIR)/dist/mock/$(CHROOT)/$(PACKAGE)"
