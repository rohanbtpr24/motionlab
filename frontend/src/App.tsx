import React, { useState, useEffect } from 'react';
import { uploadVideo, type VideoMetadata, type View } from './api';
import './style.css';
import TrackingPanel from './TrackingPanel';
import SetupEditor from './SetupEditor';
import ComparisonPanel from './ComparisonPanel';

const views: View[] = ['side', 'front', 'rear'];
function VideoCard({ view, index, initial, history, onReady }: { view: View; index: number; initial?: VideoMetadata; history: VideoMetadata[]; onReady: (video: VideoMetadata) => void }) {
  const [video, setVideo] = useState<VideoMetadata | undefined>(initial);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [previewError, setPreviewError] = useState(false);
  async function upload(file?: File) {
    if (!file) return;
    setBusy(true); setError('');
    try { const next = await uploadVideo(view, file); onReady(next); setVideo(next); setPreviewError(false); }
    catch (e) { setError(e instanceof Error ? e.message : 'Upload failed. Confirm the backend is running and try again.'); }
    finally { setBusy(false); }
  }
  return <article className="card" aria-busy={busy}>
    <div className="card-title"><span className="number">0{index + 1}</span><h2>{view} view</h2><span className={'badge ' + (video ? 'ready' : '')}>{video ? 'Uploaded' : 'Awaiting video'}</span></div>
    {history.length > 1 && <label className="recording-picker">Saved {view} recording<select aria-label={`Saved ${view} recording`} value={video?.video_id ?? ''} disabled={busy} onChange={e => { setVideo(history.find(v => v.video_id === e.target.value)); setPreviewError(false); }}>{history.map(v => <option key={v.video_id} value={v.video_id}>{v.label || new Date(v.uploaded_at).toLocaleString()} · {v.video_id.slice(0,6)}</option>)}</select></label>}
    <div className="preview">{video ? <video key={video.video_id} controls preload="metadata" src={video.preview_url ?? video.content_url} onError={() => setPreviewError(true)} /> : <div><span className="camera">▣</span><p>{view === 'side' ? 'Capture the full bike and rider' : view === 'front' ? 'Center the rider in the frame' : 'Keep the rider and trainer visible'}</p><small>Landscape recording recommended</small></div>}</div>
    {video && <dl><div><dt>Resolution</dt><dd>{video.width} × {video.height}</dd></div><div><dt>Duration</dt><dd>{video.duration_seconds.toFixed(2)} s</dd></div><div><dt>Frame rate</dt><dd>{video.frame_rate.toFixed(2)} fps</dd></div><div><dt>File size</dt><dd>{(video.size_bytes / 1048576).toFixed(1)} MB</dd></div></dl>}
    {video && <p className="id">ID · {video.video_id}</p>}
    <label className={'upload ' + (busy ? 'disabled' : '')}>{busy ? 'Uploading & validating…' : video ? 'Upload another video' : 'Choose video'}<input aria-label={`Upload ${view} video`} type="file" accept=".mp4,.mov" disabled={busy} onChange={e => { void upload(e.target.files?.[0]); e.target.value = ''; }} /></label>
    <p className="error" role="alert">{error || (previewError ? 'Your browser could not preview this video. The original upload is saved.' : '')}</p>
    {busy && <p className="status" role="status">Validating video and preparing a preview. Large videos can take a few minutes.</p>}
    {video && <SetupEditor key={`setup-${video.video_id}`} video={video} onSave={next => { setVideo(next); onReady(next); }} />}
    {video && <TrackingPanel key={video.video_id} video={video} />}
  </article>;
}
export default function App() {
  const [count, setCount] = useState(0);
  const [saved, setSaved] = useState<VideoMetadata[]>([]);
  const [loadError, setLoadError] = useState('');
  useEffect(() => {
    let cancelled = false;
    fetch('/api/videos').then(async r => { if (!r.ok) throw new Error('Could not restore uploaded videos.'); return r.json(); }).then((items: VideoMetadata[]) => {
      if (cancelled) return;
      const latest = views.map(view => items.find(v => v.view === view)).filter((v): v is VideoMetadata => !!v);
      setSaved(items); setCount(latest.length);
    }).catch(e => { if (!cancelled) setLoadError(e.message); });
    return () => { cancelled = true; };
  }, []);
  return <><header><a className="brand" href="/">◈ <span>MotionLab</span></a><span className="local"><i /> Local workspace</span></header><main><div className="eyebrow">CYCLING / VIDEO INGESTION</div><div className="intro"><div><h1>A clearer view of your ride.</h1><p>Start with your side and front recordings. Add a rear view when available.</p></div><div className="counter"><strong>{count}<span> / 3</span></strong><small>views available</small></div></div><section className="notice"><strong>Independent recording sessions</strong><span>Side and Front are analyzed separately. Rear is optional. A clap cue does not synchronize recordings from different sessions.</span></section>{loadError && <p className="error" role="alert">{loadError}</p>}<section className="grid" aria-label="Camera uploads">{views.map((view, i) => <VideoCard key={saved.find(v => v.view === view)?.video_id ?? view} initial={saved.find(v => v.view === view)} history={saved.filter(v => v.view === view)} view={view} index={i} onReady={next => { const updated = saved.some(v => v.video_id === next.video_id) ? saved.map(v => v.video_id === next.video_id ? next : v) : [next, ...saved]; setSaved(updated); setCount(new Set(updated.map(v => v.view)).size); }} />)}</section><ComparisonPanel videos={saved} /><footer><span>MP4 or MOV · H.264 or HEVC · up to 500 MB and 5 minutes per video · max 4096 px</span><p>Videos stay on this computer. Tracking uses local MediaPipe estimates; colored-dot tracking, calibration, and synchronization are not implemented. Three views alone do not establish accurate 3D measurements.</p></footer></main></>;
}
