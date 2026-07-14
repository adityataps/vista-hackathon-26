import { useEffect, useState } from 'react';
import OperationsDashboard from './views/OperationsDashboard.jsx';
import ExceptionQueue from './views/ExceptionQueue.jsx';
import BottleneckMonitor from './views/BottleneckMonitor.jsx';
import { probeBackend, getExceptions, getAlerts } from './api/client.js';

const TABS = [
  { id: 'dashboard', label: 'Operations Dashboard' },
  { id: 'exceptions', label: 'Exception Queue' },
  { id: 'monitor', label: 'Bottleneck Monitor' },
];

export default function App() {
  const [tab, setTab] = useState('dashboard');
  const [backendLive, setBackendLive] = useState(null);
  const [openExceptions, setOpenExceptions] = useState(0);
  const [alertCount, setAlertCount] = useState(0);

  useEffect(() => {
    probeBackend().then(setBackendLive);
    getExceptions().then(({ data }) =>
      setOpenExceptions(data.filter((e) => e.status === 'pending').length)
    );
    getAlerts().then(({ data }) => setAlertCount(data.length));
  }, []);

  return (
    <div className="app">
      <header className="header">
        <div className="brand">
          <div className="brand-logo">⚡</div>
          <div>
            PayInvestigator
            <small>AI Payment Exception Investigation · Global PAYplus layer</small>
          </div>
        </div>
        <nav className="tabs">
          {TABS.map((t) => (
            <button
              key={t.id}
              className={`tab ${tab === t.id ? 'active' : ''}`}
              onClick={() => setTab(t.id)}
            >
              {t.label}
              {t.id === 'exceptions' && openExceptions > 0 && (
                <span className="badge">{openExceptions}</span>
              )}
              {t.id === 'monitor' && alertCount > 0 && (
                <span className="badge">{alertCount}</span>
              )}
            </button>
          ))}
        </nav>
        <div className="conn" title="Backend connectivity">
          <span className={`dot ${backendLive ? 'live' : 'mock'}`} />
          {backendLive === null ? 'Connecting…' : backendLive ? 'Backend live' : 'Demo mode (mock data)'}
        </div>
      </header>

      <main className="main">
        {tab === 'dashboard' && <OperationsDashboard />}
        {tab === 'exceptions' && <ExceptionQueue />}
        {tab === 'monitor' && <BottleneckMonitor />}
      </main>
    </div>
  );
}
