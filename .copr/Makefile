# COPR SCM make_srpm; set subdirectory to packages/openttd.
.PHONY: srpm
srpm:
	dnf -y install --setopt=install_weak_deps=0 python3 python3-pyyaml python3-rpm rpm-build make
	$(MAKE) srpm OUTDIR="$(outdir)"
