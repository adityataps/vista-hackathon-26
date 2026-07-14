import { useEffect, useState } from 'react';
import { getAlerts, getInflight, getHeatmap } from '../api/client.js';

const RISK = {
  'breached': ['red', '🔴 Breached'],
  'at-risk': ['yellow', '🟡 At-Risk'],
  'on-track': ['green', '🟢 On-Track'],
};

const HM_CLS = { ok: 'hm-ok', warn: 'hm-warn', bad: 'hm-bad' };
const HM_LABEL = { ok: 'on-track', warn: 'at-risk', bad: 'breached' };

export default function BottleneckMonitor() {
  const [alerts, setAlerts] = useState([]);
  const [inflight, setInflight] = useState([]);
  const [hm, setHm] = useState(null);
  const [escalated, setEscalated] = useState({});

  useEffect(() => {
    getAlerts().then(({ data }) => setAlerts(data));
    getInflight().then(({ data }) => setInflight(data));
    getHeatmap().then(({ data }) => setHm(data));
  }, []);

  return (
    <>
      {alerts.map((a) => (
        <div
          className="alert-banner"
          key={a.id}
          style={a.severity === 'warning' ? { borderColor: '#fbbf24', background: 'rgba(251,191,36,0.06)' } : {}}
        >
          <div className="icon">{a.severity === 'critical' ? '🔴' : '🟡'}</div>
          <div className="body">
            <div className="title" style={a.severity === 'warning' ? { color: '#fbbf24' } : {}}>
              {a.severity === 'critical' ? 'ACTIVE ALERT' : 'EARLY WARNING'}: {a.title}
            </div>
            <div className="detail">{a.detail}</div>
            <div className="detail">
              Affected: {a.payments.join(', ')} · Recommended: <strong>{a.recommended}</strong>
            </div>
          </div>
          <button
            className="btn primary"
            disabled={escalated[a.id]}
            onClick={() => setEscalated((e) => ({ ...e, [a.id]: true }))}
          >
            {escalated[a.id] ? '✓ Escalated' : 'Escalate'}
          </button>
        </div>
      ))}

      <div className="grid-2" style={{ marginTop: 0 }}>
        <div className="card">
          <h3>In-Flight Payments (risk-ranked by Monitor Agent)</h3>
          <table>
            <thead>
              <tr><th>TX ID</th><th>Corridor</th><th>Current Step</th><th>Elapsed / SLA</th><th>Risk</th></tr>
            </thead>
            <tbody>
              {inflight.map((p) => {
                const [cls, label] = RISK[p.risk] ?? RISK['on-track'];
                const ratio = Math.min(p.elapsed_min / p.sla_min, 3);
                return (
                  <tr key={p.tx_id}>
                    <td className="num">{p.tx_id}</td>
                    <td className="num">{p.corridor}</td>
                    <td style={{ color: '#8fa1c0' }}>{p.step}</td>
                    <td className="num">
                      {Math.floor(p.elapsed_min / 60) > 0 ? `${Math.floor(p.elapsed_min / 60)}h ${p.elapsed_min % 60}m` : `${p.elapsed_min}m`}
                      <span style={{ color: '#8fa1c0' }}> / {p.sla_min}m</span>
                      <div style={{ height: 4, background: '#22304d', borderRadius: 2, marginTop: 4 }}>
                        <div style={{
                          height: 4, borderRadius: 2,
                          width: `${Math.min(ratio * 33.3, 100)}%`,
                          background: ratio > 1 ? '#f87171' : ratio > 0.75 ? '#fbbf24' : '#34d399',
                        }} />
                      </div>
                    </td>
                    <td><span className={`pill ${cls}`}>{label}</span></td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>

        <div className="card">
          <h3>Corridor Latency Heatmap (per lifecycle step)</h3>
          {hm && (
            <div
              className="heatmap"
              style={{ gridTemplateColumns: `110px repeat(${hm.steps.length}, 1fr)` }}
            >
              <div />
              {hm.steps.map((s) => <div className="hm-head" key={s}>{s}</div>)}
              {hm.rows.map((row) => (
                [
                  <div className="hm-label" key={row.corridor}>{row.corridor}</div>,
                  ...row.cells.map((c, i) => (
                    <div className={`hm-cell ${HM_CLS[c]}`} key={`${row.corridor}-${i}`}>
                      {HM_LABEL[c]}
                    </div>
                  )),
                ]
              ))}
            </div>
          )}
          <div className="footnote">
            Colour = elapsed time vs. SLA benchmark (p95) for the corridor+step. Pattern Agent flags systemic
            issues when multiple payments share a delay at the same correspondent or rail.
          </div>
        </div>
      </div>
    </>
  );
}
