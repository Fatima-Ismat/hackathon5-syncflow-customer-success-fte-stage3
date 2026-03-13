import SupportForm from '@/components/SupportForm';

export const metadata = {
  title: 'Submit a Request – SyncFlow Support',
};

export default function SupportPage() {
  return (
    <div className="max-w-2xl mx-auto px-4 sm:px-6 py-12">
      {/* Page header */}
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-slate-900 dark:text-slate-100 mb-2">Submit a Support Request</h1>
        <p className="text-slate-500 dark:text-slate-400 text-sm">
          Our AI agent will review your request and respond instantly. Complex issues are
          automatically escalated to the right specialist team.
        </p>
      </div>

      {/* Channel badges */}
      <div className="flex gap-2 mb-8">
        {[
          { label: 'AI-Powered', color: 'brand' },
          { label: 'Instant Response', color: 'emerald' },
          { label: 'SLA Guaranteed', color: 'slate' },
        ].map(({ label, color }) => (
          <span
            key={label}
            className={`text-xs font-medium px-2.5 py-1 rounded-full border ${
              color === 'brand'
                ? 'bg-brand-50 dark:bg-brand-900/30 text-brand-700 dark:text-brand-300 border-brand-100 dark:border-brand-800'
                : color === 'emerald'
                ? 'bg-emerald-50 dark:bg-emerald-900/30 text-emerald-700 dark:text-emerald-300 border-emerald-100 dark:border-emerald-800'
                : 'bg-slate-100 dark:bg-slate-700 text-slate-600 dark:text-slate-300 border-slate-200 dark:border-slate-600'
            }`}
          >
            {label}
          </span>
        ))}
      </div>

      {/* Form card */}
      <div className="card p-6 sm:p-8">
        <SupportForm />
      </div>

      {/* SLA info */}
      <div className="mt-6 rounded-xl bg-slate-100 dark:bg-slate-800 p-4 border border-transparent dark:border-slate-700">
        <p className="text-xs font-semibold text-slate-700 dark:text-slate-300 mb-2">Response SLA by Plan</p>
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
          {[
            { plan: 'Starter',    sla: '24h' },
            { plan: 'Growth',     sla: '8h'  },
            { plan: 'Business',   sla: '2h'  },
            { plan: 'Enterprise', sla: '1h'  },
          ].map(({ plan, sla }) => (
            <div key={plan} className="bg-white dark:bg-slate-700 rounded-lg px-3 py-2 text-center border border-slate-200 dark:border-slate-600">
              <div className="text-xs text-slate-500 dark:text-slate-400">{plan}</div>
              <div className="text-sm font-bold text-brand-600 dark:text-brand-400">{sla}</div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
