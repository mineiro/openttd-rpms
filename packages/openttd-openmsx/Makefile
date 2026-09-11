PACKAGE := openttd-openmsx
OUTDIR ?= $(CURDIR)/../../dist/srpm
.PHONY: srpm
srpm:
	$(MAKE) -C ../.. srpm PACKAGE="$(PACKAGE)" OUTDIR="$(OUTDIR)"
