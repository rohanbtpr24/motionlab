"""Projected interior angles, in degrees. No clinical flexion convention implied."""
import math
import numpy as np

JOINTS = {"hip": (11, 23, 25), "knee": (23, 25, 27), "ankle": (25, 27, 31)}

def interior_angle(a, b, c):
    u, v = np.asarray(a, dtype=float) - b, np.asarray(c, dtype=float) - b
    denominator = np.linalg.norm(u) * np.linalg.norm(v)
    if not math.isfinite(denominator) or denominator < 1e-8:
        return None
    return float(np.degrees(np.arccos(np.clip(np.dot(u, v) / denominator, -1, 1))))

def joint_angles(landmarks, width, height, threshold=0.6):
    result = {}
    for side, offset in (("left", 0), ("right", 1)):
        for name, indices in JOINTS.items():
            points = [landmarks[i + offset] for i in indices]
            valid = all(p["visibility"] >= threshold and p["presence"] >= threshold and 0 <= p["x"] <= 1 and 0 <= p["y"] <= 1 for p in points)
            xy = [np.array([p["x"] * width, p["y"] * height]) for p in points]
            result[f"{side}_{name}"] = interior_angle(*xy) if valid else None
    return result
