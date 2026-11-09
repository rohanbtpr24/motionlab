"""Descriptive comparisons between independent side-view clips, not fit advice."""
import math
import numpy as np
from fastapi import HTTPException


def summarize(values, total):
    clean = [float(v) for v in values if isinstance(v, (float, int)) and not isinstance(v, bool) and math.isfinite(v) and 0 <= v <= 180]
    if not clean:
        return None
    return dict(valid_samples=len(clean), total_samples=total, coverage=len(clean)/total,
                minimum=float(np.min(clean)), p05=float(np.percentile(clean, 5)),
                median=float(np.median(clean)), p95=float(np.percentile(clean, 95)), maximum=float(np.max(clean)))


def compare_results(baseline, candidate, side):
    if side not in {'left', 'right'}:
        raise HTTPException(422, 'Choose anatomical left or right.')
    if baseline['video_id'] == candidate['video_id']:
        raise HTTPException(422, 'Choose two different recordings.')
    if baseline['view'] != 'side' or candidate['view'] != 'side':
        raise HTTPException(422, 'Hip/knee/ankle comparisons currently require two side-view recordings.')
    for field in ('method', 'angle_convention', 'tracking_version', 'model_sha256', 'confidence_threshold'):
        if baseline.get(field) is not None and candidate.get(field) is not None and baseline[field] != candidate[field]:
            raise HTTPException(422, f'Analysis {field} differs. Re-run both clips with the same tracking method.')
    metrics = {}
    for joint in ('hip', 'knee', 'ankle'):
        key = f'{side}_{joint}'
        a = summarize([f.get('angles', {}).get(key) for f in baseline['frames']], len(baseline['frames']))
        b = summarize([f.get('angles', {}).get(key) for f in candidate['frames']], len(candidate['frames']))
        delta = {stat: b[stat]-a[stat] for stat in ('minimum','p05','median','p95','maximum')} if a and b else None
        metrics[joint] = dict(baseline=a, candidate=b, delta=delta)
    if not any(m['delta'] is not None for m in metrics.values()):
        raise HTTPException(422, 'No valid joint angles on this anatomical side in both clips. Choose the visible side or re-run tracking.')
    warnings = [
        'Independent sessions: samples are not synchronized or aligned to crank phase.',
        'Observed clip summaries are not cycle-specific extrema or fit recommendations.',
        'Differences can reflect camera position, tracking error, cadence, workload, posture, and the setup change. Keep these conditions consistent.',
        'Measurement error and repeatability have not been quantified; a difference is not proof that the setup caused it.'
    ]
    if not baseline.get('model_sha256') or not candidate.get('model_sha256'):
        warnings.append('Legacy analysis lacks model provenance. Re-run both clips for fully versioned results.')
    return dict(side=side, units='degrees', convention='2D interior angle; 180 degrees is straight',
                delta_direction='candidate minus baseline', synchronized=False, recommendations=None,
                metrics=metrics, warnings=warnings)
