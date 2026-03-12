'use client';

import { useState } from 'react';
import { getTicket, type Ticket } from '@/lib/api';
import TicketCard from '@/components/TicketCard';

type LookupState = 'idle' | 'loading' | 'found' | 'not_found' | 'error';

export default function TicketStatusPage() {
  const [ticketRef, setTicketRef] = useState('');
  const [state, setState]         = useState<LookupState>('idle');
  const [ticket, setTicket]       = useState<Ticket | null>(null);
  const [errorMsg, setErrorMsg]   = useState('');

  async function handleLookup(e: React.FormEvent) {
    e.preventDefault();
    const ref = ticketRef.trim().toUpperCase();
    if (!ref) return;

    setState('loading');
    setTicket(null);
    setErrorMsg('');

    try {
      const res = await getTicket(ref);
      if (res.success && res.data) {
        setTicket(res.data);
        setState('found');
      } else {
        setErrorMsg(res.error || 'Ticket not found.');
        setState('not_found');
      }
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Unknown error.';
      if (msg.includes('404') || msg.toLowerCase().includes('not found')) {
        setState('not_found');
        setErrorMsg(`No ticket found with reference "${ref}".`);
      } else {
        setState('error');
        setErrorMsg(msg);
      }
    }
  }

  function handleReset() {
    setTicketRef('');
    setState('idle');
    setTicket(null);
    setErrorMsg('');
  }

  return (
    <div className="max-w-2xl mx-auto px-4 sm:px-6 py-12">
      {/* Header */}
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-slate-900 mb-2">Track Your Ticket</h1>
        <p className="text-slate-500 text-sm">
          Enter your ticket reference number (e.g. <code className="font-mono text-xs bg-slate-100
          rounded px-1.5 py-0.5">TKT-20260311-4821</code>) to see its current status,
          priority, and SLA deadline.
        </p>
      </div>

      {/* Lookup form */}
      <div className="card p-6 mb-6">
        <form onSubmit={handleLookup} className="flex gap-3">
          <div className="flex-1">
            <label htmlFor="ticketRef" className="label-base">
              Ticket Reference
            </label>
            <input
              id="ticketRef"
              type="text"
              value={ticketRef}
              onChange={(e) => setTicketRef(e.target.value)}
              placeholder="TKT-20260311-4821"
              className="input-base font-mono"
              autoComplete="off"
              spellCheck={false}
              disabled={state === 'loading'}
            />
          </div>
          <div className="flex items-end">
            <button
              type="submit"
              disabled={!ticketRef.trim() || state === 'loading'}
              className="btn-primary"
            >
              {state === 'loading' ? (
                <>
                  <Spinner />
                  Looking up…
                </>
              ) : (
                <>
                  <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24"
                       stroke="currentColor" strokeWidth={2.5}>
                    <path strokeLinecap="round" strokeLinejoin="round"
                          d="M21 21l-5.197-5.197m0 0A7.5 7.5 0 105.196
                             15.803a7.5 7.5 0 0010.607 0z" />
                  </svg>
                  Look Up
                </>
              )}
            </button>
          </div>
        </form>
      </div>

      {/* Results */}
      {state === 'found' && ticket && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-semibold text-slate-700">Ticket Details</h2>
            <button onClick={handleReset} className="text-xs text-brand-600 hover:text-brand-700
                                                     font-medium">
              Search another ticket
            </button>
          </div>
          <TicketCard ticket={ticket} />
        </div>
      )}

      {state === 'not_found' && (
        <div className="card p-8 text-center">
          <div className="w-14 h-14 rounded-full bg-slate-100 flex items-center justify-center
                          mx-auto mb-4">
            <svg className="w-7 h-7 text-slate-400" fill="none" viewBox="0 0 24 24"
                 stroke="currentColor" strokeWidth={1.8}>
              <path strokeLinecap="round" strokeLinejoin="round"
                    d="M9.879 7.519c1.171-1.025 3.071-1.025 4.242 0 1.172 1.025
                       1.172 2.687 0 3.712-.203.179-.43.326-.67.442-.745.361-1.45.999-1.45
                       1.827v.75M21 12a9 9 0 11-18 0 9 9 0 0118 0zm-9 5.25h.008v.008H12v-.008z" />
            </svg>
          </div>
          <p className="text-slate-700 font-semibold mb-1">Ticket not found</p>
          <p className="text-sm text-slate-400 mb-5">{errorMsg}</p>
          <button onClick={handleReset} className="btn-secondary">
            Try another reference
          </button>
        </div>
      )}

      {state === 'error' && (
        <div className="card border-red-200 p-6">
          <div className="flex gap-3 items-start">
            <svg className="w-5 h-5 text-red-500 flex-shrink-0" fill="none" viewBox="0 0 24 24"
                 stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round"
                    d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948
                       3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949
                       3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126zM12 15.75h.008v.008H12v-.008z" />
            </svg>
            <div>
              <p className="text-sm font-semibold text-red-800">Could not reach the backend</p>
              <p className="text-sm text-red-700 mt-0.5">{errorMsg}</p>
              <p className="text-xs text-red-600 mt-2">
                Make sure the FastAPI server is running:{' '}
                <code className="font-mono bg-red-100 px-1 rounded">
                  uvicorn api.main:app --reload --port 8000
                </code>
              </p>
            </div>
          </div>
        </div>
      )}

      {/* Help text */}
      {state === 'idle' && (
        <div className="text-center py-8 text-slate-400">
          <svg className="w-12 h-12 mx-auto mb-3 opacity-40" fill="none" viewBox="0 0 24 24"
               stroke="currentColor" strokeWidth={1.2}>
            <path strokeLinecap="round" strokeLinejoin="round"
                  d="M16.5 6v.75m0 3v.75m0 3v.75m0 3V18m-9-5.25h5.25M7.5 15h3M3.375
                     5.25c-.621 0-1.125.504-1.125 1.125v3.026a2.999 2.999 0 010
                     5.198v3.031c0 .621.504 1.125 1.125 1.125h17.25c.621 0 1.125-.504
                     1.125-1.125v-3.03a3 3 0 010-5.2V6.375c0-.621-.504-1.125-1.125-1.125H3.375z" />
          </svg>
          <p className="text-sm">Your ticket reference is shown after submitting a support request.</p>
          <p className="text-xs mt-1">
            Format: <span className="font-mono">TKT-YYYYMMDD-XXXX</span>
          </p>
        </div>
      )}
    </div>
  );
}

function Spinner() {
  return (
    <svg className="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24">
      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
      <path className="opacity-75" fill="currentColor"
            d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
    </svg>
  );
}
