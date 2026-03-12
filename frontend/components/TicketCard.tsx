'use client';

import type { Ticket } from '@/lib/api';

// ---------------------------------------------------------------------------
// Status config
// ---------------------------------------------------------------------------

const STATUS_CONFIG: Record<string, { label: string; bg: string; text: string; dot: string }> = {
  open:             { label: 'Open',             bg: 'bg-blue-50',   text: 'text-blue-700',   dot: 'bg-blue-500'   },
  in_progress:      { label: 'In Progress',      bg: 'bg-brand-50',  text: 'text-brand-700',  dot: 'bg-brand-500'  },
  waiting_customer: { label: 'Awaiting You',     bg: 'bg-amber-50',  text: 'text-amber-700',  dot: 'bg-amber-500'  },
  escalated:        { label: 'Escalated',        bg: 'bg-red-50',    text: 'text-red-700',    dot: 'bg-red-500'    },
  resolved:         { label: 'Resolved',         bg: 'bg-emerald-50',text: 'text-emerald-700',dot: 'bg-emerald-500'},
};

const PRIORITY_CONFIG: Record<string, { label: string; color: string }> = {
  critical: { label: 'Critical', color: 'text-red-600'    },
  high:     { label: 'High',     color: 'text-orange-600' },
  medium:   { label: 'Medium',   color: 'text-amber-600'  },
  low:      { label: 'Low',      color: 'text-slate-500'  },
};

// ---------------------------------------------------------------------------
// TicketCard
// ---------------------------------------------------------------------------

export default function TicketCard({ ticket }: { ticket: Ticket }) {
  const status   = STATUS_CONFIG[ticket.status]   ?? STATUS_CONFIG['open'];
  const priority = PRIORITY_CONFIG[ticket.priority] ?? PRIORITY_CONFIG['medium'];

  const created  = new Date(ticket.created_at);
  const deadline = new Date(ticket.sla_deadline);
  const now      = new Date();
  const isBreached = ticket.sla_breached || (ticket.status !== 'resolved' && now > deadline);

  return (
    <div className="card divide-y divide-slate-100">
      {/* Header */}
      <div className="p-5 flex items-start justify-between gap-4">
        <div className="min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <span className="font-mono text-xs font-semibold text-slate-500 tracking-wide uppercase">
              {ticket.ticket_ref}
            </span>
            <span className={`inline-flex items-center gap-1.5 text-xs font-semibold px-2 py-0.5
                              rounded-full ${status.bg} ${status.text}`}>
              <span className={`w-1.5 h-1.5 rounded-full ${status.dot}`} />
              {status.label}
            </span>
          </div>
          <p className="text-sm font-medium text-slate-800 leading-snug">
            {ticket.issue_summary || 'No summary available'}
          </p>
        </div>
        <span className={`text-sm font-semibold flex-shrink-0 ${priority.color}`}>
          {priority.label}
        </span>
      </div>

      {/* Metadata grid */}
      <div className="px-5 py-4 grid grid-cols-2 sm:grid-cols-3 gap-4">
        <InfoItem label="Channel"    value={formatChannel(ticket.channel)} />
        <InfoItem label="Opened"     value={created.toLocaleDateString()} />
        <InfoItem label="Assigned To" value={formatAssignee(ticket.assigned_to)} />
        {ticket.topic && (
          <InfoItem label="Topic" value={ticket.topic.replace(/_/g, ' ')} />
        )}
        {ticket.sentiment_at_open && (
          <InfoItem label="Sentiment" value={ticket.sentiment_at_open} />
        )}
        {ticket.agent_confidence !== null && ticket.agent_confidence !== undefined && (
          <InfoItem
            label="AI Confidence"
            value={`${Math.round(ticket.agent_confidence * 100)}%`}
          />
        )}
      </div>

      {/* SLA bar */}
      <div className="px-5 py-4">
        <div className="flex items-center justify-between mb-2">
          <span className="text-xs font-medium text-slate-600">SLA Deadline</span>
          <span className={`text-xs font-semibold ${isBreached ? 'text-red-600' : 'text-slate-600'}`}>
            {deadline.toLocaleString()}
          </span>
        </div>
        <SLABar
          created={created}
          deadline={deadline}
          resolved={ticket.resolved_at ? new Date(ticket.resolved_at) : null}
          breached={isBreached}
        />
        {isBreached && (
          <p className="text-xs text-red-600 mt-2 font-medium">SLA deadline has been exceeded.</p>
        )}
      </div>

      {/* Escalation info */}
      {ticket.status === 'escalated' && ticket.escalation_queue && (
        <div className="px-5 py-4 bg-red-50 rounded-b-xl">
          <p className="text-xs font-semibold text-red-700 mb-1">Escalated to Specialist</p>
          <div className="flex items-center gap-4">
            <InfoItem label="Queue"  value={ticket.escalation_queue.replace(/-/g, ' ')} />
            {ticket.escalation_reason && (
              <InfoItem label="Reason" value={ticket.escalation_reason.replace(/_/g, ' ')} />
            )}
          </div>
        </div>
      )}

      {/* Resolution info */}
      {ticket.status === 'resolved' && ticket.resolution_time_s !== null && (
        <div className="px-5 py-4 bg-emerald-50 rounded-b-xl">
          <p className="text-xs font-semibold text-emerald-700">
            Resolved in {formatDuration(ticket.resolution_time_s)}
            {ticket.resolved_at && ` — ${new Date(ticket.resolved_at).toLocaleString()}`}
          </p>
        </div>
      )}

      {/* Tags */}
      {ticket.tags && ticket.tags.length > 0 && (
        <div className="px-5 py-3 flex flex-wrap gap-1.5">
          {ticket.tags.map((tag) => (
            <span key={tag}
                  className="text-xs bg-slate-100 text-slate-600 px-2 py-0.5 rounded-full border
                             border-slate-200">
              {tag}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// SLA Progress Bar
// ---------------------------------------------------------------------------

function SLABar({
  created, deadline, resolved, breached,
}: {
  created: Date;
  deadline: Date;
  resolved: Date | null;
  breached: boolean;
}) {
  const total    = deadline.getTime() - created.getTime();
  const elapsed  = (resolved ?? new Date()).getTime() - created.getTime();
  const pct      = Math.min(Math.round((elapsed / total) * 100), 100);
  const barColor = breached  ? 'bg-red-500' :
                   pct > 80  ? 'bg-orange-400' :
                   pct > 60  ? 'bg-amber-400' : 'bg-emerald-500';

  return (
    <div className="h-1.5 rounded-full bg-slate-100 overflow-hidden">
      <div
        className={`h-full rounded-full transition-all ${barColor}`}
        style={{ width: `${pct}%` }}
      />
    </div>
  );
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function InfoItem({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="text-xs text-slate-400 mb-0.5">{label}</dt>
      <dd className="text-sm font-medium text-slate-700 capitalize">{value}</dd>
    </div>
  );
}

function formatChannel(ch: string): string {
  const map: Record<string, string> = {
    email: 'Email', whatsapp: 'WhatsApp', web_form: 'Web Form',
  };
  return map[ch] ?? ch;
}

function formatAssignee(a: string): string {
  if (a === 'ai_agent')         return 'AI Agent';
  if (a.startsWith('queue:'))   return a.replace('queue:', '').replace(/-/g, ' ');
  if (a.startsWith('human:'))   return a.replace('human:', '');
  return a;
}

function formatDuration(seconds: number): string {
  if (seconds < 60)     return `${seconds}s`;
  if (seconds < 3600)   return `${Math.round(seconds / 60)}m`;
  if (seconds < 86400)  return `${Math.round(seconds / 3600)}h`;
  return `${Math.round(seconds / 86400)}d`;
}
