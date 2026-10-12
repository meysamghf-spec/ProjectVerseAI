"use client";

import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis, Area, AreaChart } from "recharts";

export function CategoryChart({ data }: { data: Array<{ name: string; amount: number }> }) {
  if (data.length === 0 || data.every((item) => item.amount === 0)) {
    return <p className="text-sm text-muted">No included cost lines are available to chart.</p>;
  }
  return (
    <div className="h-64 w-full">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data}>
          <CartesianGrid stroke="#314155" vertical={false} />
          <XAxis dataKey="name" stroke="#93a4b8" tick={{ fontSize: 12 }} />
          <YAxis stroke="#93a4b8" tick={{ fontSize: 12 }} />
          <Tooltip />
          <Bar dataKey="amount" fill="#e2a34a" radius={[6, 6, 0, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

export function SpendChart({ data }: { data: Array<{ day: number; cost: number }> }) {
  if (data.length === 0) {
    return <p className="text-sm text-muted">Planned expenditure has not been calculated.</p>;
  }
  return (
    <div className="h-64 w-full">
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart data={data}>
          <CartesianGrid stroke="#314155" vertical={false} />
          <XAxis dataKey="day" stroke="#93a4b8" tick={{ fontSize: 12 }} />
          <YAxis stroke="#93a4b8" tick={{ fontSize: 12 }} />
          <Tooltip />
          <Area type="monotone" dataKey="cost" stroke="#7eb8a8" fill="#7eb8a8" fillOpacity={0.25} />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}
