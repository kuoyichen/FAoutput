"""Cross-sections of the voxel solid and half rings for lofting (symmetric about x=0)."""
import numpy as np
from scipy import ndimage
from skimage import measure


def resample(path, n):
    d = np.r_[0, np.cumsum(np.linalg.norm(np.diff(path, axis=0), axis=1))]
    t = np.linspace(0, d[-1], n + 1)
    return np.c_[np.interp(t, d, path[:, 0]), np.interp(t, d, path[:, 1])]


class Sections:
    def __init__(s, solid, lo, vox): s.S, s.lo, s.vx = solid, lo, vox

    def section(s, y, close=3):
        """outer contour (x, z) of the solid at station y; small gaps and notches closed"""
        sl = ndimage.binary_fill_holes(s.S[:, int(round((y - s.lo[1]) / s.vx)), :])
        st = ndimage.generate_binary_structure(2, 1)
        sl = ndimage.binary_closing(np.pad(sl, close+1), structure=st, iterations=close)[close+1:-close-1, close+1:-close-1]
        sl = ndimage.binary_fill_holes(sl)
        c = max(measure.find_contours(np.pad(sl.astype(float), 1), 0.5), key=len)
        return (c - 1) * s.vx + s.lo[[0, 2]]

    def half_ring(s, y, up=4, mid=2, inn=3):
        """right half from top centre to bottom centre; locked at the widest point and the lowest point.
        up/mid/inn = segments: top->widest, widest->lowest, lowest->bottom centre."""
        P = s.section(y); n = len(P); xs, zs = P[:, 0], P[:, 1]
        near = np.abs(xs) <= s.vx * 1.01
        it = np.where(near)[0][np.argmax(zs[near])]; ib = np.where(near)[0][np.argmin(zs[near])]
        P = np.roll(P, -it, axis=0); ib = (ib - it) % n
        if P[min(5, n-1), 0] < 0: P = np.roll(P[::-1], 1, axis=0); ib = (n - ib) % n
        half = P[:ib+1]; im = np.argmax(half[:, 0])
        il = im + np.argmin(half[im:, 1])
        if il == len(half) - 1 or il == im: il = (im + len(half) - 1) // 2
        R = np.vstack([resample(half[:im+1], up), resample(half[im:il+1], mid)[1:], resample(half[il:], inn)[1:]])
        R[0, 0] = 0; R[-1, 0] = 0
        return R
