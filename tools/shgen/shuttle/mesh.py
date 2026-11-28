"""Minimal mesh container (same as tools/shgen/glb2sh/geom.Mesh, without its skimage-dependent imports)."""
class Mesh:
    """V: float points; F: (vertex ids, colour, smooth, normal hint)"""
    def __init__(s): s.V = []; s.F = []
    def add(s, p): s.V.append(tuple(float(x) for x in p)); return len(s.V) - 1
