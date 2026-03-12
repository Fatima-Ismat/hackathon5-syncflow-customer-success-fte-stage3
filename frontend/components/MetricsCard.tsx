'use client';

// ---------------------------------------------------------------------------
// Stat Card
// ---------------------------------------------------------------------------

export function StatCard({
  title,
  value,
  subtitle,
  color = 'slate',
  icon,
}: {
  title: string;
  value: string | number;
  subtitle?: string;
  color?: 'brand' | 'emerald' | 'amber' | 'red' | 'slate';
  icon?: React.ReactNode;
}) {
  const colorMap = {
    brand:   'text-brand-600   bg-brand-50   border-brand-100',
    emerald: 'text-emerald-600 bg-emerald-50 border-emerald-100',
    amber:   'text-amber-600   bg-amber-50   border-amber-100',
    red:     'text-red-600     bg-red-50     border-red-100',
    slate:   'text-slate-600   bg-slate-100  border-slate-200',
  };

  return (
    <div className="card p-5">
      <div className="flex items-start justify-between">
        <div>
          <p className="text-sm text-slate-500 font-medium">{title}</p>
          <p className="text-3xl font-bold text-slate-900 mt-1">{value}</p>
          {subtitle && (
            <p className="text-xs text-slate-400 mt-1">{subtitle}</p>
          )}
        </div>
        {icon && (
          <div className={`w-10 h-10 rounded-xl flex items-center justify-center
                          border ${colorMap[color]}`}>
            {icon}
          </div>
        )}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Bar Chart (simple CSS-based)
// ---------------------------------------------------------------------------

export function BarChart({
  title,
  data,
}: {
  title: string;
  data: { label: string; value: number; color?: string }[];
}) {
  const max = Math.max(...data.map((d) => d.value), 1);

  return (
    <div className="card p-5">
      <h3 className="text-sm font-semibold text-slate-700 mb-4">{title}</h3>
      <div className="space-y-3">
        {data.map(({ label, value, color = 'bg-brand-500' }) => (
          <div key={label}>
            <div className="flex items-center justify-between mb-1">
              <span className="text-xs text-slate-600 capitalize">{label.replace(/_/g, ' ')}</span>
              <span className="text-xs font-semibold text-slate-700">{value}</span>
            </div>
            <div className="h-2 rounded-full bg-slate-100 overflow-hidden">
              <div
                className={`h-full rounded-full ${color} transition-all duration-500`}
                style={{ width: `${(value / max) * 100}%` }}
              />
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Quality Metric (with percentage ring)
// ---------------------------------------------------------------------------

export function QualityRing({
  label,
  pct,
  color = 'brand',
}: {
  label: string;
  pct: number | null;
  color?: 'brand' | 'emerald' | 'amber' | 'red';
}) {
  const colorClass = {
    brand:   'text-brand-600',
    emerald: 'text-emerald-600',
    amber:   'text-amber-600',
    red:     'text-red-600',
  }[color];

  const display = pct === null ? '—' : `${Math.round(pct * 100)}%`;

  return (
    <div className="flex flex-col items-center gap-1.5">
      <div className={`text-2xl font-bold ${colorClass}`}>{display}</div>
      <div className="text-xs text-slate-500 text-center">{label}</div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Escalation Reason Table
// ---------------------------------------------------------------------------

export function EscalationTable({
  data,
}: {
  data: Record<string, number>;
}) {
  const entries = Object.entries(data).sort((a, b) => b[1] - a[1]);

  if (!entries.length) {
    return (
      <div className="card p-5">
        <h3 className="text-sm font-semibold text-slate-700 mb-3">Escalation Breakdown</h3>
        <p className="text-sm text-slate-400">No escalations in this window.</p>
      </div>
    );
  }

  return (
    <div className="card p-5">
      <h3 className="text-sm font-semibold text-slate-700 mb-3">Escalation Breakdown</h3>
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-slate-100">
            <th className="text-left text-xs text-slate-400 font-medium pb-2">Reason</th>
            <th className="text-right text-xs text-slate-400 font-medium pb-2">Count</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-50">
          {entries.map(([reason, count]) => (
            <tr key={reason}>
              <td className="py-2 text-slate-600 capitalize">
                {reason.replace(/_/g, ' ')}
              </td>
              <td className="py-2 text-right font-semibold text-slate-800">{count}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Status Distribution
// ---------------------------------------------------------------------------

export function StatusDistribution({
  open,
  inProgress,
  escalated,
  resolved,
  total,
}: {
  open: number;
  inProgress: number;
  escalated: number;
  resolved: number;
  total: number;
}) {
  const bars = [
    { label: 'Open',        count: open,       color: 'bg-blue-400'    },
    { label: 'In Progress', count: inProgress,  color: 'bg-brand-500'   },
    { label: 'Escalated',   count: escalated,   color: 'bg-red-500'     },
    { label: 'Resolved',    count: resolved,    color: 'bg-emerald-500' },
  ];

  return (
    <div className="card p-5">
      <h3 className="text-sm font-semibold text-slate-700 mb-4">Ticket Distribution</h3>
      {total === 0 ? (
        <p className="text-sm text-slate-400">No tickets yet. Submit a support request to get started.</p>
      ) : (
        <>
          {/* Stacked bar */}
          <div className="flex h-3 rounded-full overflow-hidden mb-4 bg-slate-100">
            {bars.map(({ label, count, color }) =>
              count > 0 ? (
                <div
                  key={label}
                  className={`${color} transition-all`}
                  style={{ width: `${(count / total) * 100}%` }}
                  title={`${label}: ${count}`}
                />
              ) : null,
            )}
          </div>
          {/* Legend */}
          <div className="grid grid-cols-2 gap-2">
            {bars.map(({ label, count, color }) => (
              <div key={label} className="flex items-center gap-2">
                <span className={`w-2.5 h-2.5 rounded-full ${color} flex-shrink-0`} />
                <span className="text-xs text-slate-600">{label}</span>
                <span className="text-xs font-semibold text-slate-800 ml-auto">{count}</span>
              </div>
            ))}
          </div>
        </>
      )}
    </div>
  );
}
