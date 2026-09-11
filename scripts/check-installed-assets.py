#!/usr/bin/env python3
"""Exercise OpenTTD's discovery of the sound/music sets provided by RPMs."""
import os
from pathlib import Path
import subprocess
import tempfile


def usable_sets(help_text, heading, next_heading):
    section = help_text.split(heading + '\n', 1)[1].split(next_heading, 1)[0]
    return {line.split(':', 1)[0].strip() for line in section.splitlines()
            if ':' in line and '(unusable:' not in line}


def main():
    with tempfile.TemporaryDirectory(prefix='openttd-assets-') as directory:
        env = dict(os.environ, XDG_DATA_HOME=directory + '/data',
                   XDG_CONFIG_HOME=directory + '/config', LANG='C.UTF-8')
        help_text = subprocess.check_output(['openttd', '-h'], cwd=directory, env=env, text=True)
    sounds = usable_sets(help_text, 'List of sounds sets:', 'List of music sets:')
    music = usable_sets(help_text, 'List of music sets:', 'List of music drivers:')
    print('Usable sound sets:', ', '.join(sorted(sounds)))
    print('Usable music sets:', ', '.join(sorted(music)))
    if 'OpenSFX' not in sounds or 'OpenMSX' not in music:
        raise SystemExit('FAIL: packaged OpenSFX/OpenMSX are missing or unusable')
    subprocess.run(['rpm', '-q', 'openttd-opensfx', 'openttd-openmsx'], check=True)
    for filename in ['opensfx/opensfx.obs', 'opensfx/opensfx.cat', 'openmsx/openmsx.obm']:
        assert (Path('/usr/share/openttd/baseset') / filename).is_file()
    print('PASS: installed engine discovers both packaged audio sets')


if __name__ == '__main__':
    main()
