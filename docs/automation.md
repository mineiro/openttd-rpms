# Release automation

GitHub Actions checks the official OpenTTD CDN every hour at minute 23 (UTC).
GitHub scheduling can be delayed. A successful poll records a dated check in
`.github/upstream-check.txt` at least every 30 days, keeping repository activity
within GitHub's 60-day public-repository inactivity window even when upstream
has no new releases. Manual `workflow_dispatch` is also available. This is
polling, not an upstream webhook. Investigate failing runs promptly; prolonged
failures also prevent these successful-check commits.

The release workflow runs a separate matrix job for each managed package:
Catcodec, OpenSFX, OpenMSX and OpenTTD. Jobs run serially to avoid racing Git
pushes; one package's failure does not cancel the other jobs. Each job checks
out current main. The game tracks stable/testing releases and the data/tool
packages track stable releases only.

For each package, the workflow:

1. Reads `latest.yaml`, selects the highest version in that package's configured channels
   using RPM ordering, then verifies its `manifest.yaml` identity and source
   SHA256/size. No nightly snapshots and no automatic downgrades.
2. Stops if a published release's metadata changed or bundled sources or asset license/attribution files need
   review. Failures are visible in Actions logs and normal GitHub notifications.
3. Runs updater tests and lint, generates a verified source RPM, commits only
   that package's spec/release lock (plus the periodic check marker), and pushes the release record to main.
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
gh workflow run releases.yml --repo mineiro/openttd-rpms -f package=all
# Or select just one package:
gh workflow run releases.yml --repo mineiro/openttd-rpms -f package=openttd-opensfx
```

To rehearse locally without publishing:

```sh
make update
make check
make mock CHROOT=fedora-44-x86_64
```

To publish a verified SRPM using local COPR credentials:

```sh
python3 scripts/copr-build.py "$(python3 scripts/releases.py srpm-path --package openttd-opensfx)"
```

Optional COPR SCM setup uses `https://github.com/mineiro/openttd-rpms.git`,
committish `main`, subdirectory `packages/<name>`, spec `<name>.spec`, and
`make_srpm`. The scheduled publisher uploads the verified SRPM directly; it
needs no SCM webhook and does not race a second automatic build trigger.


## Bootstrapping audio packages

Publish Catcodec successfully before the first OpenSFX build: Fedora does not
supply that build dependency. COPR includes the project's own repository when
resolving build dependencies. OpenMSX has no dependency on Catcodec. After the
initial bootstrap, the scheduled jobs reconcile each package independently.

A data-only release does not rebuild or bump the game RPM. An unchanged game
NVR is skipped once all its targets have succeeded. Existing OpenTTD RPMs already
recommend these exact audio package names, so fresh installations gain audio
without another game rebuild. Existing users can explicitly install the two
new data packages and select them in Game Options.
