export type View = 'side' | 'front' | 'rear';
export interface VideoMetadata {
  label?: string; seatpost_extension_change_mm?: number | null;
  video_id: string; view: View; width: number; height: number;
  duration_seconds: number; frame_rate: number; size_bytes: number;
  codec: string; preview_url?: string | null; content_url: string; uploaded_at: string;
}
export async function uploadVideo(view: View, file: File): Promise<VideoMetadata> {
  const body = new FormData(); body.append('view', view); body.append('file', file);
  const response = await fetch('/api/videos', { method: 'POST', body });
  const data = await response.json().catch(() => null);
  if (!response.ok) throw new Error(typeof data?.detail === 'string' ? data.detail : `Upload failed (${response.status}). Check the file and try again.`);
  return data;
}
