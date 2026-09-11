SHELL := /bin/bash
PACKAGE ?= openttd
OUTDIR ?= $(CURDIR)/dist/srpm
CHROOT ?= fedora-44-x86_64
.PHONY: list check check-specs check-sources update srpm mock
list:
	@echo openttd
check: check-specs
	python3 -m unittest discover -s tests -v
check-specs:
	rpmspec -P packages/openttd/openttd.spec >/dev/null
	rpmlint packages/openttd/openttd.spec
check-sources:
	python3 scripts/releases.py fetch
update:
	python3 scripts/releases.py update
srpm:
	@test "$(PACKAGE)" = openttd
	python3 scripts/releases.py srpm --outdir "$(OUTDIR)"
mock: srpm
	mock -r "$(CHROOT)" --rebuild "$$(ls -t "$(OUTDIR)"/openttd-*.src.rpm | head -1)" --resultdir "$(CURDIR)/dist/mock/$(CHROOT)"
