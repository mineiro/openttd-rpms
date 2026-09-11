#!/usr/bin/env python3
"""Select official releases, verify pinned sources, and build offline-ready SRPMs."""
import argparse
from datetime import datetime, timezone
from dataclasses import dataclass
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
@dataclass(frozen=True)
class Package:
    name: str
    upstream: str
    channels: tuple = ('stable',)
    unpack_suffix: str = ''
    license_files: tuple = ()
    extra_sources: tuple = ()
    source_kind: str = 'cdn'

    @property
    def directory(self):
        return ROOT / 'packages' / self.name

    @property
    def spec(self):
        return self.directory / f'{self.name}.spec'

    @property
    def lock(self):
        return self.directory / 'release.json'

    @property
    def review_file(self):
        return self.directory / ('bundled-sources.json' if self.name == 'openttd' else 'licenses.json')


PACKAGES = {
    'catcodec': Package('catcodec', 'catcodec', license_files=('COPYING', 'docs/readme.txt'),
                        extra_sources=('scripts/check-catcodec.py', 'LICENSE')),
    'openttd-opensfx': Package('openttd-opensfx', 'opensfx', unpack_suffix='-source',
        license_files=('docs/license.txt', 'docs/readme.ptxt', 'docs/digifish_music_grant.txt', 'src/opensfx.psfo'),
        extra_sources=('scripts/check-baseset.py', 'LICENSE')),
    'openttd-openmsx': Package('openttd-openmsx', 'openmsx', unpack_suffix='-source',
        license_files=('docs/license.ptxt', 'docs/readme.ptxt', 'docs/redfarn_music_grant.txt', 'src/themes.list'),
        extra_sources=('scripts/check-baseset.py', 'LICENSE')),
    'python-blend-modes': Package('python-blend-modes', 'blend_modes', source_kind='pypi',
        license_files=('LICENSE.txt',), extra_sources=('scripts/check-blend-modes.py', 'LICENSE')),
    'openttd-opengfx2-classic': Package('openttd-opengfx2-classic', 'opengfx2_classic',
        source_kind='git-lfs', unpack_suffix='-source',
        license_files=('LICENSE', 'README.md', 'credits.md', 'graphics/fonts/charactergrab.py', 'baseset/lang/english.lng'),
        extra_sources=('scripts/build-opengfx2-fonts.py', 'scripts/check-graphics.py', 'LICENSE')),
    'openttd': Package('openttd', 'openttd', channels=('stable', 'testing'),
        extra_sources=('packages/openttd/org.openttd.OpenTTD.metainfo.xml', 'packages/openttd/openttd-fonts.LICENSE')),
}
DEFAULT = PACKAGES['openttd']
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


def latest_version(index, package=DEFAULT):
    versions = [str(item['version']) for item in index['latest']
                if item.get('folder') == f'{package.upstream}-releases'
                and item.get('name') in package.channels]
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


def release_metadata(version, manifest, package=DEFAULT):
    rpm_version(version)
    if package.source_kind == 'pypi':
        from source_providers import pypi_metadata
        return pypi_metadata(package.upstream, version)
    if package.source_kind == 'git-lfs':
        from source_providers import graphics_metadata
        return graphics_metadata(version, manifest)
    if str(manifest['version']) != version or manifest['category'] != package.upstream:
        raise ValueError('Release manifest identity mismatch')
    filename = f'{package.upstream}-{version}-source.tar.xz'
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
            'source': f'{CDN}/{package.upstream}-releases/{version}/{filename}',
            'sha256': source['sha256sum'], 'size': size}


def read_lock(package=DEFAULT):
    lock = json.loads(package.lock.read_text())
    expected_url = f"{CDN}/{package.upstream}-releases/{lock['upstream_version']}/{package.upstream}-{lock['upstream_version']}-source.tar.xz"
    if package.source_kind == 'pypi':
        expected_url = f"https://files.pythonhosted.org/packages/source/{package.upstream[0]}/{package.upstream}/{package.upstream}-{lock['upstream_version']}.tar.gz"
    elif package.source_kind == 'git-lfs':
        from source_providers import GFX_REPO, FONTS_REPO, FONTS_COMMIT
        if not re.fullmatch(r'[a-f0-9]{40}', lock['commit']):
            raise ValueError('Invalid graphics commit')
        expected_url = f"https://api.github.com/repos/{GFX_REPO}/tarball/{lock['commit']}"
        if lock['fonts']['source'] != f'https://api.github.com/repos/{FONTS_REPO}/tarball/{FONTS_COMMIT}':
            raise ValueError('Unexpected font source')
    if lock['source'] != expected_url or lock['rpm_version'] != rpm_version(lock['upstream_version']):
        raise ValueError('Invalid release lock identity')
    spec = package.spec.read_text()
    for pattern, expected in [(r'^Name:\s+(\S+)$', package.name),
                              (r'^%global upstream_version (\S+)$', lock['upstream_version']),
                              (r'^Version:\s+(\S+)$', lock['rpm_version'])]:
        if re.search(pattern, spec, re.M).group(1) != expected:
            raise ValueError('Spec and release lock disagree')
    return lock


def verify_file(path, lock):
    with path.open('rb') as stream:
        digest = hashlib.file_digest(stream, 'sha256').hexdigest()
    if path.stat().st_size != lock['size'] or digest != lock['sha256']:
        raise ValueError(f'Checksum/size mismatch: {path}; refusing to replace the recorded checksum')


def fetch_source(lock, package=DEFAULT):
    directory = package.directory / 'sources'
    directory.mkdir(exist_ok=True)
    filename = lock.get('filename', lock['source'].rsplit('/', 1)[1])
    if Path(filename).name != filename:
        raise ValueError('Invalid local source filename')
    path = directory / filename
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
    prefix = f'openttd-{version}/'
    inventory = {}
    with tarfile.open(source) as archive:
        for member in archive:
            if not member.isfile() or not member.name.startswith(prefix):
                continue
            relative = member.name[len(prefix):]
            is_code = relative.startswith('src/3rdparty/')
            is_font = relative.startswith('media/baseset/') and (relative.endswith('.ttf') or relative.endswith('OpenTTD-font.md'))
            if is_code or is_font:
                inventory[relative] = hashlib.sha256(archive.extractfile(member).read()).hexdigest()
    if not inventory:
        raise ValueError('Missing bundled dependency inventory')
    return inventory


def license_inventory(source, version, package):
    prefix = f'{package.upstream}-{version}{package.unpack_suffix}/'
    with tarfile.open(source) as archive:
        if package.source_kind == 'git-lfs':
            from source_providers import archive_root
            prefix = archive_root(archive)
        return {name: hashlib.sha256(archive.extractfile(prefix + name).read()).hexdigest()
                for name in package.license_files}


def verify_bundles(source, version, package=DEFAULT):
    expected = json.loads(package.review_file.read_text())
    actual = (bundle_inventory(source, version) if package.name == 'openttd'
              else license_inventory(source, version, package))
    changed = sorted(k for k in expected.keys() | actual.keys() if expected.get(k) != actual.get(k))
    if changed:
        raise ValueError('Bundled source/license changes require review of License and Provides; '
                         'see docs/packaging-policy.md: ' + ', '.join(changed[:12]))


def update(package=DEFAULT):
    old = read_lock(package)
    if package.source_kind == 'pypi':
        from source_providers import get_json
        version = get_json(f'https://pypi.org/pypi/{package.upstream}/json')['info']['version']
        rpm_version(version)
    else:
        version = latest_version(fetch_yaml(f'{CDN}/latest.yaml'), package)
    if compare(version, old['upstream_version']) < 0:
        raise ValueError('Upstream index went backwards; refusing a downgrade')
    manifest = (None if package.source_kind == 'pypi' else
                fetch_yaml(f'{CDN}/{package.upstream}-releases/{version}/manifest.yaml'))
    new = release_metadata(version, manifest, package)
    if compare(version, old['upstream_version']) == 0:
        if old != new:
            raise ValueError('Published release metadata changed; manual investigation required')
        print(f'{package.name}: already tracking {version}')
        return
    source = fetch_source(new, package)
    verify_bundles(source, version, package)
    spec = package.spec.read_text()
    spec = re.sub(r'^%global upstream_version .+$', f'%global upstream_version {version}', spec, flags=re.M)
    spec = re.sub(r'^Version:.*$', f"Version:        {new['rpm_version']}", spec, flags=re.M)
    spec = re.sub(r'^Release:.*$', 'Release:        1%{?dist}', spec, flags=re.M)
    date = datetime.now(timezone.utc).strftime('%a %b %d %Y')
    entry = f"* {date} OpenTTD RPM automation <rpms@mineiro.io> - {new['rpm_version']}-1\n- Package upstream release {version}\n\n"
    spec = spec.replace('%changelog\n', '%changelog\n' + entry)
    package.spec.write_text(spec)
    package.lock.write_text(json.dumps(new, indent=2) + '\n')
    print(f'{package.name}: updated to {version}')


def srpm(outdir, package=DEFAULT):
    lock = read_lock(package)
    source = fetch_source(lock, package)
    verify_bundles(source, lock['upstream_version'], package)
    extra = []
    if package.source_kind == 'git-lfs':
        from source_providers import prepare_graphics
        extra.append(fetch_source(lock['fonts'], package))
        source = prepare_graphics(source, lock, package.directory / 'sources', ROOT / '.cache/lfs-objects')
    outdir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='openttd-srpm-') as work:
        top = Path(work)
        sources = top / 'SOURCES'
        sources.mkdir()
        shutil.copy2(source, sources)
        (sources / source.name).chmod(0o644)
        for path in extra:
            shutil.copy2(path, sources)
            (sources / path.name).chmod(0o644)
        for relative in package.extra_sources:
            shutil.copy2(ROOT / relative, sources)
        for patch in sorted((package.directory / 'patches').glob('*.patch')):
            shutil.copy2(patch, sources)
        command = ['rpmbuild', '-bs', '--define', f'_topdir {top}', '--define',
                   f'_srcrpmdir {outdir.resolve()}', '--define', 'dist %{nil}']
        if package.source_kind == 'git-lfs':
            # The complete artwork is already XZ-compressed; avoid expensive recompression.
            command.extend(['--define', '_source_payload w1.zstdio'])
        subprocess.run(command + [str(package.spec)], check=True)


def srpm_path(outdir, package=DEFAULT):
    nvr = subprocess.check_output(['rpmspec', '-q', '--srpm', '--define', 'dist %{nil}',
        '--qf', '%{NAME}-%{VERSION}-%{RELEASE}', str(package.spec)], text=True).strip()
    return outdir.resolve() / f'{nvr}.src.rpm'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['update', 'fetch', 'srpm', 'srpm-path'])
    parser.add_argument('--outdir', type=Path, default=ROOT / 'dist/srpm')
    parser.add_argument('--package', choices=PACKAGES, default='openttd')
    args = parser.parse_args()
    package = PACKAGES[args.package]
    if args.command == 'update':
        update(package)
    elif args.command == 'srpm':
        srpm(args.outdir, package)
    elif args.command == 'srpm-path':
        print(srpm_path(args.outdir, package))
    else:
        lock = read_lock(package)
        source = fetch_source(lock, package)
        verify_bundles(source, lock['upstream_version'], package)
        print(f'Verified {source.name}')


if __name__ == '__main__':
    main()
