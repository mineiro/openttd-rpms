import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import releases
spec = importlib.util.spec_from_file_location('copr_build', Path(releases.ROOT) / 'scripts/copr-build.py')
copr_build = importlib.util.module_from_spec(spec)
spec.loader.exec_module(copr_build)


class ReleasesTest(unittest.TestCase):
    def test_rpm_upgrade_order(self):
        versions = ['15.3', '16.0-beta1', '16.0-beta2', '16.0-beta10', '16.0-RC1', '16.0-RC2', '16.0', '16.1', '17.0-beta1']
        for a, b in zip(versions, versions[1:]):
            self.assertLess(releases.compare(a, b), 0, (a, b))

    def test_ignore_nightlies_and_choose_stable_over_stale_testing(self):
        index = {'latest': [
            {'folder': 'openttd-releases', 'name': 'testing', 'version': '16.0-RC2'},
            {'folder': 'openttd-releases', 'name': 'stable', 'version': '16.0'},
            {'folder': 'openttd-nightlies/2026', 'name': 'master', 'version': '20260911-master'}]}
        self.assertEqual(releases.latest_version(index), '16.0')
        index['latest'][0]['version'] = '17.0-beta1'
        self.assertEqual(releases.latest_version(index), '17.0-beta1')

    def test_reject_unexpected_versions(self):
        for value in ['../16.0', '16.0\n', '$(echo evil)', '16.0-alpha1', '16.0-beta0']:
            with self.assertRaises(ValueError):
                releases.rpm_version(value)

    def test_missing_release_is_failure(self):
        with self.assertRaises(ValueError):
            releases.latest_version({'latest': []})

    def test_source_identity_and_hash_validation(self):
        manifest = {'version': '16.0', 'category': 'openttd', 'dev_files': [
            {'id': 'openttd-16.0-source.tar.xz', 'sha256sum': 'a' * 64, 'size': 8}]}
        result = releases.release_metadata('16.0', manifest)
        self.assertEqual(result['rpm_version'], '16.0')
        manifest['dev_files'].append(manifest['dev_files'][0])
        with self.assertRaises(ValueError):
            releases.release_metadata('16.0', manifest)

    def test_cached_tampering_fails(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'source'
            path.write_bytes(b'tampered')
            with self.assertRaises(ValueError):
                releases.verify_file(path, {'size': 8, 'sha256': 'a' * 64})

    def test_update_rejects_replaced_release(self):
        old = releases.read_lock()
        new = dict(old, sha256='a' * 64)
        with patch.object(releases, 'fetch_yaml'), patch.object(releases, 'latest_version', return_value=old['upstream_version']), patch.object(releases, 'release_metadata', return_value=new):
            with self.assertRaisesRegex(ValueError, 'metadata changed'):
                releases.update()

    def test_update_never_downgrades(self):
        with patch.object(releases, 'fetch_yaml'), patch.object(releases, 'latest_version', return_value='1.0'):
            with self.assertRaisesRegex(ValueError, 'downgrade'):
                releases.update()

    def test_verified_update_changes_spec_and_lock_together(self):
        old = releases.read_lock()
        new = dict(old, upstream_version='17.0-RC1', rpm_version='17.0~rc1')
        with tempfile.TemporaryDirectory() as directory:
            lock = Path(directory) / 'release.json'
            spec = Path(directory) / 'openttd.spec'
            lock.write_text(json.dumps(old))
            spec.write_text(releases.SPEC.read_text().replace('Release:        1', 'Release:        4'))
            with patch.object(releases, 'LOCK', lock), patch.object(releases, 'SPEC', spec), patch.object(releases, 'fetch_yaml'), patch.object(releases, 'latest_version', return_value='17.0-RC1'), patch.object(releases, 'release_metadata', return_value=new), patch.object(releases, 'fetch_source') as fetch, patch.object(releases, 'verify_bundles') as verify:
                releases.update()
                fetch.assert_called_once_with(new)
                verify.assert_called_once()
                self.assertEqual(json.loads(lock.read_text()), new)
                self.assertIn('Version:        17.0~rc1', spec.read_text())
                self.assertIn('Release:        1%{?dist}', spec.read_text())
                self.assertIn('%global upstream_version 17.0-RC1', spec.read_text())

    def test_bundle_failure_does_not_mutate_package(self):
        old = releases.read_lock()
        original = releases.SPEC.read_text()
        with patch.object(releases, 'fetch_yaml'), patch.object(releases, 'latest_version', return_value='17.0'), patch.object(releases, 'release_metadata', return_value=dict(old, upstream_version='17.0')), patch.object(releases, 'fetch_source'), patch.object(releases, 'verify_bundles', side_effect=ValueError('review required')):
            with self.assertRaisesRegex(ValueError, 'review required'):
                releases.update()
        self.assertEqual(releases.SPEC.read_text(), original)
        self.assertEqual(releases.read_lock(), old)

    def test_bundle_change_requires_review(self):
        with patch.object(releases, 'bundle_inventory', return_value={'new-library/LICENSE': 'changed'}):
            with self.assertRaisesRegex(ValueError, 'require review'):
                releases.verify_bundles(Path('unused'), '16.0')


class CoprTest(unittest.TestCase):
    def build(self, ident, version, **states):
        return ({'id': ident, 'source_package': {'version': version}},
                [{'name': name, 'state': state} for name, state in states.items()])

    def test_retry_failed_and_new_targets_only(self):
        builds = [self.build(1, '16.0-1', f44='succeeded', f43='failed')]
        missing, active = copr_build.remaining_chroots(builds, '16.0-1', {'f44', 'f43', 'f45'})
        self.assertEqual(missing, {'f43', 'f45'})
        self.assertEqual(active, set())

    def test_resume_pending_and_ignore_other_nvr(self):
        builds = [self.build(1, '15.3-1', f44='succeeded'), self.build(2, '16.0-1', f44='running')]
        self.assertEqual(copr_build.remaining_chroots(builds, '16.0-1', {'f44'}), ({'f44'}, {2}))

    def test_successful_retry_wins(self):
        builds = [self.build(1, '16.0-1', f44='failed'), self.build(2, '16.0-1', f44='succeeded')]
        self.assertEqual(copr_build.remaining_chroots(builds, '16.0-1', {'f44'}), (set(), set()))


if __name__ == '__main__':
    unittest.main()
