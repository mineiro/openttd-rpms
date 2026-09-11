#!/usr/bin/env python3
"""Select official releases, verify pinned sources, and build offline-ready SRPMs."""
import argparse
from datetime import datetime, timezone
from functools import cmp_to_key
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import tarfile
import tempfile
import urllib.request

import rpm
import yaml

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / 'packages/openttd'
SPEC = PACKAGE / 'openttd.spec'
LOCK = PACKAGE / 'release.json'
CDN = 'https://cdn.openttd.org'
VERSION = re.compile(r'([0-9]+(?:\.[0-9]+){1,2})(?:-(beta|RC)([1-9][0-9]*))?\Z')


def rpm_version(version):
    match = VERSION.fullmatch(version)
    if not match:
        raise ValueError(f'Unsupported release version: {version!r}')
    base, stage, number = match.groups()
    return base + (f'~{stage.lower()}{number}' if stage else '')


def compare(a, b):
    return rpm.labelCompare(('0', rpm_version(a), '0'), ('0', rpm_version(b), '0'))


def latest_version(index):
    versions = [str(item['version']) for item in index['latest']
                if item.get('folder') == 'openttd-releases'
                and item.get('name') in ('stable', 'testing')]
    if not versions:
        raise ValueError('No official stable/testing releases in index')
    # Validate all candidates, including ones that would sort behind the winner.
    for version in versions:
        rpm_version(version)
    return max(versions, key=cmp_to_key(compare))


def request(url):
    return urllib.request.urlopen(urllib.request.Request(
        url, headers={'User-Agent': 'openttd-rpms/1.0 (https://mineiro.io)'}), timeout=60)


def fetch_yaml(url):
    with request(url) as response:
        # Keep version scalars textual: YAML floats would turn 16.10 into 16.1.
        return yaml.load(response.read(2 * 1024 * 1024), Loader=yaml.BaseLoader)


def release_metadata(version, manifest):
    rpm_version(version)
    if str(manifest['version']) != version or manifest['category'] != 'openttd':
        raise ValueError('Release manifest identity mismatch')
    filename = f'openttd-{version}-source.tar.xz'
    matches = [f for f in manifest['dev_files'] if f['id'] == filename]
    if len(matches) != 1:
        raise ValueError('Expected exactly one source tarball in release manifest')
    source = matches[0]
    if not re.fullmatch(r'[a-f0-9]{64}', source['sha256sum']):
        raise ValueError('Invalid source SHA256')
    if not re.fullmatch(r'[1-9][0-9]*', str(source['size'])):
        raise ValueError('Invalid source size')
    size = int(source['size'])
    if size >= 256 * 1024 * 1024:
        raise ValueError('Unexpected source size')
    return {'upstream_version': version, 'rpm_version': rpm_version(version),
            'source': f'{CDN}/openttd-releases/{version}/{filename}',
            'sha256': source['sha256sum'], 'size': size}


def read_lock():
    lock = json.loads(LOCK.read_text())
    expected_url = f"{CDN}/openttd-releases/{lock['upstream_version']}/openttd-{lock['upstream_version']}-source.tar.xz"
    if lock['source'] != expected_url or lock['rpm_version'] != rpm_version(lock['upstream_version']):
        raise ValueError('Invalid release lock identity')
    spec = SPEC.read_text()
    for pattern, expected in [(r'^%global upstream_version (\S+)$', lock['upstream_version']),
                              (r'^Version:\s+(\S+)$', lock['rpm_version'])]:
        if re.search(pattern, spec, re.M).group(1) != expected:
            raise ValueError('Spec and release lock disagree')
    return lock


def verify_file(path, lock):
    with path.open('rb') as stream:
        digest = hashlib.file_digest(stream, 'sha256').hexdigest()
    if path.stat().st_size != lock['size'] or digest != lock['sha256']:
        raise ValueError(f'Checksum/size mismatch: {path}; refusing to replace the recorded checksum')


def fetch_source(lock):
    directory = PACKAGE / 'sources'
    directory.mkdir(exist_ok=True)
    path = directory / lock['source'].rsplit('/', 1)[1]
    if path.exists():
        verify_file(path, lock)
        return path
    with tempfile.NamedTemporaryFile(dir=directory, delete=False) as temp:
        temp_path = Path(temp.name)
        try:
            with request(lock['source']) as response:
                # Bound the download by the size attested in the manifest.
                remaining = lock['size'] + 1
                while remaining:
                    chunk = response.read(min(1024 * 1024, remaining))
                    if not chunk:
                        break
                    temp.write(chunk)
                    remaining -= len(chunk)
            temp.close()
            verify_file(temp_path, lock)
            temp_path.replace(path)
        finally:
            temp_path.unlink(missing_ok=True)
    return path


def bundle_inventory(source, version):
    """Review gate for changed vendored dependencies, including license changes."""
    prefix = f'openttd-{version}/src/3rdparty/'
    inventory = {}
    with tarfile.open(source) as archive:
        for member in archive:
            if member.isfile() and member.name.startswith(prefix):
                relative = member.name[len(prefix):]
                inventory[relative] = hashlib.sha256(archive.extractfile(member).read()).hexdigest()
    if not inventory:
        raise ValueError('Missing bundled dependency inventory')
    return inventory


def verify_bundles(source, version):
    expected = json.loads((PACKAGE / 'bundled-sources.json').read_text())
    actual = bundle_inventory(source, version)
    changed = sorted(k for k in expected.keys() | actual.keys() if expected.get(k) != actual.get(k))
    if changed:
        raise ValueError('Bundled source/license changes require review of License and Provides; '
                         'see docs/packaging-policy.md: ' + ', '.join(changed[:12]))


def update():
    old = read_lock()
    version = latest_version(fetch_yaml(f'{CDN}/latest.yaml'))
    if compare(version, old['upstream_version']) < 0:
        raise ValueError('Upstream index went backwards; refusing a downgrade')
    new = release_metadata(version, fetch_yaml(f'{CDN}/openttd-releases/{version}/manifest.yaml'))
    if compare(version, old['upstream_version']) == 0:
        if old != new:
            raise ValueError('Published release metadata changed; manual investigation required')
        print(f'Already tracking {version}')
        return
    source = fetch_source(new)
    verify_bundles(source, version)
    spec = SPEC.read_text()
    spec = re.sub(r'^%global upstream_version .+$', f'%global upstream_version {version}', spec, flags=re.M)
    spec = re.sub(r'^Version:.*$', f"Version:        {new['rpm_version']}", spec, flags=re.M)
    spec = re.sub(r'^Release:.*$', 'Release:        1%{?dist}', spec, flags=re.M)
    date = datetime.now(timezone.utc).strftime('%a %b %d %Y')
    entry = f"* {date} OpenTTD RPM automation <rpms@mineiro.io> - {new['rpm_version']}-1\n- Package upstream release {version}\n\n"
    spec = spec.replace('%changelog\n', '%changelog\n' + entry)
    SPEC.write_text(spec)
    LOCK.write_text(json.dumps(new, indent=2) + '\n')
    print(f'Updated to {version}')


def srpm(outdir):
    lock = read_lock()
    source = fetch_source(lock)
    verify_bundles(source, lock['upstream_version'])
    outdir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='openttd-srpm-') as work:
        top = Path(work)
        sources = top / 'SOURCES'
        sources.mkdir()
        shutil.copy2(source, sources)
        (sources / source.name).chmod(0o644)
        shutil.copy2(PACKAGE / 'org.openttd.OpenTTD.metainfo.xml', sources)
        subprocess.run(['rpmbuild', '-bs', '--define', f'_topdir {top}', '--define',
                        f'_srcrpmdir {outdir.resolve()}', '--define', 'dist %{nil}', str(SPEC)], check=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['update', 'fetch', 'srpm'])
    parser.add_argument('--outdir', type=Path, default=ROOT / 'dist/srpm')
    args = parser.parse_args()
    if args.command == 'update':
        update()
    elif args.command == 'srpm':
        srpm(args.outdir)
    else:
        lock = read_lock()
        source = fetch_source(lock)
        verify_bundles(source, lock['upstream_version'])
        print(f'Verified {source.name}')


if __name__ == '__main__':
    main()
