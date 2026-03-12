import type { Metadata } from 'next';
import Link from 'next/link';
import './globals.css';

export const metadata: Metadata = {
  title: 'SyncFlow Support – NovaSync Technologies',
  description: 'Hackathon 5 Stage 3 — AI-powered Customer Success Digital FTE for SyncFlow. 24/7 support across Gmail, WhatsApp, and Web Form.',
  keywords: 'customer success, AI support, SyncFlow, NovaSync, helpdesk, ticketing',
  authors: [{ name: 'Ismat Fatima' }],
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className="min-h-screen flex flex-col">
        <header className="border-b border-slate-200 bg-white sticky top-0 z-50">
          <div className="max-w-6xl mx-auto px-4 sm:px-6 h-16 flex items-center justify-between">
            {/* Logo */}
            <Link href="/" className="flex items-center gap-2.5 group">
              <div className="w-8 h-8 rounded-lg bg-brand-600 flex items-center justify-center
                              group-hover:bg-brand-700 transition-colors">
                <svg className="w-4.5 h-4.5 text-white" fill="none" viewBox="0 0 24 24"
                     stroke="currentColor" strokeWidth={2.5}>
                  <path strokeLinecap="round" strokeLinejoin="round"
                        d="M8.625 9.75a.375.375 0 11-.75 0 .375.375 0 01.75 0zm0 0H8.25m4.125
                           0a.375.375 0 11-.75 0 .375.375 0 01.75 0zm0 0H12m4.125 0a.375.375 0
                           11-.75 0 .375.375 0 01.75 0zm0 0h-.375m-13.5 3.01c0 1.6 1.123
                           2.994 2.707 3.227 1.087.16 2.185.283 3.293.369V21l4.184-4.183a1.14
                           1.14 0 01.778-.332 48.294 48.294 0 005.83-.498c1.585-.233
                           2.708-1.626 2.708-3.228V6.741c0-1.602-1.123-2.995-2.707-3.228A48.394
                           48.394 0 0012 3c-2.392 0-4.744.175-7.043.513C3.373 3.746
                           2.25 5.14 2.25 6.741v6.018z" />
                </svg>
              </div>
              <div>
                <span className="font-bold text-slate-900 text-sm leading-none block">
                  SyncFlow Support
                </span>
                <span className="text-xs text-slate-500 leading-none">
                  NovaSync Technologies
                </span>
              </div>
            </Link>

            {/* Navigation */}
            <nav className="flex items-center gap-1">
              <NavLink href="/support">Submit a Request</NavLink>
              <NavLink href="/ticket-status">Track Ticket</NavLink>
              <NavLink href="/admin">Dashboard</NavLink>
            </nav>
          </div>
        </header>

        <main className="flex-1">
          {children}
        </main>

        <footer className="border-t border-slate-200 bg-white mt-auto">
          <div className="max-w-6xl mx-auto px-4 sm:px-6 py-5 flex items-center
                          justify-between text-xs text-slate-400">
            <span>
              &copy; {new Date().getFullYear()} NovaSync Technologies. All rights reserved.
            </span>
            <span className="flex items-center gap-1.5">
              <span className="inline-block w-1.5 h-1.5 rounded-full bg-emerald-400" />
              Powered by SyncFlow AI Digital FTE
            </span>
          </div>
        </footer>
      </body>
    </html>
  );
}

function NavLink({ href, children }: { href: string; children: React.ReactNode }) {
  return (
    <Link
      href={href}
      className="px-3.5 py-2 rounded-lg text-sm font-medium text-slate-600
                 hover:text-slate-900 hover:bg-slate-100 transition-colors duration-150"
    >
      {children}
    </Link>
  );
}
