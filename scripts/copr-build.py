#!/usr/bin/env python3
"""Reconcile an SRPM against COPR, retrying only missing/failed chroots."""
import argparse
import os
from pathlib import Path
import subprocess
import time

ACTIVE = {'importing', 'pending', 'starting', 'running', 'waiting'}


def remaining_chroots(builds, version, wanted):
    """Return missing targets and relevant running builds, newest attempts win."""
    latest = {}
    for build, chroots in sorted(builds, key=lambda pair: pair[0]['id'], reverse=True):
        if (build.get('source_package') or {}).get('version') != version:
            continue
        for chroot in chroots:
            if chroot['name'] in wanted:
                latest.setdefault(chroot['name'], (chroot['state'], build['id']))
    missing = set(wanted)
    active = set()
    for name, (state, build_id) in latest.items():
        if state == 'succeeded':
            missing.discard(name)
        elif state in ACTIVE:
            active.add(build_id)
    return missing, active


def wait(client, build_id, deadline):
    print(f'https://copr.fedorainfracloud.org/coprs/build/{build_id}/', flush=True)
    while time.monotonic() < deadline:
        build = client.build_proxy.get(build_id)
        if build.state == 'succeeded':
            return
        if build.state not in ACTIVE:
            raise RuntimeError(f'COPR build {build_id}: {build.state}; next run retries failed targets')
        print(f'Build {build_id}: {build.state}', flush=True)
        time.sleep(45)
    raise TimeoutError(f'Build {build_id} still running; next run resumes watching it')


def main():
    from copr.v3 import Client
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('srpm', type=Path)
    parser.add_argument('--project', default='mineiro/openttd')
    parser.add_argument('--timeout', type=int, default=6600)
    args = parser.parse_args()
    owner, project = args.project.split('/')
    name, version = subprocess.check_output(
        ['rpm', '-qp', '--qf', '%{NAME} %{VERSION}-%{RELEASE}', str(args.srpm)], text=True).split()
    if name != 'openttd':
        raise ValueError('Expected an openttd source RPM')
    client = Client.create_from_config_file()
    wanted = set(client.project_proxy.get(owner, project).chroot_repos)
    if not wanted:
        raise ValueError('COPR project has no enabled chroots')
    deadline = time.monotonic() + args.timeout
    builds = list(client.build_proxy.get_list(owner, project, packagename=name,
                                             pagination={'limit': 100}))
    candidates = []
    for build in builds:
        if (build.get('source_package') or {}).get('version') == version:
            candidates.append((build, list(client.build_chroot_proxy.get_list(build.id))))
        elif not build.get('source_package') and build.state in ACTIVE:
            # An import has no NVR yet. Wait for it rather than uploading duplicates.
            wait(client, build.id, deadline)
            raise RuntimeError('An import completed; rerun to reconcile its package version')
    missing, active = remaining_chroots(candidates, version, wanted)
    if active:
        for build_id in sorted(active):
            wait(client, build_id, deadline)
        # Reload actual per-chroot outcomes, including cancelled/excluded targets.
        candidates = [(build, list(client.build_chroot_proxy.get_list(build['id'])))
                      for build, _ in candidates]
        missing, active = remaining_chroots(candidates, version, wanted)
    if not missing:
        print(f'{name}-{version} already succeeded on all {len(wanted)} enabled chroots')
        return
    build = client.build_proxy.create_from_file(owner, project, str(args.srpm),
                                                buildopts={'chroots': sorted(missing), 'enable_net': False})
    if output := os.environ.get('GITHUB_OUTPUT'):
        with open(output, 'a') as stream:
            stream.write(f'submitted=true\nbuild_id={build.id}\n')
    wait(client, build.id, deadline)
    states = {c.name: c.state for c in client.build_chroot_proxy.get_list(build.id)}
    if any(states.get(name) != 'succeeded' for name in missing):
        raise RuntimeError(f'Incomplete COPR chroot results: {states}')
    print(f'{name}-{version}: all {len(wanted)} targets built successfully')


if __name__ == '__main__':
    main()
