#!/usr/bin/env python3
"""Reject package changes which cannot be delivered as a new RPM update."""
import json
import os
import subprocess
import tempfile
from pathlib import Path
import rpm


def git(*args):
    return subprocess.check_output(['git', *args], text=True).strip()


def main():
    event_path = os.environ.get('GITHUB_EVENT_PATH')
    if not event_path:
        print('NVR guard: no GitHub event; skipped')
        return
    event = json.loads(Path(event_path).read_text())
    base = (event.get('pull_request') or {}).get('base', {}).get('sha') or event.get('before')
    if not base or set(base) == {'0'}:
        print('NVR guard: initial push or manual run')
        return
    def evr(spec):
        with tempfile.NamedTemporaryFile(mode='w', suffix='.spec') as temp:
            temp.write(spec)
            temp.flush()
            return tuple(subprocess.check_output(['rpmspec', '-q', '--srpm', '--qf', '%{EPOCHNUM} %{VERSION} %{RELEASE}', temp.name], text=True).split())
    from releases import PACKAGES
    changed = set(git('diff', '--name-only', base, 'HEAD').splitlines())
    for package in PACKAGES.values():
        directory = f'packages/{package.name}'
        if not any(path.startswith(directory + '/') or path in package.extra_sources for path in changed):
            continue
        path = f'{directory}/{package.name}.spec'
        previous = subprocess.run(['git', 'show', f'{base}:{path}'], capture_output=True, text=True)
        if previous.returncode:
            print(f'NVR guard: new package {package.name}')
            continue
        if rpm.labelCompare(evr(Path(path).read_text()), evr(previous.stdout)) <= 0:
            raise SystemExit(f'{package.name} changed without a newer Version/Release; bump Release')
        print(f'NVR guard: {package.name} upgrade ordering verified')



if __name__ == '__main__':
    main()
