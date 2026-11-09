import copy
import pytest
from fastapi import HTTPException
from app.biomechanics.comparison import compare_results, summarize


def result(video_id, values, view='side'):
    return dict(video_id=video_id,view=view,method='test',frames=[{'angles': {'right_knee':v,'right_hip':v,'right_ankle':None}} for v in values])


def test_comparison_delta_coverage_and_missing_metrics():
    comparison=compare_results(result('a',[100,110,None,120]),result('b',[105,115,125,135]),'right')
    knee=comparison['metrics']['knee']
    assert knee['baseline']['median'] == 110
    assert knee['candidate']['median'] == 120
    assert knee['delta']['median'] == 10
    assert knee['baseline']['coverage'] == .75
    assert knee['baseline']['p05'] == pytest.approx(101)
    assert comparison['metrics']['ankle']['delta'] is None
    assert comparison['synchronized'] is False
    assert comparison['recommendations'] is None


def test_summary_does_not_treat_missing_or_nonfinite_as_zero():
    assert summarize([None,float('nan'),float('inf'),-1,181,True],6) is None
    assert summarize([0,180,None],3)['median']==90


@pytest.mark.parametrize('change', ['same_video','front','wrong_side','method','model','angle'])
def test_rejects_incompatible_comparisons(change):
    a,b=result('a',[120]),result('b',[130])
    side='right'
    if change=='same_video': b['video_id']='a'
    if change=='front': b['view']='front'
    if change=='wrong_side': side='left'
    if change=='method': b['method']='different'
    if change=='model': a['model_sha256']='first'; b['model_sha256']='second'
    if change=='angle': a['angle_convention']='interior';b['angle_convention']='flexion'
    with pytest.raises(HTTPException): compare_results(a,b,side)
