#!/usr/bin/env python3
"""Numerical regression checks without the PNG fixtures absent from the sdist."""
import numpy as np
from blend_modes import normal, multiply, overlay

bottom = np.array([[[100., 150., 200., 255.]]])
top = np.array([[[200., 100., 50., 255.]]])
np.testing.assert_allclose(normal(bottom, top, 0.0), bottom)
np.testing.assert_allclose(normal(bottom, top, 1.0), top)
result = multiply(bottom, top, 1.0)
np.testing.assert_allclose(result[..., :3], bottom[..., :3] * top[..., :3] / 255.)
assert np.isfinite(overlay(bottom, top, 0.5)).all()
print('Blend Modes: opacity endpoints, multiplication and overlay passed')
