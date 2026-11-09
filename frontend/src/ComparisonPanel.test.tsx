// @vitest-environment jsdom
import React from 'react';
import { afterEach, expect, test, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import ComparisonPanel from './ComparisonPanel';
import SetupEditor from './SetupEditor';
import type { VideoMetadata } from './api';
const base: VideoMetadata = { video_id: 'old', view:'side', label:'Baseline', width:1920,height:1080,duration_seconds:20,frame_rate:60,size_bytes:100,codec:'h264',content_url:'/old',uploaded_at:'2026-11-08T00:00:00Z' };
const candidate: VideoMetadata = {...base,video_id:'new',label:'Seatpost +20 mm',content_url:'/new'};
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

test('comparison requires two different completed analyses', async () => {
  vi.stubGlobal('fetch', vi.fn(async () => ({ok:true,json:async()=>({analysis_id:'a',video_id:'old',status:'completed'})})));
  render(<ComparisonPanel videos={[base]} />);
  expect((screen.getByText('Compare angle estimates') as HTMLButtonElement).disabled).toBe(true);
  fireEvent.click(screen.getByText('Refresh tracking results'));
  await waitFor(()=>expect((screen.getByLabelText('Baseline recording') as HTMLSelectElement).value).toBe('a'));
  expect((screen.getByText('Compare angle estimates') as HTMLButtonElement).disabled).toBe(true);
});

test('compares selected recordings and reports descriptive differences', async () => {
  const summary = {valid_samples:100,total_samples:150,coverage:2/3,minimum:90,p05:95,median:110,p95:130,maximum:140};
  const comparison = {side:'right',metrics:{knee:{baseline:summary,candidate:{...summary,median:115},delta:{median:5}}},warnings:['Independent sessions.']};
  const fetch = vi.fn(async (url: string) => ({ok:true,json:async()=>url.startsWith('/api/comparisons') ? comparison : {analysis_id:url.includes('/old/')?'a':'b',video_id:url.includes('/old/')?'old':'new',status:'completed'}}));
  vi.stubGlobal('fetch',fetch);
  render(<ComparisonPanel videos={[candidate,base]} />);
  await waitFor(()=>expect((screen.getByText('Compare angle estimates') as HTMLButtonElement).disabled).toBe(false));
  fireEvent.click(screen.getByText('Compare angle estimates'));
  await screen.findByText('+5.0°');
  expect(fetch.mock.calls.some(([url])=>url.includes('baseline_analysis_id=a&candidate_analysis_id=b&side=right'))).toBe(true);
  expect(screen.getByText('100/150 / 100/150')).toBeTruthy();
  expect(screen.getByText('Independent sessions.')).toBeTruthy();
  fireEvent.change(screen.getByLabelText('Comparison anatomical side'),{target:{value:'left'}});
  expect(screen.queryByText('+5.0°')).toBeNull();
});

test('setup annotations persist as explicitly entered millimeters', async () => {
  const save=vi.fn();
  const fetch=vi.fn(async (_url:string,_options?:RequestInit)=>({ok:true,json:async()=>({...candidate,seatpost_extension_change_mm:20})}));
  vi.stubGlobal('fetch',fetch);
  render(<SetupEditor video={base} onSave={save} />);
  fireEvent.change(screen.getByLabelText('side recording label'),{target:{value:'Seatpost +20 mm'}});
  fireEvent.change(screen.getByLabelText('side seatpost extension change'),{target:{value:'20'}});
  fireEvent.click(screen.getByText('Save setup details'));
  await screen.findByText('Setup saved.');
  expect(JSON.parse(fetch.mock.calls[0][1]!.body as string)).toEqual({label:'Seatpost +20 mm',seatpost_extension_change_mm:20});
  expect(save).toHaveBeenCalledOnce();
});
