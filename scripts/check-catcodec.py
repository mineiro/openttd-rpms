#!/usr/bin/env python3
"""Round-trip a generated PCM sample through the real encoder and decoder."""
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import wave

binary = str(Path(sys.argv[1]).resolve())
frames = struct.pack('<' + 'h' * 512, *([0, 1000, -1000, 0] * 128))
with tempfile.TemporaryDirectory() as directory:
    root = Path(directory)
    with wave.open(str(root / 'tone.wav'), 'wb') as sample:
        sample.setparams((1, 2, 44100, 0, 'NONE', 'not compressed'))
        sample.writeframes(frames)
    (root / 'sample.sfo').write_text('"tone.wav" Test signal\n')
    subprocess.run([binary, '-e', 'sample.cat'], cwd=root, check=True)
    (root / 'tone.wav').unlink()
    subprocess.run([binary, '-d', 'sample.cat'], cwd=root, check=True)
    with wave.open(str(root / 'tone.wav')) as sample:
        assert sample.getnchannels() == 1 and sample.getsampwidth() == 2
        assert sample.getframerate() == 44100
        assert sample.readframes(sample.getnframes()) == frames
print('Catcodec: PCM round-trip passed')
