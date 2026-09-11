#!/usr/bin/env python3
"""Validate the Classic descriptor, GRF identities, and GRF-format MD5 hashes."""
import configparser
from pathlib import Path
import subprocess
import sys

root = Path(sys.argv[1])
version = sys.argv[2]
config = configparser.ConfigParser(interpolation=None)
config.optionxform = str
config.read(root / 'opengfx2_8.obg', encoding='utf-8')
assert config['metadata']['name'] == 'OpenGFX2 Classic'
assert version in config['metadata']['description']
assert config['metadata']['blitter'] == '8bpp'
assert int(config['metadata']['version']) > 0
files = set(config['files'].values())
assert len(files) == 6 and files == set(config['md5s'])
for filename in files:
    assert Path(filename).name == filename and filename.endswith('_8.grf')
    path = root / filename
    assert path.is_file() and path.stat().st_size > 16
    # NewGRF v2 hashes the data section, not the entire file; use the format tool.
    actual = subprocess.check_output(['grfid', '-m', str(path)], text=True).strip()
    assert actual == config['md5s'][filename], f'Invalid GRF checksum: {filename}'
assert set(p.name for p in root.glob('*.grf')) == files
print(f'OpenGFX2 Classic {version}: all six GRFs match their descriptor')
