// @vitest-environment jsdom
import React from 'react';
import { afterEach, expect, test, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import App from './App';

function stubFetch(handler: (...args: any[]) => any) {
  vi.stubGlobal('fetch', (url: string, options?: RequestInit) => {
    if (url === '/api/videos' && !options) return Promise.resolve({ ok: true, json: async () => [] });
    if (url.endsWith('/analyses/latest')) return Promise.resolve({ ok: true, json: async () => null });
    return handler(url, options);
  });
}

afterEach(() => { cleanup(); vi.unstubAllGlobals(); });
const metadata = { video_id: 'a'.repeat(32), view: 'side', width: 1920, height: 1080, duration_seconds: 12.5, frame_rate: 29.97, size_bytes: 1048576, codec: 'h264', content_url: '/api/videos/test/content', uploaded_at: '2026-11-08T00:00:00Z' };
function choose() { fireEvent.change(screen.getByLabelText('Upload side video'), { target: { files: [new File(['video'], 'ride.mp4', { type: 'video/mp4' })] } }); }

test('renders three labeled inputs', () => {
  render(<App />);
  for (const view of ['side', 'front', 'rear']) expect(screen.getByLabelText(`Upload ${view} video`)).toBeTruthy();
});

test('shows validation state then preview and server metadata', async () => {
  let resolve!: (value: unknown) => void;
  const fetch = vi.fn(() => new Promise(r => { resolve = r; })); stubFetch(fetch);
  const { container } = render(<App />); choose();
  expect((screen.getByLabelText('Upload side video') as HTMLInputElement).disabled).toBe(true);
  expect(screen.getByRole('status').textContent).toContain('Validating video');
  const body = fetch.mock.calls[0] as unknown as [string, { body: FormData }];
  expect(body[1].body.get('view')).toBe('side');
  resolve({ ok: true, json: async () => metadata });
  await screen.findByText('1920 × 1080');
  expect(screen.getByText('29.97 fps')).toBeTruthy();
  expect(container.querySelector('video')?.getAttribute('src')).toBe(metadata.content_url);
  expect((screen.getByLabelText('Upload side video') as HTMLInputElement).disabled).toBe(false);
  expect(screen.getByText('Uploaded')).toBeTruthy();
});

test('shows server validation errors', async () => {
  stubFetch(vi.fn(async () => ({ ok: false, status: 415, json: async () => ({ detail: 'Use H.264 video.' }) })));
  render(<App />); choose();
  await screen.findByText('Use H.264 video.');
  expect(screen.queryByText('Uploaded')).toBeNull();
});

test('recovers from network failure and permits retry', async () => {
  stubFetch(vi.fn().mockRejectedValueOnce(new Error('Connection unavailable')).mockResolvedValue({ ok: true, json: async () => metadata }));
  render(<App />); choose();
  await screen.findByText('Connection unavailable');
  await waitFor(() => expect((screen.getByLabelText('Upload side video') as HTMLInputElement).disabled).toBe(false));
  choose(); await screen.findByText('1920 × 1080');
  expect(screen.queryByText('Connection unavailable')).toBeNull();
});


test('uses the compatible preview when the server supplies one', async () => {
  stubFetch(vi.fn(async () => ({ ok: true, json: async () => ({ ...metadata, codec: 'hevc', preview_url: '/api/videos/test/preview' }) })));
  const { container } = render(<App />); choose();
  await screen.findByText('1920 × 1080');
  expect(container.querySelector('video')?.getAttribute('src')).toBe('/api/videos/test/preview');
});


test('restores saved views after refresh without requiring all three cameras', async () => {
  vi.stubGlobal('fetch', vi.fn(async (url: string) => ({ ok: true, json: async () => url === '/api/videos' ? [metadata] : null })));
  render(<App />);
  await screen.findByText('1920 × 1080');
  expect(screen.getByRole('region', { name: 'side joint tracking' })).toBeTruthy();
  expect(screen.getByText(/A clap cue does not synchronize/)).toBeTruthy();
  expect(screen.getByLabelText('Upload rear video')).toBeTruthy();
});

test('starts an independent clip job with the selected range and shows failures', async () => {
  const post = vi.fn(async (_url: string, _options?: RequestInit) => ({ ok: true, json: async () => ({ analysis_id: 'job-1', status: 'queued', progress: 0 }) }));
  vi.stubGlobal('fetch', vi.fn(async (url: string, options?: RequestInit) => {
    if (options?.method === 'POST') return post(url, options);
    return { ok: true, json: async () => url === '/api/videos' ? [metadata] : url.endsWith('/latest') ? null : { analysis_id: 'job-1', status: 'failed', error: 'No model available' } };
  }));
  render(<App />);
  const button = await screen.findByText('Run joint tracking');
  fireEvent.change(screen.getByLabelText('side clip start'), { target: { value: '3' } });
  fireEvent.change(screen.getByLabelText('side clip length'), { target: { value: '5' } });
  fireEvent.click(button);
  await screen.findByText('No model available');
  const args = post.mock.calls[0] as unknown as [string, RequestInit];
  expect(args[0]).toBe(`/api/videos/${metadata.video_id}/analyses`);
  expect(JSON.parse(args[1].body as string)).toEqual({ start_seconds: 3, duration_seconds: 5 });
});

vi.mock('./AngleChart', () => ({ default: () => <div>Angle timeline</div> }));

test('restores completed tracking and draws only confident joints with angles', async () => {
  const { act } = await import('@testing-library/react');
  let tick: FrameRequestCallback | undefined;
  vi.stubGlobal('requestAnimationFrame', (callback: FrameRequestCallback) => { tick = callback; return 1; });
  vi.stubGlobal('cancelAnimationFrame', vi.fn());
  const points = Array.from({ length: 33 }, (_, i) => ({ x: .5, y: .5, visibility: [12,14,16,24,26,28,32].includes(i) ? 1 : 0, presence: 1 }));
  const job = { analysis_id: 'job-complete', status: 'completed', progress: 100, result_url: '/api/analyses/job-complete/result' };
  const result = { width: 160, height: 120, start_seconds: 0, duration_seconds: 1, detected_frames: 1, total_frames: 1, frames: [{ time_seconds: 0, landmarks: points, angles: { right_hip: 110, right_knee: 90, right_ankle: 120, left_knee: null } }] };
  vi.stubGlobal('fetch', vi.fn(async (url: string) => ({ ok: true, json: async () => url === '/api/videos' ? [metadata] : url === job.result_url ? result : job })));
  const { container } = render(<App />);
  await screen.findByLabelText('Estimated skeleton overlay');
  await waitFor(() => expect(tick).toBeTruthy());
  act(() => { tick!(0); });
  await screen.findByText('90.0°');
  expect((screen.getByLabelText('side anatomical side') as HTMLSelectElement).value).toBe('right');
  expect(container.querySelectorAll('svg circle').length).toBe(7);
  expect(container.querySelectorAll('svg line').length).toBeGreaterThan(0);
  fireEvent.change(screen.getByLabelText('side anatomical side'), { target: { value: 'left' } });
  expect(screen.queryByText('90.0°')).toBeNull();
});


test('keeps older side recordings selectable after a new upload', async () => {
  const older = {...metadata, video_id:'old-side', label:'Baseline', content_url:'/baseline.mp4'};
  const newer = {...metadata, video_id:'new-side', label:'Seatpost +20 mm', content_url:'/raised.mp4'};
  vi.stubGlobal('fetch',vi.fn(async (url:string)=>({ok:true,json:async()=>url==='/api/videos'?[newer,older]:null})));
  const {container}=render(<App />);
  const picker=await screen.findByLabelText('Saved side recording');
  expect(container.querySelector('video')?.getAttribute('src')).toBe('/raised.mp4');
  fireEvent.change(picker,{target:{value:'old-side'}});
  expect(container.querySelector('video')?.getAttribute('src')).toBe('/baseline.mp4');
  expect((screen.getByLabelText('side recording label') as HTMLInputElement).value).toBe('Baseline');
});
