import React, { Suspense, lazy, useEffect, useRef, useState } from 'react';
const AngleChart = lazy(() => import('./AngleChart'));
import type { VideoMetadata } from './api';

type Job = { analysis_id: string; status: 'queued' | 'running' | 'completed' | 'failed'; progress: number; error?: string; result_url?: string };
type Landmark = { x: number; y: number; visibility: number; presence: number };
type Sample = { time_seconds: number; landmarks: Landmark[] | null; angles: Record<string, number | null> };
type Result = { frames: Sample[]; width: number; height: number; start_seconds: number; duration_seconds: number; detected_frames: number; total_frames: number };
const edges = [[11,12],[11,13],[13,15],[12,14],[14,16],[11,23],[12,24],[23,24],[23,25],[25,27],[27,31],[24,26],[26,28],[28,32]];
async function request<T>(url: string, options?: RequestInit): Promise<T> {
  const response = await fetch(url, options);
  const data = await response.json();
  if (!response.ok) throw new Error(typeof data.detail === 'string' ? data.detail : 'Tracking request failed.');
  return data;
}
const visible = (p: Landmark) => p.visibility >= 0.6 && p.presence >= 0.6 && p.x >= 0 && p.x <= 1 && p.y >= 0 && p.y <= 1;

export default function TrackingPanel({ video }: { video: VideoMetadata }) {
  const [start, setStart] = useState(0), [duration, setDuration] = useState(10);
  const [job, setJob] = useState<Job | null>(null), [result, setResult] = useState<Result | null>(null);
  const [error, setError] = useState(''), [submitting, setSubmitting] = useState(false);
  const [side, setSide] = useState('left'), [sampleIndex, setSampleIndex] = useState(-1);
  const player = useRef<HTMLVideoElement>(null);
  useEffect(() => {
    let cancelled = false;
    setResult(null); setJob(null);
    request<Job | null>(`/api/videos/${video.video_id}/analyses/latest`).then(data => { if (!cancelled) setJob(data); }).catch(e => { if (!cancelled) setError(e.message); });
    return () => { cancelled = true; };
  }, [video.video_id]);
  useEffect(() => {
    if (!job || job.status === 'failed') return;
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout>;
    async function update() {
      try {
        const next = await request<Job>(`/api/analyses/${job!.analysis_id}`);
        if (cancelled) return;
        setError('');
        if (next.status === 'completed' && next.result_url) {
          const data = await request<Result>(next.result_url);
          if (!cancelled) {
            setResult(data); setJob(next);
            const count = (side: string) => data.frames.filter(f => f.angles[`${side}_knee`] != null).length;
            setSide(count('right') > count('left') ? 'right' : 'left');
          }
        } else if (next.status === 'failed') setJob(next);
        else { setJob(next); timer = setTimeout(update, 1000); }
      } catch (e) {
        if (!cancelled) {
          setError((e instanceof Error ? e.message : 'Could not read tracking progress.') + ' Retrying…');
          timer = setTimeout(update, 3000);
        }
      }
    }
    void update();
    return () => { cancelled = true; clearTimeout(timer); };
  }, [job?.analysis_id]);
  useEffect(() => {
    if (!result) return;
    let animation: number;
    function tick() {
      const time = player.current?.currentTime ?? -1;
      const index = Math.round((time - result!.start_seconds) * 15);
      setSampleIndex(index >= 0 && index < result!.frames.length ? index : -1);
      animation = requestAnimationFrame(tick);
    }
    animation = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(animation);
  }, [result]);
  async function run() {
    setError(''); setSubmitting(true); setResult(null);
    try {
      setJob(await request<Job>(`/api/videos/${video.video_id}/analyses`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ start_seconds: start, duration_seconds: duration }) }));
    } catch (e) { setError(e instanceof Error ? e.message : 'Could not start tracking.'); }
    finally { setSubmitting(false); }
  }
  const busy = submitting || job?.status === 'queued' || job?.status === 'running';
  const sample = result?.frames[sampleIndex];
  const landmarks = sample?.landmarks;
  const chart = result?.frames.map(f => ({ t: +(f.time_seconds - result.start_seconds).toFixed(2), hip: f.angles[`${side}_hip`], knee: f.angles[`${side}_knee`], ankle: f.angles[`${side}_ankle`] }));
  return <section className="tracking" aria-label={`${video.view} joint tracking`}>
    <h3>Joint tracking preview</h3>
    <p>Independent session · 2D estimates · no synchronization</p>
    {video.view !== 'side' && <p className="tracking-note">Front-view flexion angles are strongly affected by projection. Use Side for hip, knee, and ankle flexion inspection.</p>}
    <div className="clip-controls"><label>Start (s)<input aria-label={`${video.view} clip start`} type="number" min="0" max={video.duration_seconds} step="1" value={start} disabled={busy} onChange={e => setStart(+e.target.value)} /></label><label>Length (s)<input aria-label={`${video.view} clip length`} type="number" min="1" max="30" value={duration} disabled={busy} onChange={e => setDuration(+e.target.value)} /></label></div>
    <button className="track-button" disabled={busy} onClick={() => void run()}>{busy ? `Tracking… ${job?.progress ?? 0}%` : 'Run joint tracking'}</button>
    {busy && <p role="status">Processing locally. One clip at a time; keep this window open to see progress.</p>}
    {(error || job?.error) && <p className="error" role="alert">{error || job?.error}</p>}
    {result && <>
      <p>Pose detected in {result.detected_frames} / {result.total_frames} samples. Play the clip to inspect the skeleton.</p>
      <div className="skeleton-player">
        <video ref={player} controls preload="metadata" src={video.preview_url ?? video.content_url} onLoadedMetadata={e => { e.currentTarget.currentTime = result.start_seconds; }} onTimeUpdate={e => { if (e.currentTarget.currentTime >= result.start_seconds + result.duration_seconds) e.currentTarget.pause(); }} />
        <svg aria-label="Estimated skeleton overlay" viewBox="0 0 1 1" preserveAspectRatio="none">
          {landmarks && edges.map(([a,b]) => visible(landmarks[a]) && visible(landmarks[b]) ? <line key={`${a}-${b}`} x1={landmarks[a].x} y1={landmarks[a].y} x2={landmarks[b].x} y2={landmarks[b].y} stroke={a % 2 ? '#19f6ab' : '#ff72cc'} strokeWidth="0.005" /> : null)}
          {landmarks?.map((p,i) => i >= 11 && visible(p) ? <circle key={i} cx={p.x} cy={p.y} r="0.007" fill="#fff14e" /> : null)}
        </svg>
      </div>
      <p>{sample ? landmarks ? 'Green: anatomical left · pink: anatomical right' : 'No pose detected at this time.' : 'Seek inside the analyzed clip to see tracking.'}</p>
      <label>Inspect anatomical side <select aria-label={`${video.view} anatomical side`} value={side} onChange={e => setSide(e.target.value)}><option value="left">Left</option><option value="right">Right</option></select></label>
      <dl>{['hip','knee','ankle'].map(name => <div key={name}><dt>{name} interior angle</dt><dd>{sample?.angles[`${side}_${name}`] != null ? `${sample.angles[`${side}_${name}`]!.toFixed(1)}°` : 'Unavailable'}</dd></div>)}</dl>
      <Suspense fallback={<p>Loading angle chart…</p>}><AngleChart data={chart ?? []} /></Suspense>
      <p>Interior angles: shoulder–hip–knee, hip–knee–ankle, and knee–ankle–toe. 180° is straight. Low-confidence estimates are hidden. These are model landmarks, not tracked colored dots or calibrated measurements.</p>
    </>}
  </section>;
}
