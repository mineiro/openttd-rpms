import importlib.util
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import releases


def module(name, filename):
    spec = importlib.util.spec_from_file_location(name, releases.ROOT / 'scripts' / filename)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


baseset = module('baseset', 'check-baseset.py')
installed = module('installed', 'check-installed-assets.py')


class PackageRoutingTest(unittest.TestCase):
    def test_audio_tracks_its_own_stable_channel(self):
        index = {'latest': [
            {'folder': 'openttd-releases', 'name': 'testing', 'version': '17.0-beta1'},
            {'folder': 'opensfx-releases', 'name': 'stable', 'version': '1.0.3'},
            {'folder': 'opensfx-releases', 'name': 'testing', 'version': '2.0-beta1'},
            {'folder': 'openmsx-releases', 'name': 'stable', 'version': '0.4.2'}]}
        self.assertEqual(releases.latest_version(index, releases.PACKAGES['openttd-opensfx']), '1.0.3')
        self.assertEqual(releases.latest_version(index, releases.PACKAGES['openttd-openmsx']), '0.4.2')

    def test_prefixed_rpm_name_uses_upstream_source_identity(self):
        package = releases.PACKAGES['openttd-openmsx']
        manifest = {'version': '0.4.2', 'category': 'openmsx', 'dev_files': [
            {'id': 'openmsx-0.4.2-source.tar.xz', 'sha256sum': 'a' * 64, 'size': '100'}]}
        lock = releases.release_metadata('0.4.2', manifest, package)
        self.assertEqual(lock['source'], 'https://cdn.openttd.org/openmsx-releases/0.4.2/openmsx-0.4.2-source.tar.xz')
        with self.assertRaises(ValueError):
            releases.release_metadata('0.4.2', manifest, releases.PACKAGES['openttd-opensfx'])

    def test_audio_update_does_not_change_game_package(self):
        package = releases.PACKAGES['openttd-opensfx']
        old = releases.read_lock(package)
        new = dict(old, upstream_version='1.0.4', rpm_version='1.0.4')
        original_game = releases.DEFAULT.spec.read_bytes()
        spec_text = package.spec.read_text()
        with tempfile.TemporaryDirectory() as directory, patch.object(releases, 'ROOT', Path(directory)):
            package.directory.mkdir(parents=True)
            package.spec.write_text(spec_text)
            package.lock.write_text(json.dumps(old))
            with patch.object(releases, 'fetch_yaml'), patch.object(releases, 'latest_version', return_value='1.0.4'), patch.object(releases, 'release_metadata', return_value=new), patch.object(releases, 'fetch_source') as fetch, patch.object(releases, 'verify_bundles') as review:
                releases.update(package)
                fetch.assert_called_once_with(new, package)
                review.assert_called_once_with(fetch.return_value, '1.0.4', package)
            self.assertIn('Version:        1.0.4', package.spec.read_text())
            self.assertEqual(json.loads(package.lock.read_text()), new)
        self.assertEqual(releases.DEFAULT.spec.read_bytes(), original_game)

    def test_audio_license_drift_blocks_build(self):
        package = releases.PACKAGES['openttd-opensfx']
        with patch.object(releases, 'license_inventory', return_value={'docs/license.txt': 'changed'}):
            with self.assertRaisesRegex(ValueError, 'require review'):
                releases.verify_bundles(Path('unused'), '1.0.3', package)

    def test_cached_game_sources_cannot_satisfy_audio_lock(self):
        package = releases.PACKAGES['openttd-openmsx']
        with tempfile.TemporaryDirectory() as directory, patch.object(releases, 'ROOT', Path(directory)):
            package.directory.mkdir(parents=True)
            wrong = {'source': 'https://cdn.openttd.org/openttd-releases/0.4.2/openttd-0.4.2-source.tar.xz',
                     'upstream_version': '0.4.2', 'rpm_version': '0.4.2'}
            package.lock.write_text(json.dumps(wrong))
            with self.assertRaisesRegex(ValueError, 'identity'):
                releases.read_lock(package)


class AssetValidationTest(unittest.TestCase):
    def test_corrupt_payload_does_not_pass_descriptor_validation(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            midi = b'MThd' + bytes(10)
            (root / 'song.mid').write_bytes(midi)
            (root / 'set.obm').write_text('[metadata]\nname=OpenMSX\nversion=1\ndescription=OpenMSX 0.4.2\n[files]\ntheme=song.mid\n[md5s]\nsong.mid=' + hashlib.md5(midi, usedforsecurity=False).hexdigest() + '\n')
            baseset.validate(root / 'set.obm', 'OpenMSX', '0.4.2', 1)
            (root / 'song.mid').write_bytes(b'corrupted')
            with self.assertRaises(AssertionError):
                baseset.validate(root / 'set.obm', 'OpenMSX', '0.4.2', 1)

    def test_unusable_sets_do_not_count_as_installed(self):
        text = 'List of sounds sets:\n NoSound: silent\n OpenSFX: broken (unusable: 1 missing file)\nList of music sets:\n'
        self.assertNotIn('OpenSFX', installed.usable_sets(text, 'List of sounds sets:', 'List of music sets:'))
        text = text.replace('broken (unusable: 1 missing file)', 'complete')
        self.assertIn('OpenSFX', installed.usable_sets(text, 'List of sounds sets:', 'List of music sets:'))


if __name__ == '__main__':
    unittest.main()
