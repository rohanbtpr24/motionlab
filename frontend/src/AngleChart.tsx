import React from 'react';
import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
export default function AngleChart({ data }: { data: { t: number; hip: number | null; knee: number | null; ankle: number | null }[] }) {
  return <div className="angle-chart" aria-label="Estimated joint angles over clip time"><ResponsiveContainer width="100%" height={180}><LineChart data={data}><CartesianGrid strokeDasharray="3 3" /><XAxis dataKey="t" unit="s" minTickGap={30} /><YAxis domain={[0,180]} unit="°" width={45} /><Tooltip /><Line name="Hip" dataKey="hip" stroke="#087f69" dot={false} isAnimationActive={false} /><Line name="Knee" dataKey="knee" stroke="#a13486" dot={false} isAnimationActive={false} /><Line name="Ankle" dataKey="ankle" stroke="#b37e00" dot={false} isAnimationActive={false} /></LineChart></ResponsiveContainer></div>;
}
