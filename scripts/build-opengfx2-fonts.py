#!/usr/bin/env python3
"""Run pinned upstream font builders and retain font-specific copyright notices."""
from pathlib import Path
import subprocess
import sys
import fontforge

root = Path(sys.argv[1]).resolve()
licenses, copyrights = set(), set()
for family, filename in [('sans', 'OpenTTD-Sans'), ('serif', 'OpenTTD-Serif'),
                         ('small', 'OpenTTD-Small'), ('mono', 'OpenTTD-Mono')]:
    folder = root / f'openttd-{family}'
    font = fontforge.open(str(folder / f'{filename}.sfd'))
    copyrights.add(font.copyright)
    for language, field, text in font.sfnt_names:
        if field == 'License':
            licenses.add(text)
    font.close()
    subprocess.run(['fontforge', '-lang=py', '-script', 'build_font.py', f'{filename}.sfd'],
                   cwd=folder, check=True)
if len(licenses) != 1 or 'SIL OPEN FONT LICENSE' not in next(iter(licenses)).upper():
    raise RuntimeError('Font licensing changed; review required')
Path('font-license.txt').write_text('OpenTTD fonts rasterized into OpenGFX2 Classic\n\n'
    + '\n'.join(sorted(copyrights)) + '\n\n' + next(iter(licenses)) + '\n')
