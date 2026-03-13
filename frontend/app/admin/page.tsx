'use client';

import { useEffect, useState, useCallback } from 'react';
import {
  getMetricsSummary, getChannelBreakdown, listTickets, checkHealth,
  type MetricsSummary, type ChannelBreakdown, type Ticket,
} from '@/lib/api';
import {
  StatCard, BarChart, QualityRing, EscalationTable, StatusDistribution,
} from '@/components/MetricsCard';

type LoadState = 'loading' | 'loaded' | 'error';

const WINDOWS = [
  { label: '1h',  hours: 1  },
  { label: '24h', hours: 24 },
  { label: '7d',  hours: 168 },
];

export default function AdminDashboard() {
  const [window, setWindow]             = useState(24);
  const [loadState, setLoadState]       = useState<LoadState>('loading');
  const [apiOnline, setApiOnline]       = useState<boolean | null>(null);
  const [metrics, setMetrics]           = useState<MetricsSummary | null>(null);
  const [channels, setChannels]         = useState<ChannelBreakdown | null>(null);
  const [tickets, setTickets]           = useState<Ticket[]>([]);
  const [lastRefresh, setLastRefresh]   = useState<Date | null>(null);
  const [errorMsg, setErrorMsg]         = useState('');

  const load = useCallback(async (hrs: number) => {
    setLoadState('loading');
    setErrorMsg('');

    const healthy = await checkHealth();
    setApiOnline(healthy);

    if (!healthy) {
      setLoadState('error');
      setErrorMsg('Cannot reach the FastAPI backend. Start it with: uvicorn api.main:app --reload --port 8000');
      return;
    }

    try {
      const [metricsRes, channelsRes, ticketsRes] = await Promise.all([
        getMetricsSummary(hrs),
        getChannelBreakdown(hrs),
        listTickets({ limit: 200 }),
      ]);

      setMetrics(metricsRes.data);
      setChannels(channelsRes.data);
      setTickets(ticketsRes.data?.tickets ?? []);
      setLastRefresh(new Date());
      setLoadState('loaded');
    } catch (err) {
      setErrorMsg(err instanceof Error ? err.message : 'Failed to load dashboard data.');
      setLoadState('error');
    }
  }, []);

  useEffect(() => { load(window); }, [window, load]);

  // Auto-refresh every 30 seconds
  useEffect(() => {
    const interval = setInterval(() => load(window), 30_000);
    return () => clearInterval(interval);
  }, [window, load]);

  // Derived ticket counts
  const ticketCounts = {
    open:       tickets.filter((t) => t.status === 'open').length,
    inProgress: tickets.filter((t) => t.status === 'in_progress').length,
    escalated:  tickets.filter((t) => t.status === 'escalated').length,
    resolved:   tickets.filter((t) => t.status === 'resolved').length,
    total:      tickets.length,
  };

  return (
    <div className="max-w-6xl mx-auto px-4 sm:px-6 py-10">
      {/* Page header */}
      <div className="flex items-start justify-between mb-8 flex-wrap gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 dark:text-slate-100 mb-1">Admin Dashboard</h1>
          <p className="text-slate-500 dark:text-slate-400 text-sm">
            Real-time AI agent performance and ticket analytics.
          </p>
        </div>

        <div className="flex items-center gap-3">
          {/* API status indicator */}
          <div className="flex items-center gap-1.5 text-xs text-slate-500 dark:text-slate-400">
            <span className={`inline-block w-2 h-2 rounded-full ${
              apiOnline === null ? 'bg-slate-300 animate-pulse' :
              apiOnline           ? 'bg-emerald-400' : 'bg-red-400'
            }`} />
            API {apiOnline === null ? '…' : apiOnline ? 'Online' : 'Offline'}
          </div>

          {/* Window selector */}
          <div className="flex rounded-lg border border-slate-200 dark:border-slate-600 overflow-hidden bg-white dark:bg-slate-800">
            {WINDOWS.map(({ label, hours }) => (
              <button
                key={hours}
                onClick={() => setWindow(hours)}
                className={`px-3 py-1.5 text-xs font-medium transition-colors ${
                  window === hours
                    ? 'bg-brand-600 text-white'
                    : 'text-slate-600 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-slate-700'
                }`}
              >
                {label}
              </button>
            ))}
          </div>

          {/* Refresh button */}
          <button
            onClick={() => load(window)}
            disabled={loadState === 'loading'}
            className="btn-secondary py-1.5 px-3 text-xs"
          >
            <svg className={`w-3.5 h-3.5 ${loadState === 'loading' ? 'animate-spin' : ''}`}
                 fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
              <path strokeLinecap="round" strokeLinejoin="round"
                    d="M16.023 9.348h4.992v-.001M2.985 19.644v-4.992m0 0h4.992m-4.993
                       0l3.181 3.183a8.25 8.25 0 0013.803-3.7M4.031 9.865a8.25 8.25
                       0 0113.803-3.7l3.181 3.182m0-4.991v4.99" />
            </svg>
            Refresh
          </button>
        </div>
      </div>

      {/* Last refresh */}
      {lastRefresh && (
        <p className="text-xs text-slate-400 dark:text-slate-500 mb-6">
          Last updated: {lastRefresh.toLocaleTimeString()} — auto-refreshes every 30s
        </p>
      )}

      {/* Error state */}
      {loadState === 'error' && (
        <div className="card border-red-200 dark:border-red-900 dark:bg-red-950/20 p-6 mb-6">
          <div className="flex gap-3 items-start">
            <svg className="w-5 h-5 text-red-500 flex-shrink-0 mt-0.5" fill="none"
                 viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round"
                    d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73
                       0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898
                       0L2.697 16.126zM12 15.75h.008v.008H12v-.008z" />
            </svg>
            <div>
              <p className="text-sm font-semibold text-red-800 dark:text-red-300">Dashboard unavailable</p>
              <p className="text-sm text-red-700 dark:text-red-400 mt-1">{errorMsg}</p>
            </div>
          </div>
        </div>
      )}

      {/* Loading skeleton */}
      {loadState === 'loading' && !metrics && (
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 mb-6 animate-pulse">
          {[...Array(4)].map((_, i) => (
            <div key={i} className="card p-5 h-24 bg-slate-100 dark:bg-slate-700" />
          ))}
        </div>
      )}

      {/* ── Volume Stats ─────────────────────────────────────────────────── */}
      {metrics && (
        <>
          <section className="mb-6">
            <h2 className="text-xs font-semibold text-slate-400 dark:text-slate-500 uppercase tracking-widest mb-3">
              Ticket Volume — Last {WINDOWS.find((w) => w.hours === window)?.label}
            </h2>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
              <StatCard
                title="Total Tickets"
                value={ticketCounts.total || metrics.volume.tickets_created}
                subtitle={`${metrics.volume.responses_generated} AI responses`}
                color="brand"
                icon={
                  <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24"
                       stroke="currentColor" strokeWidth={1.8}>
                    <path strokeLinecap="round" strokeLinejoin="round"
                          d="M16.5 6v.75m0 3v.75m0 3v.75m0 3V18m-9-5.25h5.25M7.5 15h3M3.375
                             5.25c-.621 0-1.125.504-1.125 1.125v3.026a2.999 2.999 0 010
                             5.198v3.031c0 .621.504 1.125 1.125 1.125h17.25c.621 0
                             1.125-.504 1.125-1.125v-3.03a3 3 0 010-5.2V6.375c0-.621-.504-1.125-1.125-1.125H3.375z" />
                  </svg>
                }
              />
              <StatCard
                title="Open Tickets"
                value={ticketCounts.open + ticketCounts.inProgress}
                subtitle={`${ticketCounts.inProgress} in progress`}
                color="amber"
                icon={
                  <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24"
                       stroke="currentColor" strokeWidth={1.8}>
                    <path strokeLinecap="round" strokeLinejoin="round"
                          d="M12 6v6h4.5m4.5 0a9 9 0 11-18 0 9 9 0 0118 0z" />
                  </svg>
                }
              />
              <StatCard
                title="Escalated"
                value={ticketCounts.escalated || metrics.volume.escalations}
                subtitle={metrics.quality.escalation_rate !== null
                  ? `${Math.round(metrics.quality.escalation_rate * 100)}% escalation rate`
                  : undefined}
                color="red"
                icon={
                  <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24"
                       stroke="currentColor" strokeWidth={1.8}>
                    <path strokeLinecap="round" strokeLinejoin="round"
                          d="M15 11.25l-3-3m0 0l-3 3m3-3v7.5M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                  </svg>
                }
              />
              <StatCard
                title="Resolved"
                value={ticketCounts.resolved || metrics.volume.resolutions}
                subtitle={metrics.quality.auto_resolution_rate !== null
                  ? `${Math.round(metrics.quality.auto_resolution_rate * 100)}% auto-resolved`
                  : undefined}
                color="emerald"
                icon={
                  <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24"
                       stroke="currentColor" strokeWidth={1.8}>
                    <path strokeLinecap="round" strokeLinejoin="round"
                          d="M9 12.75L11.25 15 15 9.75M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                  </svg>
                }
              />
            </div>
          </section>

          {/* ── Quality Metrics ─────────────────────────────────────────── */}
          <section className="mb-6">
            <h2 className="text-xs font-semibold text-slate-400 dark:text-slate-500 uppercase tracking-widest mb-3">
              AI Agent Quality
            </h2>
            <div className="card p-6">
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-6 divide-x divide-slate-100 dark:divide-slate-700">
                <QualityRing
                  label="Auto-Resolution Rate"
                  pct={metrics.quality.auto_resolution_rate}
                  color="emerald"
                />
                <div className="pl-6">
                  <QualityRing
                    label="KB Usage Rate"
                    pct={metrics.quality.kb_usage_rate}
                    color="brand"
                  />
                </div>
                <div className="pl-6">
                  <QualityRing
                    label="Avg Confidence"
                    pct={metrics.quality.avg_agent_confidence}
                    color="brand"
                  />
                </div>
                <div className="pl-6">
                  <div className="flex flex-col items-center gap-1.5">
                    <div className="text-2xl font-bold text-slate-700 dark:text-slate-300">
                      {metrics.quality.avg_resolution_time_s !== null
                        ? formatDuration(metrics.quality.avg_resolution_time_s)
                        : '—'}
                    </div>
                    <div className="text-xs text-slate-500 dark:text-slate-400 text-center">Avg Resolution Time</div>
                  </div>
                </div>
              </div>

              {/* SLA breaches */}
              {metrics.volume.sla_breaches > 0 && (
                <div className="mt-5 pt-4 border-t border-slate-100 dark:border-slate-700">
                  <p className="text-xs text-red-600 dark:text-red-400 font-medium flex items-center gap-1.5">
                    <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24"
                         stroke="currentColor" strokeWidth={2}>
                      <path strokeLinecap="round" strokeLinejoin="round"
                            d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948
                               3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949
                               3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126zM12
                               15.75h.008v.008H12v-.008z" />
                    </svg>
                    {metrics.volume.sla_breaches} SLA {metrics.volume.sla_breaches === 1 ? 'breach' : 'breaches'} in this window
                  </p>
                </div>
              )}
            </div>
          </section>

          {/* ── Charts Row ──────────────────────────────────────────────── */}
          <div className="grid sm:grid-cols-2 gap-5 mb-6">
            <StatusDistribution
              open={ticketCounts.open}
              inProgress={ticketCounts.inProgress}
              escalated={ticketCounts.escalated}
              resolved={ticketCounts.resolved}
              total={ticketCounts.total}
            />
            {channels && (
              <BarChart
                title="Channel Volume"
                data={[
                  { label: 'Email',     value: channels.channels.email?.tickets     ?? 0, color: 'bg-brand-500'   },
                  { label: 'WhatsApp',  value: channels.channels.whatsapp?.tickets  ?? 0, color: 'bg-emerald-500' },
                  { label: 'Web Form',  value: channels.channels.web_form?.tickets  ?? 0, color: 'bg-amber-400'   },
                ]}
              />
            )}
          </div>

          {/* ── Escalation & Recent Tickets ─────────────────────────────── */}
          <div className="grid sm:grid-cols-2 gap-5">
            <EscalationTable data={metrics.escalation_reasons} />

            {/* Recent escalated tickets */}
            <div className="card p-5">
              <h3 className="text-sm font-semibold text-slate-700 dark:text-slate-200 mb-3">
                Recent Escalations
              </h3>
              {tickets.filter((t) => t.status === 'escalated').length === 0 ? (
                <p className="text-sm text-slate-400 dark:text-slate-500">No escalated tickets.</p>
              ) : (
                <div className="space-y-2">
                  {tickets
                    .filter((t) => t.status === 'escalated')
                    .slice(0, 5)
                    .map((t) => (
                      <div key={t.ticket_ref}
                           className="flex items-start justify-between gap-2 py-2 border-b
                                      border-slate-50 dark:border-slate-700 last:border-0">
                        <div className="min-w-0">
                          <p className="text-xs font-mono text-slate-500 dark:text-slate-400">{t.ticket_ref}</p>
                          <p className="text-xs text-slate-700 dark:text-slate-300 truncate mt-0.5">
                            {t.escalation_queue?.replace(/-/g, ' ') ?? 'unknown queue'}
                          </p>
                        </div>
                        <span className={`text-xs font-semibold flex-shrink-0 ${
                          t.priority === 'critical' ? 'text-red-600 dark:text-red-400'    :
                          t.priority === 'high'     ? 'text-orange-600 dark:text-orange-400' :
                          t.priority === 'medium'   ? 'text-amber-600 dark:text-amber-400'  : 'text-slate-500 dark:text-slate-400'
                        }`}>
                          {t.priority}
                        </span>
                      </div>
                    ))}
                </div>
              )}
            </div>
          </div>
        </>
      )}
    </div>
  );
}

function formatDuration(seconds: number): string {
  if (seconds < 60)    return `${Math.round(seconds)}s`;
  if (seconds < 3600)  return `${Math.round(seconds / 60)}m`;
  if (seconds < 86400) return `${Math.round(seconds / 3600)}h`;
  return `${Math.round(seconds / 86400)}d`;
}
