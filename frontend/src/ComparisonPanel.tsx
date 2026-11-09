import React, { useEffect, useState } from 'react';
import type { VideoMetadata } from './api';
type Ready = { analysis_id: string; video_id: string };
type Summary = { valid_samples: number; total_samples: number; coverage: number; minimum: number; p05: number; median: number; p95: number; maximum: number };
type Comparison = { side: string; metrics: Record<string, { baseline: Summary | null; candidate: Summary | null; delta: Record<string, number> | null }>; warnings: string[] };
const number = (n: number | null | undefined) => n == null ? 'Unavailable' : `${n.toFixed(1)}°`;
export default function ComparisonPanel({ videos }: { videos: VideoMetadata[] }) {
  const [ready, setReady] = useState<Ready[]>([]), [baseline, setBaseline] = useState(''), [candidate, setCandidate] = useState('');
  const [side, setSide] = useState('right'), [comparison, setComparison] = useState<Comparison | null>(null);
  const [busy, setBusy] = useState(false), [error, setError] = useState('');
  const sideVideos = videos.filter(v => v.view === 'side');
  const signature = sideVideos.map(v => v.video_id).join(',');
  async function refresh() {
    setError(''); setComparison(null); setBusy(true);
    try {
      const jobs = await Promise.all(sideVideos.map(async video => {
        const r = await fetch(`/api/videos/${video.video_id}/analyses/latest`);
        if (!r.ok) throw new Error('Could not load tracking results.');
        return r.json();
      }));
      const complete = jobs.filter(j => j?.status === 'completed') as Ready[];
      setReady(complete);
      setBaseline(value => complete.some(j => j.analysis_id === value) ? value : complete[complete.length-1]?.analysis_id ?? '');
      setCandidate(value => complete.some(j => j.analysis_id === value) ? value : complete.length > 1 ? complete[0].analysis_id : '');
    } catch (e) { setError(e instanceof Error ? e.message : 'Could not refresh results.'); }
    finally { setBusy(false); }
  }
  useEffect(() => { if (sideVideos.length >= 2) void refresh(); }, [signature]);
  function selection(update: () => void) { update(); setComparison(null); }
  async function compare() {
    setBusy(true); setError(''); setComparison(null);
    try {
      const response = await fetch(`/api/comparisons?baseline_analysis_id=${baseline}&candidate_analysis_id=${candidate}&side=${side}`);
      const data = await response.json();
      if (!response.ok) throw new Error(typeof data.detail === 'string' ? data.detail : 'Comparison failed.');
      setComparison(data);
    } catch (e) { setError(e instanceof Error ? e.message : 'Comparison failed.'); }
    finally { setBusy(false); }
  }
  const options = ready.map(j => { const v = sideVideos.find(v => v.video_id === j.video_id); return <option key={j.analysis_id} value={j.analysis_id}>{v?.label || `Side · ${v ? new Date(v.uploaded_at).toLocaleString() : j.video_id}`} · {j.video_id.slice(0,6)}</option>; });
  return <section className="comparison card" aria-label="Bike position comparison"><h2>Compare two bike positions</h2><p>Upload another side recording and save labels such as “Baseline” and “Seatpost +20 mm.” Run tracking on a steady-pedaling clip from each, then refresh results here.</p><p>Use the same anatomical side, camera placement, workload, cadence, footwear, and hand position. These recordings are separate sessions; the clap cue is not used for alignment.</p>
    <button disabled={busy} onClick={() => void refresh()}>Refresh tracking results</button>
    <div className="compare-controls"><label>Baseline<select disabled={busy} aria-label="Baseline recording" value={baseline} onChange={e => selection(() => setBaseline(e.target.value))}><option value="">Choose baseline</option>{options}</select></label><label>New position<select disabled={busy} aria-label="Candidate recording" value={candidate} onChange={e => selection(() => setCandidate(e.target.value))}><option value="">Choose new position</option>{options}</select></label><label>Anatomical side<select disabled={busy} aria-label="Comparison anatomical side" value={side} onChange={e => selection(() => setSide(e.target.value))}><option value="right">Right</option><option value="left">Left</option></select></label></div>
    <button className="track-button" disabled={busy || !baseline || !candidate || baseline === candidate} onClick={() => void compare()}>{busy ? 'Comparing…' : 'Compare angle estimates'}</button>
    {error && <p className="error" role="alert">{error}</p>}
    {comparison && <><p>2D interior angles · 180° is straight · change = new position minus baseline. These are observed clip summaries, not a bike-fit score.</p><div className="comparison-table"><table><thead><tr><th>Joint</th><th>Baseline median</th><th>New median</th><th>Median change</th><th>Baseline P5–P95</th><th>New P5–P95</th><th>Valid samples: baseline / new</th></tr></thead><tbody>{Object.entries(comparison.metrics).map(([name,m]) => <tr key={name}><th>{name}</th><td>{number(m.baseline?.median)}</td><td>{number(m.candidate?.median)}</td><td>{m.delta ? `${m.delta.median >= 0 ? '+' : ''}${number(m.delta.median)}` : 'Unavailable'}</td><td>{m.baseline ? `${number(m.baseline.p05)}–${number(m.baseline.p95)}` : 'Unavailable'}</td><td>{m.candidate ? `${number(m.candidate.p05)}–${number(m.candidate.p95)}` : 'Unavailable'}</td><td>{m.baseline ? `${m.baseline.valid_samples}/${m.baseline.total_samples}` : '0'} / {m.candidate ? `${m.candidate.valid_samples}/${m.candidate.total_samples}` : '0'}</td></tr>)}</tbody></table></div><ul>{comparison.warnings.map(w => <li key={w}>{w}</li>)}</ul><p>No recommendation is generated from these differences. Repeatability and measurement error have not yet been validated.</p></>}
  </section>;
}
