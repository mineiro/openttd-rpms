#!/usr/bin/env python3
"""Validate built OpenTTD sound/music descriptors against the installed payload."""
import argparse
import configparser
import hashlib
from pathlib import Path
import shutil
import subprocess
import tempfile
import wave


def validate(descriptor, name, version, count, sample_source=None):
    descriptor = Path(descriptor)
    if sample_source is not None:
        sample_source = Path(sample_source).resolve()
    cfg = configparser.ConfigParser(interpolation=None)
    cfg.optionxform = str
    cfg.read(descriptor, encoding='utf-8')
    assert cfg['metadata']['name'] == name
    assert version in cfg['metadata']['description']
    assert int(cfg['metadata']['version']) > 0
    files = [value for value in cfg['files'].values() if value]
    assert len(files) == (1 if name == 'OpenSFX' else count)
    assert set(files) == set(cfg['md5s'])
    for filename in files:
        relative = Path(filename)
        assert not relative.is_absolute() and '..' not in relative.parts
        path = descriptor.parent / relative
        data = path.read_bytes()
        assert data and hashlib.md5(data, usedforsecurity=False).hexdigest() == cfg['md5s'][filename]
        if name == 'OpenMSX':
            assert data.startswith(b'MThd'), f'Invalid MIDI header: {filename}'
    if name == 'OpenSFX':
        with tempfile.TemporaryDirectory() as work:
            root = Path(work)
            (root / 'src/wav').mkdir(parents=True)
            shutil.copy2(descriptor.parent / files[0], root / 'sounds.cat')
            subprocess.run(['catcodec', '-d', 'sounds.cat'], cwd=root, check=True)
            samples = list(root.rglob('*.wav'))
            assert len(samples) == count
            for sample in samples:
                with wave.open(str(sample)) as wav:
                    assert wav.getnchannels() == 1
                    assert wav.getsampwidth() in (1, 2)
                    assert wav.getframerate() in (11025, 22050, 44100)
                    if sample_source is not None:
                        with wave.open(str(sample_source / sample.relative_to(root))) as original:
                            assert wav.getparams() == original.getparams()
                            assert wav.readframes(wav.getnframes()) == original.readframes(original.getnframes())
    print(f'{name} {version}: validated descriptor and {count} samples/tracks')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('descriptor', type=Path)
    parser.add_argument('name', choices=('OpenSFX', 'OpenMSX'))
    parser.add_argument('version')
    parser.add_argument('count', type=int)
    parser.add_argument('--sample-source', type=Path)
    args = parser.parse_args()
    validate(args.descriptor, args.name, args.version, args.count, args.sample_source)
