import React, { useState } from 'react';
import type { VideoMetadata } from './api';
export default function SetupEditor({ video, onSave }: { video: VideoMetadata; onSave: (video: VideoMetadata) => void }) {
  const [label, setLabel] = useState(video.label ?? '');
  const [change, setChange] = useState(video.seatpost_extension_change_mm?.toString() ?? '');
  const [busy, setBusy] = useState(false), [message, setMessage] = useState('');
  async function save() {
    setBusy(true); setMessage('');
    try {
      const response = await fetch(`/api/videos/${video.video_id}/setup`, { method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ label, seatpost_extension_change_mm: change === '' ? null : Number(change) }) });
      const data = await response.json();
      if (!response.ok) throw new Error(typeof data.detail === 'string' ? data.detail : 'Could not save setup details.');
      onSave(data); setMessage('Setup saved.');
    } catch (e) { setMessage(e instanceof Error ? e.message : 'Could not save setup details.'); }
    finally { setBusy(false); }
  }
  return <div className="setup-editor"><label>Recording label<input aria-label={`${video.view} recording label`} maxLength={80} placeholder="e.g. Baseline or Seatpost +20 mm" value={label} onChange={e => setLabel(e.target.value)} /></label><label>Seatpost extension change (mm)<input aria-label={`${video.view} seatpost extension change`} type="number" step="any" placeholder="Unknown" value={change} onChange={e => setChange(e.target.value)} /></label><small>Optional, self-reported change relative to your baseline. This is not a measured vertical saddle-height change.</small><button disabled={busy} onClick={() => void save()}>{busy ? 'Saving…' : 'Save setup details'}</button>{message && <p role="status">{message}</p>}</div>;
}
