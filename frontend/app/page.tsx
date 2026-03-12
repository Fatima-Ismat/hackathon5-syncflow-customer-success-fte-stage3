import Link from 'next/link';

export default function HomePage() {
  return (
    <div className="max-w-6xl mx-auto px-4 sm:px-6 py-20">
      {/* Hero */}
      <div className="text-center mb-16">
        <div className="inline-flex items-center gap-2 bg-brand-50 text-brand-700 text-xs font-semibold
                        px-3 py-1.5 rounded-full mb-6 border border-brand-100">
          <span className="inline-block w-1.5 h-1.5 rounded-full bg-brand-500 animate-pulse" />
          AI-Powered Customer Success
        </div>
        <h1 className="text-4xl sm:text-5xl font-bold text-slate-900 mb-5 tracking-tight">
          SyncFlow Support Center
        </h1>
        <p className="text-lg text-slate-500 max-w-xl mx-auto leading-relaxed">
          Get instant help from our AI Digital FTE. Submit a support request,
          track your tickets, or browse our knowledge base.
        </p>
      </div>

      {/* Cards */}
      <div className="grid sm:grid-cols-3 gap-5 max-w-3xl mx-auto">
        <ActionCard
          href="/support"
          icon={
            <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}>
              <path strokeLinecap="round" strokeLinejoin="round"
                    d="M16.862 4.487l1.687-1.688a1.875 1.875 0 112.652 2.652L10.582
                       16.07a4.5 4.5 0 01-1.897 1.13L6 18l.8-2.685a4.5 4.5 0
                       011.13-1.897l8.932-8.931zm0 0L19.5 7.125M18 14v4.75A2.25
                       2.25 0 0115.75 21H5.25A2.25 2.25 0 013 18.75V8.25A2.25
                       2.25 0 015.25 6H10" />
            </svg>
          }
          title="Submit a Request"
          description="Describe your issue and get an AI response in seconds."
          cta="Get Help"
          color="brand"
        />
        <ActionCard
          href="/ticket-status"
          icon={
            <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}>
              <path strokeLinecap="round" strokeLinejoin="round"
                    d="M21 21l-5.197-5.197m0 0A7.5 7.5 0 105.196 15.803a7.5
                       7.5 0 0010.607 0z" />
            </svg>
          }
          title="Track Your Ticket"
          description="Look up your ticket by reference ID to see its current status."
          cta="Track Now"
          color="slate"
        />
        <ActionCard
          href="/admin"
          icon={
            <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}>
              <path strokeLinecap="round" strokeLinejoin="round"
                    d="M3 13.125C3 12.504 3.504 12 4.125 12h2.25c.621 0 1.125.504
                       1.125 1.125v6.75C7.5 20.496 6.996 21 6.375 21h-2.25A1.125
                       1.125 0 013 19.875v-6.75zM9.75 8.625c0-.621.504-1.125
                       1.125-1.125h2.25c.621 0 1.125.504 1.125 1.125v11.25c0
                       .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0
                       01-1.125-1.125V8.625zM16.5 4.125c0-.621.504-1.125
                       1.125-1.125h2.25C20.496 3 21 3.504 21 4.125v15.75c0
                       .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0
                       01-1.125-1.125V4.125z" />
            </svg>
          }
          title="Admin Dashboard"
          description="View real-time metrics, ticket volume, and AI agent performance."
          cta="View Dashboard"
          color="slate"
        />
      </div>

      {/* Stats strip */}
      <div className="mt-20 grid grid-cols-2 sm:grid-cols-4 gap-px bg-slate-200 rounded-xl overflow-hidden">
        {[
          { label: 'Tickets Analyzed', value: '55+' },
          { label: 'Knowledge Base Entries', value: '12' },
          { label: 'Escalation Triggers', value: '21' },
          { label: 'Channels Supported', value: '3' },
        ].map((stat) => (
          <div key={stat.label} className="bg-white px-6 py-5 text-center">
            <div className="text-2xl font-bold text-brand-600">{stat.value}</div>
            <div className="text-xs text-slate-500 mt-0.5">{stat.label}</div>
          </div>
        ))}
      </div>
    </div>
  );
}

function ActionCard({
  href, icon, title, description, cta, color,
}: {
  href: string;
  icon: React.ReactNode;
  title: string;
  description: string;
  cta: string;
  color: 'brand' | 'slate';
}) {
  const iconBg = color === 'brand' ? 'bg-brand-50 text-brand-600' : 'bg-slate-100 text-slate-600';
  const ctaClass = color === 'brand' ? 'btn-primary' : 'btn-secondary';

  return (
    <Link
      href={href}
      className="card p-6 flex flex-col gap-4 hover:border-brand-200 hover:shadow-md
                 transition-all duration-200 group"
    >
      <div className={`w-11 h-11 rounded-xl ${iconBg} flex items-center justify-center`}>
        {icon}
      </div>
      <div>
        <h2 className="font-semibold text-slate-900 mb-1 group-hover:text-brand-700 transition-colors">
          {title}
        </h2>
        <p className="text-sm text-slate-500 leading-relaxed">{description}</p>
      </div>
      <span className={`${ctaClass} mt-auto w-full`}>{cta}</span>
    </Link>
  );
}
