import json
import subprocess

import pytest
from fastapi.testclient import TestClient
from app.config import Settings
from app.main import create_app

@pytest.fixture
def client(tmp_path):
    return TestClient(create_app(Settings(data_dir=tmp_path / 'data', max_bytes=1024 * 1024, max_duration=2)))

@pytest.fixture(scope='session')
def videos(tmp_path_factory):
    root = tmp_path_factory.mktemp('fixtures')
    result = {}
    for ext, codec, duration in [('mp4', 'libx264', 1), ('mov', 'libx264', 1), ('avi', 'libx264', 1), ('mp4', 'mpeg4', 1), ('mp4', 'libx264', 3)]:
        path = root / f'{codec}-{duration}.{ext}'
        subprocess.run(['ffmpeg', '-v', 'error', '-f', 'lavfi', '-i', f'color=c=blue:s=160x120:r=24:d={duration}', '-c:v', codec, '-pix_fmt', 'yuv420p', str(path)], check=True)
        result[(ext, codec, duration)] = path.read_bytes()
    return result

def post(client, content, filename='clip.mp4', view='side'):
    return client.post('/api/videos', data={'view': view}, files={'file': (filename, content, 'video/mp4')})

def test_health(client):
    assert client.get('/health').json() == {'status': 'ok'}

@pytest.mark.parametrize('ext,view', [('mp4', 'side'), ('mov', 'front'), ('mp4', 'rear')])
def test_valid_upload(client, videos, ext, view):
    payload = videos[(ext, 'libx264', 1)]
    response = post(client, payload, f'../../unsafe.{ext}', view)
    assert response.status_code == 201, response.text
    data = response.json()
    assert len(data['video_id']) == 32
    assert (data['width'], data['height'], data['view']) == (160, 120, view)
    assert data['duration_seconds'] == pytest.approx(1)
    assert data['frame_rate'] == 24
    assert data['size_bytes'] == len(payload)
    assert data['time_base'] and data['duration_ts'] and data['average_frame_rate'] == '24/1'
    assert data['uploaded_at'].endswith('+00:00')
    partial = client.get(data['content_url'], headers={'Range': 'bytes=0-31'})
    assert partial.status_code == 206
    assert partial.content == payload[:32]
    assert client.get(data['content_url']).content == payload
    assert client.get(f"/api/videos/{data['video_id']}").json() == data
    root = client.app.state.store.root
    assert {p.name for p in root.iterdir()} == {data['video_id'] + '.' + ext, data['video_id'] + '.json'}
    # Metadata remains usable after restarting the application.
    restarted = TestClient(create_app(client.app.state.store.settings))
    assert restarted.get(data['content_url']).content == payload

@pytest.mark.parametrize('content,filename,status', [(b'', 'x.mp4', 422), (b'not video', 'x.mov', 422), (b'fake', 'x.txt', 415)])
def test_invalid_upload(client, content, filename, status):
    assert post(client, content, filename).status_code == status
    assert list(client.app.state.store.root.iterdir()) == []

def test_codec_and_duration(client, videos):
    assert post(client, videos[('mp4', 'mpeg4', 1)]).status_code == 415
    assert post(client, videos[('mp4', 'libx264', 3)]).status_code == 422
    assert list(client.app.state.store.root.iterdir()) == []

def test_invalid_view(client, videos):
    assert post(client, videos[('mp4', 'libx264', 1)], view='diagonal').status_code == 422

def test_file_size_and_cleanup(client):
    assert post(client, b'x' * (1024 * 1024 + 1)).status_code == 413
    assert list(client.app.state.store.root.iterdir()) == []

def test_request_size_limit(client):
    assert post(client, b'x' * (2 * 1024 * 1024)).status_code == 413
    assert list(client.app.state.store.root.iterdir()) == []

def test_missing_video(client):
    assert client.get('/api/videos/' + 'a' * 32 + '/content').status_code == 404
    assert client.get('/api/videos/not-an-id').status_code == 404

def test_missing_tools(client, videos, monkeypatch):
    def missing(*args, **kwargs):
        raise FileNotFoundError()
    monkeypatch.setattr(subprocess, 'run', missing)
    assert post(client, videos[('mp4', 'libx264', 1)]).status_code == 503
    assert list(client.app.state.store.root.iterdir()) == []


def test_spoofed_container_and_truncated_video(client, videos):
    assert post(client, videos[('avi', 'libx264', 1)], 'disguised.mp4').status_code == 415
    payload = videos[('mp4', 'libx264', 1)]
    assert post(client, payload[:len(payload) // 2]).status_code == 422
    assert list(client.app.state.store.root.iterdir()) == []

def test_validation_timeout(client, videos, monkeypatch):
    def timeout(*args, **kwargs):
        raise subprocess.TimeoutExpired('ffprobe', 30)
    monkeypatch.setattr(subprocess, 'run', timeout)
    assert post(client, videos[('mp4', 'libx264', 1)]).status_code == 422
    assert list(client.app.state.store.root.iterdir()) == []

@pytest.mark.parametrize('codec,pixel_format', [('libx265', 'yuv420p'), ('libx265', 'yuv420p10le'), ('libx264', 'yuv420p10le')])
def test_phone_codecs_preserve_original_and_create_preview(client, tmp_path, codec, pixel_format):
    path = tmp_path / 'phone.mov'
    command = ['ffmpeg', '-v', 'error', '-f', 'lavfi', '-i', 'color=c=blue:s=160x120:r=24:d=1', '-c:v', codec, '-pix_fmt', pixel_format]
    if codec == 'libx265':
        command += ['-x265-params', 'pools=1:frame-threads=1:log-level=error', '-tag:v', 'hvc1']
    subprocess.run(command + [str(path)], check=True, capture_output=True)
    payload = path.read_bytes()
    response = post(client, payload, 'phone.mov')
    assert response.status_code == 201, response.text
    data = response.json()
    assert data['codec'] == ('hevc' if codec == 'libx265' else 'h264')
    assert data['pixel_format'] == pixel_format
    assert data['size_bytes'] == len(payload)
    assert client.get(data['content_url']).content == payload
    assert data['preview_url']
    preview = client.get(data['preview_url'])
    assert preview.status_code == 200
    derivative = tmp_path / 'preview.mp4'
    derivative.write_bytes(preview.content)
    probe = json.loads(subprocess.run(['ffprobe', '-v', 'error', '-show_streams', '-of', 'json', str(derivative)], capture_output=True, text=True, check=True).stdout)['streams'][0]
    assert probe['codec_name'] == 'h264'
    assert probe['pix_fmt'] == 'yuv420p'
    assert (probe['width'], probe['height']) == (160, 120)
    assert float(probe['duration']) == pytest.approx(data['duration_seconds'])
    assert probe['avg_frame_rate'] == data['average_frame_rate']
    assert client.get(data['preview_url'], headers={'Range': 'bytes=0-31'}).status_code == 206
    restarted = TestClient(create_app(client.app.state.store.settings))
    assert restarted.get(data['preview_url']).content == preview.content


def test_failed_conversion_removes_partial_files(client, videos, monkeypatch):
    from app.ingestion import service
    original_run = service.run_media
    def fail_conversion(args, timeout):
        if args[0] == 'ffprobe':
            probe = json.loads(original_run(args, timeout))
            probe['streams'][0]['pix_fmt'] = 'yuv420p10le'
            return json.dumps(probe)
        if 'libx264' in args:
            from pathlib import Path
            from fastapi import HTTPException
            Path(args[-1]).write_bytes(b'partial output')
            raise HTTPException(422, 'Conversion timed out')
        return original_run(args, timeout)
    monkeypatch.setattr(service, 'run_media', fail_conversion)
    assert post(client, videos[('mp4', 'libx264', 1)]).status_code == 422
    assert list(client.app.state.store.root.iterdir()) == []


def test_variable_frame_rate_preview_preserves_close_timestamps(client, tmp_path):
    source = tmp_path / 'variable.mov'
    # The second frame falls only 10ms after the first. Rounding to a nominal
    # 24fps time base collapses these distinct timestamps and breaks MP4 muxing.
    subprocess.run([
        'ffmpeg', '-v', 'error', '-f', 'lavfi', '-i', 'color=c=blue:s=160x120:r=24:d=1',
        '-vf', 'settb=1/600,setpts=if(eq(N\\,1)\\,6\\,N*25)',
        '-c:v', 'libx264', '-pix_fmt', 'yuv420p10le',
        '-fps_mode', 'passthrough', '-enc_time_base:v', '1:600', str(source)
    ], capture_output=True, check=True)
    response = post(client, source.read_bytes(), 'variable.mov')
    assert response.status_code == 201, response.text
    preview = tmp_path / 'variable-preview.mp4'
    preview.write_bytes(client.get(response.json()['preview_url']).content)
    def frame_times(path):
        result = subprocess.run([
            'ffprobe', '-v', 'error', '-select_streams', 'v:0', '-show_frames',
            '-show_entries', 'frame=best_effort_timestamp_time', '-of', 'json', str(path)
        ], capture_output=True, text=True, check=True)
        return [float(frame['best_effort_timestamp_time']) for frame in json.loads(result.stdout)['frames']]
    original_times, preview_times = frame_times(source), frame_times(preview)
    assert len(original_times) == 24
    assert original_times[1] - original_times[0] == pytest.approx(0.01)
    assert preview_times == pytest.approx(original_times, abs=0.00001)


def wait_for_analysis(client, job):
    import time
    for _ in range(500):
        current = client.get('/api/analyses/' + job['analysis_id']).json()
        if current['status'] in {'completed', 'failed'}:
            return current
        time.sleep(.01)
    pytest.fail('Background analysis did not finish')


def test_analysis_job_results_and_restart(client, videos, tmp_path):
    timestamps = []
    class Tracker:
        def __init__(self, path): pass
        def detect(self, image, timestamp):
            timestamps.append(timestamp)
            if len(timestamps) % 2 == 0:
                return None
            return [dict(x=.2 + i*.01, y=.5, visibility=.9, presence=.9) for i in range(33)]
        def close(self): pass
    model = tmp_path / 'model.task'
    model.write_bytes(b'test-double')
    service = client.app.state.analysis
    service.model_path, service.tracker_factory = model, Tracker
    video = post(client, videos[('mp4','libx264',1)]).json()
    assert client.get('/api/videos').json()[0]['video_id'] == video['video_id']
    assert client.get(f"/api/videos/{video['video_id']}/analyses/latest").json() is None
    response = client.post(f"/api/videos/{video['video_id']}/analyses", json={'start_seconds': 0, 'duration_seconds': 1})
    assert response.status_code == 202
    completed = wait_for_analysis(client, response.json())
    assert completed['status'] == 'completed', completed
    result = client.get(completed['result_url']).json()
    assert result['total_frames'] == 15
    assert result['detected_frames'] == 8
    assert result['synchronized'] is False
    assert result['marker_tracking'] is False
    assert len(result['frames'][0]['landmarks']) == 33
    assert result['frames'][1]['angles']['left_knee'] is None
    assert timestamps == sorted(set(timestamps))
    assert timestamps[0] == 0
    assert result['frames'][14]['time_seconds'] == pytest.approx(14/15)
    restarted = TestClient(create_app(client.app.state.store.settings))
    assert restarted.get(completed['result_url']).json() == result
    assert restarted.get(f"/api/videos/{video['video_id']}/analyses/latest").json()['status'] == 'completed'


def test_analysis_validation_and_missing_model(client, videos, tmp_path):
    video = post(client, videos[('mp4','libx264',1)]).json()
    url = f"/api/videos/{video['video_id']}/analyses"
    for body in ({'duration_seconds':31}, {'start_seconds':-1}, {'start_seconds':2}):
        assert client.post(url, json=body).status_code == 422
    client.app.state.analysis.model_path = tmp_path / 'missing.task'
    assert client.post(url, json={}).status_code == 503
    assert client.get('/api/analyses/bad-id').status_code == 404


def test_analysis_failure_is_reported_and_queue_released(client, videos, tmp_path):
    class BrokenTracker:
        def __init__(self, path): raise RuntimeError('Test detector unavailable')
    model = tmp_path/'model.task'
    model.write_bytes(b'fake')
    service = client.app.state.analysis
    service.model_path, service.tracker_factory = model, BrokenTracker
    video = post(client, videos[('mp4','libx264',1)]).json()
    url = f"/api/videos/{video['video_id']}/analyses"
    job = client.post(url,json={'duration_seconds':1}).json()
    failed = wait_for_analysis(client,job)
    assert failed['status'] == 'failed'
    assert 'Test detector unavailable' in failed['error']
    assert client.get(f"/api/analyses/{job['analysis_id']}/result").status_code == 409
    service.executor.shutdown(wait=True)
    assert not service.active
    assert not list(service.root.glob('frames-*'))


def test_analysis_conflict_and_interrupted_jobs(client, videos, tmp_path):
    service = client.app.state.analysis
    service.model_path = tmp_path / 'model.task'
    service.model_path.write_bytes(b'fake')
    video = post(client, videos[('mp4','libx264',1)]).json()
    service.active = True
    assert client.post(f"/api/videos/{video['video_id']}/analyses",json={}).status_code == 409
    service.active = False
    job = dict(analysis_id='a'*32, video_id=video['video_id'], status='running', created_at='2026-11-08T00:00:00Z')
    service.save(job)
    restarted = TestClient(create_app(client.app.state.store.settings))
    recovered = restarted.get('/api/analyses/' + 'a'*32).json()
    assert recovered['status'] == 'failed'
    assert 'restart' in recovered['error']


def test_setup_labels_and_comparison_api(client, videos):
    first=post(client,videos[('mp4','libx264',1)]).json()
    second=post(client,videos[('mp4','libx264',1)]).json()
    url=f"/api/videos/{second['video_id']}/setup"
    updated=client.patch(url,json={'label':'Seatpost +20 mm','seatpost_extension_change_mm':20})
    assert updated.status_code==200
    assert updated.json()['seatpost_extension_change_mm']==20
    assert client.get(f"/api/videos/{second['video_id']}").json()['label']=='Seatpost +20 mm'
    assert client.patch(url,json={'label':'x'*81}).status_code==422
    assert client.patch('/api/videos/bad/setup',json={}).status_code==404
    from test_comparison import result
    service=client.app.state.analysis
    ids=['a'*32,'b'*32]
    for video,analysis_id,values in ((first,ids[0],[100,110,120]),(second,ids[1],[110,120,130])):
        service.save(dict(analysis_id=analysis_id,video_id=video['video_id'],status='completed',created_at='2026-11-08T00:00:00Z'))
        data=result(video['video_id'],values)
        data.update(start_seconds=10,duration_seconds=10)
        (service.root/analysis_id/'result.json').write_text(json.dumps(data))
    comparison=client.get(f'/api/comparisons?baseline_analysis_id={ids[0]}&candidate_analysis_id={ids[1]}&side=right')
    assert comparison.status_code==200,comparison.text
    data=comparison.json()
    assert data['metrics']['knee']['delta']['median']==10
    assert data['candidate']['video']['label']=='Seatpost +20 mm'
    assert data['candidate']['video']['seatpost_extension_change_mm']==20
    assert data['recommendations'] is None
    assert client.get(f'/api/comparisons?baseline_analysis_id={ids[0]}&candidate_analysis_id={ids[1]}&side=invalid').status_code==422
    job=service.get(ids[1]);job['status']='failed';service.save(job)
    assert client.get(f'/api/comparisons?baseline_analysis_id={ids[0]}&candidate_analysis_id={ids[1]}').status_code==409
