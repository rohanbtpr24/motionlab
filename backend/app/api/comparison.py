import json
from typing import Literal
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field
from ..biomechanics.comparison import compare_results

router = APIRouter()

class SetupUpdate(BaseModel):
    label: str = Field(default='', max_length=80)
    seatpost_extension_change_mm: float | None = Field(default=None, allow_inf_nan=False)

@router.patch('/api/videos/{video_id}/setup')
def update_setup(video_id: str, body: SetupUpdate, request: Request):
    store = request.app.state.store
    metadata, _ = store.get(video_id)
    metadata = metadata.model_copy(update=body.model_dump())
    temporary = store.root / f'{video_id}.setup.tmp'
    temporary.write_text(metadata.model_dump_json(indent=2))
    temporary.replace(store.root / f'{video_id}.json')
    return metadata

@router.get('/api/comparisons')
def compare(baseline_analysis_id: str, candidate_analysis_id: str, request: Request, side: Literal['left','right'] = 'right'):
    service = request.app.state.analysis
    results, jobs = [], []
    for analysis_id in (baseline_analysis_id, candidate_analysis_id):
        job = service.get(analysis_id)
        if job['status'] != 'completed':
            raise HTTPException(409, 'Both tracking jobs must be completed before comparison.')
        results.append(json.loads((service.root / analysis_id / 'result.json').read_text()))
        jobs.append(job)
    comparison = compare_results(*results, side)
    comparison['baseline'] = dict(analysis_id=baseline_analysis_id, video=request.app.state.store.get(jobs[0]['video_id'])[0].model_dump(), start_seconds=results[0]['start_seconds'], duration_seconds=results[0]['duration_seconds'])
    comparison['candidate'] = dict(analysis_id=candidate_analysis_id, video=request.app.state.store.get(jobs[1]['video_id'])[0].model_dump(), start_seconds=results[1]['start_seconds'], duration_seconds=results[1]['duration_seconds'])
    return comparison
