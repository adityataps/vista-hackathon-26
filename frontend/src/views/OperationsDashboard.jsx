import { useEffect, useState } from 'react';
import {
  BarChart, Bar, LineChart, Line, XAxis, YAxis, CartesianGrid,
  Tooltip, Legend, ResponsiveContainer,
} from 'recharts';
import {
  getKpis, getVolume, getLatency, getExceptionBreakdown,
  getCorrespondents, getAiStats,
} from '../api/client.js';

const tooltipStyle = {
  backgroundColor: '#0d1526',
  border: '1px solid #22304d',
  borderRadius: 8,
  color: '#e5ecf8',
  fontSize: 12,
};

const STATUS_PILL = {
  normal: ['green', '✓ Normal'],
  degraded: ['yellow', '⚠ Degraded'],
  outage: ['red', '✖ Outage'],
};

export default function OperationsDashboard() {
  const [kpis, setKpis] = useState(null);
  const [volume, setVolume] = useState([]);
  const [latency, setLatency] = useState([]);
  const [breakdown, setBreakdown] = useState([]);
  const [banks, setBanks] = useState([]);
  const [ai, setAi] = useState(null);

  useEffect(() => {
    getKpis().then(({ data }) => setKpis(data));
    getVolume().then(({ data }) => setVolume(data));
    getLatency().then(({ data }) => setLatency(data));
    getExceptionBreakdown().then(({ data }) => setBreakdown(data));
    getCorrespondents().then(({ data }) => setBanks(data));
    getAiStats().then(({ data }) => setAi(data));
  }, []);

  if (!kpis) return <div className="card">Loading…</div>;

  return (
    <>
      <div className="kpi-row">
        <div className="kpi">
          <div className="label">In-Flight Payments</div>
          <div className="value">{kpis.in_flight}</div>
          <div className="sub">across all rails &amp; corridors</div>
        </div>
        <div className="kpi">
          <div className="label">Open Exceptions</div>
          <div className="value">{kpis.exceptions_open}</div>
          <div className="sub">awaiting investigation or approval</div>
        </div>
        <div className="kpi">
          <div className="label">At-Risk (SLA)</div>
          <div className="value" style={{ color: '#f87171' }}>{kpis.at_risk}</div>
          <div className="sub">flagged by Monitor Agent</div>
        </div>
        <div className="kpi">
          <div className="label">Mean Time to Resolution</div>
          <div className="value">
            {kpis.mttr_before}<span className="arrow">→</span>{kpis.mttr_now}
          </div>
          <div className="sub">manual vs. AI investigation</div>
        </div>
      </div>

      <div className="grid-2">
        <div className="card">
          <h3>Transaction Volume (hourly, by rail)</h3>
          <ResponsiveContainer width="100%" height={260}>
            <BarChart data={volume}>
              <CartesianGrid strokeDasharray="3 3" stroke="#22304d" />
              <XAxis dataKey="hour" stroke="#8fa1c0" fontSize={11} />
              <YAxis stroke="#8fa1c0" fontSize={11} />
              <Tooltip contentStyle={tooltipStyle} cursor={{ fill: 'rgba(79,142,247,0.06)' }} />
              <Legend wrapperStyle={{ fontSize: 12 }} />
              <Bar dataKey="sepa_instant" name="SEPA Instant" stackId="a" fill="#4f8ef7" />
              <Bar dataKey="swift_gpi" name="SWIFT gpi" stackId="a" fill="#7c5cf0" />
              <Bar dataKey="fedwire" name="Fedwire" stackId="a" fill="#2dd4bf" />
              <Bar dataKey="exceptions" name="Exceptions" fill="#f87171" radius={[3, 3, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>

        <div className="card">
          <h3>Latency Percentiles by Corridor (min · current vs 7d benchmark)</h3>
          <ResponsiveContainer width="100%" height={260}>
            <LineChart data={latency}>
              <CartesianGrid strokeDasharray="3 3" stroke="#22304d" />
              <XAxis dataKey="corridor" stroke="#8fa1c0" fontSize={11} />
              <YAxis stroke="#8fa1c0" fontSize={11} />
              <Tooltip contentStyle={tooltipStyle} />
              <Legend wrapperStyle={{ fontSize: 12 }} />
              <Line type="monotone" dataKey="p50" name="p50" stroke="#34d399" strokeWidth={2} dot={{ r: 3 }} />
              <Line type="monotone" dataKey="p95" name="p95" stroke="#fbbf24" strokeWidth={2} dot={{ r: 3 }} />
              <Line type="monotone" dataKey="p99" name="p99" stroke="#f87171" strokeWidth={2} dot={{ r: 3 }} />
              <Line type="monotone" dataKey="bench_p95" name="p95 benchmark (7d)" stroke="#8fa1c0" strokeDasharray="6 4" strokeWidth={1.5} dot={false} />
            </LineChart>
          </ResponsiveContainer>
        </div>

        <div className="card">
          <h3>Exception Breakdown (today)</h3>
          <ResponsiveContainer width="100%" height={240}>
            <BarChart data={breakdown} layout="vertical" margin={{ left: 30 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#22304d" />
              <XAxis type="number" stroke="#8fa1c0" fontSize={11} allowDecimals={false} />
              <YAxis type="category" dataKey="type" stroke="#8fa1c0" fontSize={12} width={110} />
              <Tooltip contentStyle={tooltipStyle} cursor={{ fill: 'rgba(79,142,247,0.06)' }} />
              <Legend wrapperStyle={{ fontSize: 12 }} />
              <Bar dataKey="auto_resolved" name="Auto-resolved" stackId="x" fill="#34d399" />
              <Bar dataKey="escalated" name="Escalated (HITL)" stackId="x" fill="#fbbf24" radius={[0, 3, 3, 0]} />
            </BarChart>
          </ResponsiveContainer>
          {ai && (
            <div className="footnote">
              AI performance: {ai.total_investigations} investigations · {Math.round(ai.recommendation_acceptance_rate * 100)}% recommendation acceptance · avg {ai.avg_investigation_seconds}s per investigation
            </div>
          )}
        </div>

        <div className="card">
          <h3>Correspondent Health</h3>
          <table>
            <thead>
              <tr><th>BIC</th><th>Bank</th><th>Status</th><th>Avg Time</th><th>Delayed</th></tr>
            </thead>
            <tbody>
              {banks.map((b) => {
                const [cls, label] = STATUS_PILL[b.status] ?? STATUS_PILL.normal;
                return (
                  <tr key={b.bic}>
                    <td className="num">{b.bic}</td>
                    <td>{b.bank}</td>
                    <td><span className={`pill ${cls}`}>{label}</span></td>
                    <td className="num">{b.avg_processing_min} min</td>
                    <td className="num" style={b.delayed > 0 ? { color: '#f87171', fontWeight: 700 } : {}}>
                      {b.delayed}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>
    </>
  );
}
