"use client";

import { useState, useEffect, useRef } from 'react';
import { Activity, AlertTriangle, CheckCircle2, Clock, Server } from 'lucide-react';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'https://streamsense-ikg1.onrender.com';
const WS_URL = API_URL.replace(/^http/, 'ws') + '/ws/live';

export default function Dashboard() {
  const [logs, setLogs] = useState([]);
  const [recentAnomalies, setRecentAnomalies] = useState([]);
  const [metrics, setMetrics] = useState({ total_anomalies: 0, anomaly_rate_5min: {} });
  const [services, setServices] = useState([]);
  const [isConnected, setIsConnected] = useState(false);
  const wsRef = useRef(null);

  useEffect(() => {
    const fetchHistory = async () => {
      try {
        const [anomRes, metricsRes, servicesRes] = await Promise.all([
          fetch(`${API_URL}/anomalies?limit=10`),
          fetch(`${API_URL}/metrics`),
          fetch(`${API_URL}/services`)
        ]);
        
        if (anomRes.ok) setRecentAnomalies(await anomRes.json());
        if (metricsRes.ok) setMetrics(await metricsRes.json());
        if (servicesRes.ok) setServices(await servicesRes.json());
      } catch (err) {
        console.error("Failed to fetch history:", err);
      }
    };
    
    fetchHistory();
    const interval = setInterval(fetchHistory, 5000);
    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    const connect = () => {
      const ws = new WebSocket(WS_URL);
      ws.onopen = () => setIsConnected(true);
      ws.onclose = () => {
        setIsConnected(false);
        setTimeout(connect, 3000);
      };
      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          if (data.type === 'log' || data.type === 'anomaly') {
            setLogs(prev => {
              const isDuplicate = prev.some(a => a.timestamp === data.timestamp && a.service === data.service);
              if (isDuplicate) return prev;
              return [data, ...prev].slice(0, 100);
            });
            if (data.is_anomaly || data.level === 'ERROR' || data.level === 'WARN' || data.level === 'WARNING') {
               setRecentAnomalies(prev => {
                 const isDuplicate = prev.some(a => a.timestamp === data.timestamp && a.service === data.service);
                 if (isDuplicate) return prev;
                 return [data, ...prev].slice(0, 10);
               });
            }
          }
        } catch (e) {
          console.error("WS parse error:", e);
        }
      };
      wsRef.current = ws;
    };
    connect();
    return () => wsRef.current?.close();
  }, []);

  const injectAnomaly = async () => {
    try {
      await Promise.all([
        fetch(`${API_URL}/inject/service-a/error-spike`, { method: 'POST' }),
        fetch(`${API_URL}/inject/service-b/error-spike`, { method: 'POST' }),
        fetch(`${API_URL}/inject/service-c/error-spike`, { method: 'POST' })
      ]);
    } catch (e) {
      console.error("Failed to inject", e);
    }
  };

  const formatDate = (isoString) => {
    if (!isoString) return 'N/A';
    try {
      const d = new Date(isoString);
      return d.toLocaleTimeString([], { hour12: false, hour: '2-digit', minute:'2-digit', second:'2-digit' });
    } catch {
      return isoString;
    }
  };

  const formatAgo = (isoString) => {
    if (!isoString) return 'never';
    try {
      const diff = Math.floor((new Date() - new Date(isoString)) / 60000);
      if (diff === 0) return 'just now';
      return `${diff} min ago`;
    } catch {
      return 'unknown';
    }
  };

  const chartData = Object.entries(metrics.anomalies_per_service || {}).map(([key, val]) => ({
    name: key,
    score: val,
    isAnomaly: val > 10 // arbitrarily color it red if it's high
  }));

  const CustomBar = (props) => {
    const { fill, x, y, width, height, payload } = props;
    return <rect x={x} y={y} width={width} height={height} fill={payload.isAnomaly ? '#E24B4A' : 'var(--color-border-secondary)'} rx={2} ry={2} />;
  };

  const getDotClass = (rate) => {
    if (rate >= 80) return "dot-red";
    if (rate > 30) return "dot-amber";
    return "dot-green";
  };

  return (
    <div className="dash">
      <div className="topbar">
        <div className="topbar-left">
          <span className="logo"><Activity size={16} color="var(--color-text-primary)"/> StreamSense</span>
          <span className="badge">live</span>
        </div>
        <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
          <div className="ws-indicator">
            {isConnected ? <div className="ws-dot"></div> : <div className="ws-dot" style={{background: 'var(--color-text-danger)', animation: 'none'}}></div>} 
            WebSocket {isConnected ? 'connected' : 'disconnected'}
          </div>
          <button className="inject-btn" onClick={injectAnomaly}>inject anomaly ↗</button>
        </div>
      </div>

      <div className="metrics">
        <div className="metric">
          <div className="metric-label">total anomalies</div>
          <div className="metric-value danger">{metrics.total_anomalies || 0}</div>
        </div>
        <div className="metric">
          <div className="metric-label">last 5 min</div>
          <div className="metric-value danger">{Object.values(metrics.anomaly_rate_5min || {}).reduce((a,b)=>a+b, 0)}</div>
        </div>
        <div className="metric">
          <div className="metric-label">services monitored</div>
          <div className="metric-value">{services.length || 3}</div>
        </div>
        <div className="metric">
          <div className="metric-label">model thresholds</div>
          <div className="metric-value" style={{fontSize: '14px', textAlign: 'right', display: 'flex', flexDirection: 'column', gap: '2px', marginTop: '4px'}}>
            {metrics.thresholds ? Object.entries(metrics.thresholds).map(([k,v]) => (
              <span key={k} style={{color: 'var(--color-text-secondary)'}}>
                {k}: <span style={{color: 'var(--color-text-primary)'}}>{v}</span>
              </span>
            )) : "Loading..."}
          </div>
        </div>
      </div>

      <div className="grid2">
        <div className="card">
          <div className="card-title">service status</div>
          {services.map(svc => (
            <div key={svc.service} className="svc-row">
              <div>
                <span className={`dot ${getDotClass(svc.anomaly_rate)}`}></span>
                <span className="svc-name">{svc.service}</span>
              </div>
              <div style={{ textAlign: 'right' }}>
                <div className="svc-meta">{svc.anomaly_rate} anomalies / 5min</div>
                <div className="svc-score">last: {formatAgo(svc.last_anomaly)}</div>
              </div>
            </div>
          ))}
        </div>

        <div className="card">
          <div className="card-title">anomalies per service</div>
          <div className="chart-area" style={{ height: '120px', marginTop: '16px' }}>
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={chartData} margin={{ top: 0, right: 0, left: 0, bottom: 0 }}>
                <XAxis dataKey="name" stroke="var(--color-text-secondary)" tick={{ fill: 'var(--color-text-secondary)', fontSize: 11 }} tickLine={false} axisLine={false} />
                <Tooltip cursor={{ fill: 'rgba(255, 255, 255, 0.05)' }} contentStyle={{ backgroundColor: 'var(--color-background-primary)', border: '1px solid var(--color-border-secondary)', color: 'var(--color-text-primary)' }} />
                <Bar dataKey="score" shape={<CustomBar />} isAnimationActive={false} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>

      <div className="grid2">
        <div className="card">
          <div className="card-title">live log feed</div>
          <div className="log-feed">
            {logs.map((log, idx) => {
              const isAnom = log.is_anomaly;
              const rowClass = (isAnom || log.level === "ERROR") ? "log-row anomaly" : (log.level === "WARNING" || log.level === "WARN") ? "log-row warning" : "log-row normal";
              return (
                <div key={idx} className={rowClass}>
                  <span className="log-time">{formatDate(log.timestamp)}</span>
                  <span className="log-svc">{log.service}</span>
                  <span className="log-msg" title={log.message}>{log.message}</span>
                  {isAnom && <span className="score-badge">{log.anomaly_score?.toFixed(3)}</span>}
                </div>
              );
            })}
            {logs.length === 0 && <div className="log-row normal"><span className="log-msg">Waiting for logs...</span></div>}
          </div>
        </div>

        <div className="card">
          <div className="card-title">recent anomalies</div>
          <div className="alert-list">
            {recentAnomalies.map((anom, idx) => (
              <div key={idx} className="alert-item" style={{ borderLeftColor: (anom.level === "WARNING" || anom.level === "WARN") ? "#BA7517" : "#E24B4A", background: (anom.level === "WARNING" || anom.level === "WARN") ? "var(--color-background-warning)" : "var(--color-background-danger)" }}>
                <div className="alert-header">
                  <span className="alert-svc" style={{ color: (anom.level === "WARNING" || anom.level === "WARN") ? "var(--color-text-warning)" : "var(--color-text-danger)" }}>{anom.service}</span>
                  <span className="alert-time">{formatAgo(anom.timestamp)}</span>
                </div>
                <div className="alert-msg" title={anom.message}>{anom.message}</div>
                <div className="alert-score" style={{ color: (anom.level === "WARNING" || anom.level === "WARN") ? "var(--color-text-warning)" : "var(--color-text-danger)" }}>
                  score: {anom.anomaly_score?.toFixed(3)} · {anom.level.toLowerCase()}
                </div>
              </div>
            ))}
            {recentAnomalies.length === 0 && <div className="alert-item" style={{background: 'transparent', borderLeft: 'none', color: 'var(--color-text-secondary)'}}>No recent anomalies.</div>}
          </div>
        </div>
      </div>
    </div>
  );
}
