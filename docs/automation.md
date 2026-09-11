# Release automation

GitHub Actions checks the official OpenTTD CDN every hour at minute 23 (UTC).
GitHub scheduling can be delayed and inactive public repositories may have
scheduled workflows disabled after 60 days. Check Actions periodically; manual
`workflow_dispatch` is also available. It is polling, not an upstream webhook.

The release workflow:

1. Reads `latest.yaml`, selects the highest official stable/testing version
   using RPM ordering, then verifies its `manifest.yaml` identity and source
   SHA256/size. No nightly snapshots and no automatic downgrades.
2. Stops if a published release's metadata changed or bundled sources need
   review. Failures are visible in Actions logs and normal GitHub notifications.
3. Runs updater tests and lint, generates a verified source RPM, commits only
   the spec/release lock, and pushes the release record to main.
4. Reconciles that NVR against COPR on **every** run, even when the version did
   not change. Watches matching running builds, skips successful targets and
   submits only missing/failed targets with networking disabled.
5. Waits for COPR, where `%check` runs on each architecture, and retains the
   source RPM in Actions artifacts. Interrupted runs resume on the next poll.

Recording a version is not proof its binaries succeeded. Check COPR per-chroot
results. COPR publishes each successful target independently; a failed Rawhide
build does not roll back successful Fedora stable builds. No cross-chroot
atomic promotion is promised. A failed build can be retried at the same NVR
only when the package inputs have not changed; fixes require a Release bump.
The reconciler examines the latest 100 builds for this package.

## Setup

Project: `mineiro/openttd`. Repository: `mineiro/openttd-rpms`.
Enable Fedora 43 and 44 (supported stable), Fedora 45 (branched prerelease),
and Rawhide, for x86_64 and aarch64. COPR follows Fedora branching; remove EOL
chroots during routine maintenance. The workflow reads enabled chroots from
COPR, so newly enabled targets are picked up even without a version bump.

Set repository secret `COPR_CONFIG` to a COPR API configuration authorized to
build this project. Credentials never enter Git; the workflow writes a mode-600
file for the build step and removes it on exit. Rotate it before expiration.
Use a dedicated COPR account with builder permission if narrower credentials
are required; ordinary COPR API tokens inherit their owner's privileges.

The scheduled workflow has contents-write access only in its release job. PR
checks have read-only access and no COPR credentials. Third-party actions are
pinned to commit hashes and Dependabot keeps them current. The publisher is
restricted to main in this repository; fork schedules cannot publish here.

To run the complete publisher manually:

```sh
gh workflow run releases.yml --repo mineiro/openttd-rpms
```

To rehearse locally without publishing:

```sh
make update
make check
make mock CHROOT=fedora-44-x86_64
```

To publish a verified SRPM using local COPR credentials:

```sh
python3 scripts/copr-build.py dist/srpm/openttd-*.src.rpm
```

Optional COPR SCM setup uses `https://github.com/mineiro/openttd-rpms.git`,
committish `main`, subdirectory `packages/openttd`, spec `openttd.spec`, and
`make_srpm`. The scheduled publisher uploads the verified SRPM directly; it
needs no SCM webhook and does not race a second automatic build trigger.
