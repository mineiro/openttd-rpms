import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import sys
import tarfile
import tempfile
import types
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import releases
import source_providers as providers

spec = importlib.util.spec_from_file_location('publisher', releases.ROOT / 'scripts/copr-build.py')
publisher = importlib.util.module_from_spec(spec)
spec.loader.exec_module(publisher)


class SourceBundleTest(unittest.TestCase):
    def fixture(self, root):
        payload = b'preferred editable artwork\n'
        digest = hashlib.sha256(payload).hexdigest()
        pointer = f'version https://git-lfs.github.com/spec/v1\noid sha256:{digest}\nsize {len(payload)}\n'.encode()
        source = root / 'source.tar.gz'
        with tarfile.open(source, 'w:gz') as archive:
            for name, data in [('repo/LICENSE', b'license'), ('repo/art.pdn', pointer)]:
                member = tarfile.TarInfo(name)
                member.size, member.mode = len(data), 0o644
                archive.addfile(member, io.BytesIO(data))
        cache = root / 'objects'
        cache.mkdir()
        (cache / digest).write_bytes(payload)
        lock = dict(upstream_version='0.8.1', commit_date='2025-12-15T21:00:34Z',
                    commit='a' * 40, source='https://example.org/source', sha256='b' * 64, fonts={})
        return source, cache, lock, payload, digest

    def test_materializes_and_revalidates_cached_preferred_sources(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source, cache, lock, payload, digest = self.fixture(root)
            with patch.object(providers, 'get_json') as network:
                bundle = providers.prepare_graphics(source, lock, root, cache)
                self.assertEqual(providers.prepare_graphics(source, lock, root, cache), bundle)
                network.assert_not_called()
            with tarfile.open(bundle) as archive:
                self.assertEqual(archive.extractfile('opengfx2_classic-0.8.1-source/art.pdn').read(), payload)
                self.assertIn(b'20251215', archive.extractfile('opengfx2_classic-0.8.1-source/.ottdrev').read())
            entries = providers.source_entries(source, lock)
            entries['art.pdn']['sha256'] = '0' * 64
            with self.assertRaisesRegex(ValueError, 'checksum mismatch'):
                providers.verify_bundle(bundle, entries, 'opengfx2_classic-0.8.1-source/')

    def test_corrupt_lfs_cache_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source, cache, lock, payload, digest = self.fixture(root)
            (cache / digest).write_bytes(b'bad')
            with self.assertRaisesRegex(ValueError, 'Corrupt cached LFS'):
                providers.prepare_graphics(source, lock, root, cache)

    def test_truncated_prepared_bundle_cannot_be_reused(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source, cache, lock, payload, digest = self.fixture(root)
            bundle = providers.prepare_graphics(source, lock, root, cache)
            bundle.write_bytes(bundle.read_bytes()[:40])
            with self.assertRaises((tarfile.ReadError, EOFError)):
                providers.prepare_graphics(source, lock, root, cache)

    def test_lfs_batch_must_cover_all_objects(self):
        entries = {'image.png': dict(data=None, sha256='c' * 64, size=10)}
        with tempfile.TemporaryDirectory() as directory, patch.object(providers, 'get_json', return_value={'objects': []}):
            with self.assertRaisesRegex(ValueError, 'did not cover'):
                providers.fetch_lfs(entries, Path(directory))

    def test_insecure_transport_is_rejected(self):
        with self.assertRaisesRegex(ValueError, 'HTTPS'):
            providers.request('http://example.org/source')

    def test_graphics_does_not_follow_other_release_channels(self):
        index = {'latest': [
            dict(folder='opengfx-releases', name='stable', version='8.0'),
            dict(folder='opengfx2_classic-releases', name='stable', version='0.8.1'),
            dict(folder='opengfx2_classic-nightlies', name='main', version='20260101-gabcdef')
        ]}
        self.assertEqual(releases.latest_version(index, releases.PACKAGES['openttd-opengfx2-classic']), '0.8.1')


class Record(dict):
    __getattr__ = dict.__getitem__


class LazyPublisherTest(unittest.TestCase):
    def test_successful_targets_skip_srpm_generation_and_upload(self):
        client = Mock()
        client.project_proxy.get.return_value = Record(chroot_repos={'fedora-44-x86_64': 'repo'})
        client.build_proxy.get_list.return_value = [Record(id=123, source_package={'version': '0.8.1-1'}, state='succeeded')]
        client.build_chroot_proxy.get_list.return_value = [{'name': 'fedora-44-x86_64', 'state': 'succeeded'}]
        module = types.ModuleType('copr.v3')
        module.Client = Mock()
        module.Client.create_from_config_file.return_value = client
        with patch.dict(sys.modules, {'copr.v3': module}), patch.object(sys, 'argv', ['publisher', '--package', 'openttd-opengfx2-classic']), patch.object(releases, 'read_lock'), patch.object(releases, 'srpm') as build, patch.object(publisher.subprocess, 'check_output', return_value='openttd-opengfx2-classic 0.8.1-1'):
            publisher.main()
        build.assert_not_called()
        client.build_proxy.create_from_file.assert_not_called()


if __name__ == '__main__':
    unittest.main()
