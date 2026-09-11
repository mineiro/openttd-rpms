"""Verified PyPI inputs and complete, offline Git-LFS graphics source bundles."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
import hashlib
import fcntl
import io
import json
from pathlib import Path, PurePosixPath
import re
import tarfile
import tempfile
import urllib.request

FONTS_REPO = 'OpenTTD/OpenTTD-TTF'
FONTS_COMMIT = '0fc6324b32ce49b1eb3f37bf8ad36b598f044e79'
GFX_REPO = 'OpenTTD/OpenGFX2'
AGENT = 'openttd-rpms/1.0 (https://mineiro.io)'


def request(url, data=None, headers=None):
    if not url.startswith('https://'):
        raise ValueError('Source transport must use HTTPS')
    return urllib.request.urlopen(urllib.request.Request(url, data=data,
        headers={'User-Agent': AGENT, **(headers or {})}), timeout=120)


def get_json(url, data=None, headers=None):
    with request(url, data, headers) as response:
        return json.load(response)


def pypi_metadata(upstream, version):
    data = get_json(f'https://pypi.org/pypi/{upstream}/{version}/json')
    filename = f'{upstream}-{version}.tar.gz'
    files = [f for f in data['urls'] if f['packagetype'] == 'sdist' and f['filename'] == filename]
    if len(files) != 1 or data['info']['version'] != version:
        raise ValueError('Unexpected PyPI source distribution')
    source = files[0]
    if not re.fullmatch(r'[a-f0-9]{64}', source['digests']['sha256']) or not 0 < source['size'] < 256 * 1024 * 1024:
        raise ValueError('Invalid PyPI source integrity metadata')
    return dict(upstream_version=version, rpm_version=version,
        source=f'https://files.pythonhosted.org/packages/source/{upstream[0]}/{upstream}/{filename}',
        sha256=source['digests']['sha256'], size=source['size'])


def git_archive(repo, commit, filename):
    if not re.fullmatch(r'[a-f0-9]{40}', commit):
        raise ValueError('Expected immutable Git commit')
    url = f'https://api.github.com/repos/{repo}/tarball/{commit}'
    with request(url) as response:
        data = response.read(32 * 1024 * 1024 + 1)
    if len(data) > 32 * 1024 * 1024:
        raise ValueError('Git source archive exceeds reviewed size limit')
    return dict(source=url, filename=filename, sha256=hashlib.sha256(data).hexdigest(), size=len(data))


def graphics_metadata(version, manifest):
    if manifest['category'] != 'opengfx2_classic' or str(manifest['version']) != version:
        raise ValueError('Graphics manifest identity mismatch')
    filename = f'opengfx2_classic-{version}-all.zip'
    matches = [f for f in manifest['files'] if f['id'] == filename]
    if len(matches) != 1 or not re.fullmatch(r'[a-f0-9]{64}', matches[0]['sha256sum']):
        raise ValueError('Missing released Classic reference')
    ref = get_json(f'https://api.github.com/repos/{GFX_REPO}/git/ref/tags/{version}')['object']
    for _ in range(5):
        if ref['type'] == 'commit':
            break
        if ref['type'] != 'tag':
            raise ValueError('Release tag does not identify a commit')
        ref = get_json(f'https://api.github.com/repos/{GFX_REPO}/git/tags/{ref["sha"]}')['object']
    if ref['type'] != 'commit':
        raise ValueError('Nested release tag limit exceeded')
    commit = ref['sha']
    info = get_json(f'https://api.github.com/repos/{GFX_REPO}/git/commits/{commit}')
    source = git_archive(GFX_REPO, commit, f'opengfx2-git-{commit}.tar.gz')
    fonts = git_archive(FONTS_REPO, FONTS_COMMIT, f'openttd-ttf-{FONTS_COMMIT}.tar.gz')
    return dict(upstream_version=version, rpm_version=version, **source,
        commit=commit, commit_date=info['committer']['date'], fonts=fonts,
        reference_binary=dict(source=f'https://cdn.openttd.org/opengfx2_classic-releases/{version}/{filename}',
                              sha256=matches[0]['sha256sum'], size=int(matches[0]['size'])))


def archive_root(archive):
    roots = {PurePosixPath(m.name).parts[0] for m in archive.getmembers() if m.name}
    if len(roots) != 1:
        raise ValueError('Expected one source archive root')
    return next(iter(roots)) + '/'


def source_entries(source, lock):
    """Map every preferred source file to its anchored content digest and mode."""
    entries = {}
    with tarfile.open(source) as archive:
        prefix = archive_root(archive)
        for member in archive:
            relative = member.name[len(prefix):]
            path = PurePosixPath(relative)
            if member.isdir():
                continue
            if not member.isfile() or path.is_absolute() or '..' in path.parts or not relative:
                raise ValueError(f'Unsupported source member: {member.name}')
            if relative in entries:
                raise ValueError('Duplicate source member')
            data = archive.extractfile(member).read()
            entry = dict(size=len(data), sha256=hashlib.sha256(data).hexdigest(),
                         mode=member.mode & 0o777, data=data)
            if data.startswith(b'version https://git-lfs.github.com/spec/v1\n'):
                match = re.fullmatch(rb'version https://git-lfs.github.com/spec/v1\noid sha256:([a-f0-9]{64})\nsize ([0-9]+)\n', data)
                if not match:
                    raise ValueError('Invalid LFS pointer')
                entry.update(sha256=match[1].decode(), size=int(match[2]), data=None)
            entries[relative] = entry
    date = datetime.fromisoformat(lock['commit_date'].replace('Z', '+00:00'))
    revision = f"{lock['upstream_version']}\t{date:%Y%m%d}\t0\t{lock['commit']}\n".encode()
    provenance = json.dumps({k: lock[k] for k in ['source', 'sha256', 'commit', 'commit_date', 'fonts']}, sort_keys=True, indent=2).encode() + b'\n'
    for name, data in [('.ottdrev', revision), ('packaging-source.json', provenance)]:
        if name in entries:
            raise ValueError(f'Upstream now supplies reserved export metadata: {name}')
        entries[name] = dict(size=len(data), sha256=hashlib.sha256(data).hexdigest(), mode=0o644, data=data)
    if sum(entry['size'] for entry in entries.values()) > 2 * 1024 ** 3:
        raise ValueError('Graphics source inventory exceeds reviewed 2 GiB limit')
    return entries


def valid_object(path, entry):
    if not path.is_file() or path.stat().st_size != entry['size']:
        return False
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest() == entry['sha256']


def fetch_lfs(entries, cache):
    cache.mkdir(parents=True, exist_ok=True)
    pending = {}
    for entry in entries.values():
        if entry['data'] is not None:
            continue
        path = cache / entry['sha256']
        if path.exists() and not valid_object(path, entry):
            raise ValueError(f'Corrupt cached LFS object: {path}')
        if not path.exists():
            pending[entry['sha256']] = entry
    objects = [{'oid': oid, 'size': entry['size']} for oid, entry in pending.items()]
    for start in range(0, len(objects), 100):
        batch = objects[start:start + 100]
        response = get_json(f'https://github.com/{GFX_REPO}.git/info/lfs/objects/batch',
            json.dumps({'operation': 'download', 'transfers': ['basic'], 'objects': batch}).encode(),
            {'Accept': 'application/vnd.git-lfs+json', 'Content-Type': 'application/vnd.git-lfs+json'})
        if {obj['oid'] for obj in response['objects']} != {obj['oid'] for obj in batch}:
            raise ValueError('LFS response did not cover the requested objects')
        def download(obj):
            entry = pending[obj['oid']]
            action = obj.get('actions', {}).get('download')
            if not action or obj['size'] != entry['size']:
                raise ValueError(f'LFS object unavailable: {obj["oid"]}')
            path = cache / obj['oid']
            with tempfile.NamedTemporaryFile(dir=cache, delete=False) as output:
                temporary = Path(output.name)
                try:
                    with request(action['href'], headers=action.get('header')) as source:
                        remaining = entry['size'] + 1
                        while remaining:
                            chunk = source.read(min(1024 * 1024, remaining))
                            if not chunk:
                                break
                            output.write(chunk)
                            remaining -= len(chunk)
                    output.close()
                    if not valid_object(temporary, entry):
                        raise ValueError('LFS object checksum mismatch')
                    temporary.replace(path)
                finally:
                    temporary.unlink(missing_ok=True)
        with ThreadPoolExecutor(max_workers=8) as pool:
            list(pool.map(download, response['objects']))


def verify_bundle(bundle, entries, prefix):
    seen = set()
    with tarfile.open(bundle, 'r|xz') as archive:
        for member in archive:
            if not member.name.startswith(prefix) or not member.isfile():
                raise ValueError('Invalid prepared source member')
            name = member.name[len(prefix):]
            entry = entries.get(name)
            if entry is None or name in seen or member.size != entry['size'] or member.mode != entry['mode']:
                raise ValueError(f'Prepared source inventory mismatch: {name}')
            if hashlib.file_digest(archive.extractfile(member), 'sha256').hexdigest() != entry['sha256']:
                raise ValueError(f'Prepared source checksum mismatch: {name}')
            seen.add(name)
    if seen != set(entries):
        raise ValueError('Incomplete prepared source bundle')


def prepare_graphics(source, lock, directory, cache):
    with (directory / '.prepare.lock').open('w') as guard:
        fcntl.flock(guard, fcntl.LOCK_EX)
        return _prepare_graphics(source, lock, directory, cache)


def _prepare_graphics(source, lock, directory, cache):
    entries = source_entries(source, lock)
    prefix = f'opengfx2_classic-{lock["upstream_version"]}-source/'
    bundle = directory / f'opengfx2_classic-{lock["upstream_version"]}-source.tar.xz'
    if bundle.exists():
        verify_bundle(bundle, entries, prefix)
        return bundle
    fetch_lfs(entries, cache)
    epoch = int(datetime.fromisoformat(lock['commit_date'].replace('Z', '+00:00')).timestamp())
    with tempfile.NamedTemporaryFile(dir=directory, prefix=bundle.name + '.', suffix='.partial', delete=False) as output:
        temporary = Path(output.name)
    try:
        with tarfile.open(temporary, 'w:xz', preset=6) as archive:
            for name, entry in sorted(entries.items()):
                member = tarfile.TarInfo(prefix + name)
                member.size, member.mode, member.mtime = entry['size'], entry['mode'], epoch
                if entry['data'] is not None:
                    archive.addfile(member, io.BytesIO(entry['data']))
                else:
                    with (cache / entry['sha256']).open('rb') as stream:
                        archive.addfile(member, stream)
        verify_bundle(temporary, entries, prefix)
        temporary.replace(bundle)
    finally:
        temporary.unlink(missing_ok=True)
    return bundle
