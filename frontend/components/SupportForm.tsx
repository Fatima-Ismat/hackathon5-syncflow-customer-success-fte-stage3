'use client';

import { useState } from 'react';
import { submitSupportForm, type SupportFormData, type SubmitResult } from '@/lib/api';

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const CATEGORIES = [
  { value: '',                label: 'Select a category…' },
  { value: 'account_access', label: 'Account Access / Login' },
  { value: 'api',            label: 'API & Developer Issues' },
  { value: 'billing',        label: 'Billing & Payments' },
  { value: 'integration',    label: 'Integration Issues' },
  { value: 'workflow',       label: 'Workflow & Automations' },
  { value: 'team',           label: 'Team & User Management' },
  { value: 'security',       label: 'Security & SSO' },
  { value: 'data',           label: 'Data Export & Privacy' },
  { value: 'other',          label: 'Other' },
];

const PRIORITIES = [
  { value: 'low',    label: 'Low — general question' },
  { value: 'medium', label: 'Medium — impacting my workflow' },
  { value: 'high',   label: 'High — blocking my team' },
];

type FormState = 'idle' | 'submitting' | 'success' | 'error';

// ---------------------------------------------------------------------------
// Validation
// ---------------------------------------------------------------------------

interface FormErrors {
  name?: string;
  email?: string;
  subject?: string;
  category?: string;
  message?: string;
}

function validate(data: SupportFormData): FormErrors {
  const errors: FormErrors = {};
  if (!data.name.trim())
    errors.name = 'Name is required.';
  if (!data.email.trim())
    errors.email = 'Email is required.';
  else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(data.email))
    errors.email = 'Please enter a valid email address.';
  if (!data.subject.trim())
    errors.subject = 'Subject is required.';
  if (!data.category)
    errors.category = 'Please select a category.';
  if (!data.message.trim())
    errors.message = 'Message is required.';
  else if (data.message.trim().length < 20)
    errors.message = 'Please describe your issue in at least 20 characters.';
  return errors;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function SupportForm() {
  const [formData, setFormData] = useState<SupportFormData>({
    name:     '',
    email:    '',
    subject:  '',
    category: '',
    priority: 'medium',
    message:  '',
  });
  const [errors, setErrors]         = useState<FormErrors>({});
  const [touched, setTouched]       = useState<Set<string>>(new Set());
  const [formState, setFormState]   = useState<FormState>('idle');
  const [result, setResult]         = useState<SubmitResult | null>(null);
  const [apiError, setApiError]     = useState<string>('');

  // Live validation on change if field has been touched
  function handleChange(
    e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>,
  ) {
    const { name, value } = e.target;
    const updated = { ...formData, [name]: value };
    setFormData(updated);
    if (touched.has(name)) {
      setErrors(validate(updated));
    }
  }

  function handleBlur(e: React.FocusEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) {
    const { name } = e.target;
    const next = new Set(touched).add(name);
    setTouched(next);
    setErrors(validate(formData));
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();

    // Touch all fields to show errors
    setTouched(new Set(['name', 'email', 'subject', 'category', 'priority', 'message']));
    const validationErrors = validate(formData);
    setErrors(validationErrors);

    if (Object.keys(validationErrors).length > 0) return;

    setFormState('submitting');
    setApiError('');

    try {
      const response = await submitSupportForm(formData);
      if (response.success) {
        setResult(response.data);
        setFormState('success');
      } else {
        setApiError(response.error || 'Something went wrong. Please try again.');
        setFormState('error');
      }
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Network error. Please check your connection.';
      setApiError(msg);
      setFormState('error');
    }
  }

  function handleReset() {
    setFormData({ name: '', email: '', subject: '', category: '', priority: 'medium', message: '' });
    setErrors({});
    setTouched(new Set());
    setFormState('idle');
    setResult(null);
    setApiError('');
  }

  // ── Success screen ────────────────────────────────────────────────────────
  if (formState === 'success' && result) {
    return <SuccessScreen result={result} onReset={handleReset} />;
  }

  // ── Form ─────────────────────────────────────────────────────────────────
  const isSubmitting = formState === 'submitting';

  return (
    <form onSubmit={handleSubmit} noValidate className="space-y-5">
      {/* Name + Email */}
      <div className="grid sm:grid-cols-2 gap-5">
        <Field label="Full Name" error={touched.has('name') ? errors.name : undefined} required>
          <input
            type="text"
            name="name"
            value={formData.name}
            onChange={handleChange}
            onBlur={handleBlur}
            placeholder="Jane Smith"
            disabled={isSubmitting}
            className={inputClass(touched.has('name') && !!errors.name)}
            autoComplete="name"
          />
        </Field>
        <Field label="Email Address" error={touched.has('email') ? errors.email : undefined} required>
          <input
            type="email"
            name="email"
            value={formData.email}
            onChange={handleChange}
            onBlur={handleBlur}
            placeholder="jane@company.com"
            disabled={isSubmitting}
            className={inputClass(touched.has('email') && !!errors.email)}
            autoComplete="email"
          />
        </Field>
      </div>

      {/* Subject */}
      <Field label="Subject" error={touched.has('subject') ? errors.subject : undefined} required>
        <input
          type="text"
          name="subject"
          value={formData.subject}
          onChange={handleChange}
          onBlur={handleBlur}
          placeholder="Brief description of your issue"
          disabled={isSubmitting}
          className={inputClass(touched.has('subject') && !!errors.subject)}
        />
      </Field>

      {/* Category + Priority */}
      <div className="grid sm:grid-cols-2 gap-5">
        <Field label="Category" error={touched.has('category') ? errors.category : undefined} required>
          <select
            name="category"
            value={formData.category}
            onChange={handleChange}
            onBlur={handleBlur}
            disabled={isSubmitting}
            className={inputClass(touched.has('category') && !!errors.category)}
          >
            {CATEGORIES.map((c) => (
              <option key={c.value} value={c.value} disabled={!c.value}>
                {c.label}
              </option>
            ))}
          </select>
        </Field>
        <Field label="Priority">
          <select
            name="priority"
            value={formData.priority}
            onChange={handleChange}
            disabled={isSubmitting}
            className="input-base"
          >
            {PRIORITIES.map((p) => (
              <option key={p.value} value={p.value}>{p.label}</option>
            ))}
          </select>
        </Field>
      </div>

      {/* Message */}
      <Field
        label="Message"
        error={touched.has('message') ? errors.message : undefined}
        hint={`${formData.message.length} characters`}
        required
      >
        <textarea
          name="message"
          value={formData.message}
          onChange={handleChange}
          onBlur={handleBlur}
          placeholder="Please describe your issue in detail. Include any error messages, steps to reproduce, and what you have already tried."
          disabled={isSubmitting}
          rows={6}
          className={inputClass(touched.has('message') && !!errors.message) + ' resize-none'}
        />
      </Field>

      {/* API error */}
      {formState === 'error' && (
        <div className="flex gap-3 items-start rounded-lg bg-red-50 border border-red-200 p-4">
          <svg className="w-5 h-5 text-red-500 flex-shrink-0 mt-0.5" fill="none" viewBox="0 0 24 24"
               stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round"
                  d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948
                     3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949
                     3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126zM12 15.75h.007v.008H12v-.008z" />
          </svg>
          <div>
            <p className="text-sm font-medium text-red-800">Submission failed</p>
            <p className="text-sm text-red-700 mt-0.5">{apiError}</p>
          </div>
        </div>
      )}

      {/* Submit */}
      <div className="flex items-center justify-between pt-1">
        <p className="text-xs text-slate-400">
          Fields marked <span className="text-red-500">*</span> are required
        </p>
        <button type="submit" disabled={isSubmitting} className="btn-primary min-w-[160px]">
          {isSubmitting ? (
            <>
              <Spinner />
              Submitting…
            </>
          ) : (
            <>
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M6 12L3.269 3.126A59.768
                  59.768 0 0121.485 12 59.77 59.77 0 013.27 20.876L5.999 12zm0 0h7.5" />
              </svg>
              Submit Request
            </>
          )}
        </button>
      </div>
    </form>
  );
}

// ---------------------------------------------------------------------------
// Success Screen
// ---------------------------------------------------------------------------

function SuccessScreen({
  result,
  onReset,
}: {
  result: SubmitResult;
  onReset: () => void;
}) {
  const isEscalated = result.should_escalate;
  const confidence  = result.agent_confidence;
  const pct         = Math.round(confidence * 100);

  return (
    <div className="space-y-6">
      {/* Banner */}
      <div className={`flex gap-4 rounded-xl p-5 border ${
        isEscalated
          ? 'bg-amber-50 border-amber-200'
          : 'bg-emerald-50 border-emerald-200'
      }`}>
        <div className={`w-10 h-10 rounded-full flex items-center justify-center flex-shrink-0 ${
          isEscalated ? 'bg-amber-100' : 'bg-emerald-100'
        }`}>
          {isEscalated ? (
            <svg className="w-5 h-5 text-amber-600" fill="none" viewBox="0 0 24 24"
                 stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round"
                    d="M12 9v3.75m9-.75a9 9 0 11-18 0 9 9 0 0118 0zm-9 3.75h.008v.008H12v-.008z" />
            </svg>
          ) : (
            <svg className="w-5 h-5 text-emerald-600" fill="none" viewBox="0 0 24 24"
                 stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M9 12.75L11.25 15 15 9.75M21
                12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
          )}
        </div>
        <div className="min-w-0">
          <p className={`font-semibold text-sm ${isEscalated ? 'text-amber-900' : 'text-emerald-900'}`}>
            {isEscalated ? 'Connecting you with a specialist' : 'Request received — AI response ready'}
          </p>
          {result.ticket_ref && (
            <p className={`text-sm mt-0.5 font-mono ${isEscalated ? 'text-amber-700' : 'text-emerald-700'}`}>
              Ticket: {result.ticket_ref}
            </p>
          )}
        </div>
      </div>

      {/* Metadata strip */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <MetaBadge label="Priority"    value={result.priority}   />
        <MetaBadge label="Sentiment"   value={result.sentiment}  />
        <MetaBadge label="Confidence"  value={`${pct}%`}         />
        <MetaBadge label="Response ms" value={String(result.processing_time_ms)} />
      </div>

      {/* AI Response */}
      <div>
        <h3 className="text-sm font-semibold text-slate-700 mb-2 flex items-center gap-2">
          <svg className="w-4 h-4 text-brand-500" fill="none" viewBox="0 0 24 24"
               stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round"
                  d="M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25
                     12l2.846-.813a4.5 4.5 0 003.09-3.09L9 5.25l.813 2.846a4.5 4.5
                     0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.09z" />
          </svg>
          AI Response
        </h3>
        <div className="rounded-lg bg-slate-50 border border-slate-200 p-4 text-sm text-slate-700
                        whitespace-pre-wrap leading-relaxed font-mono">
          {result.response}
        </div>
      </div>

      {/* KB used */}
      {result.kb_used && result.kb_section && (
        <div className="flex items-center gap-2 text-xs text-slate-500">
          <svg className="w-3.5 h-3.5 text-brand-400" fill="none" viewBox="0 0 24 24"
               stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round"
                  d="M12 6.042A8.967 8.967 0 006 3.75c-1.052 0-2.062.18-3
                     .512v14.25A8.987 8.987 0 016 18c2.305 0 4.408.867 6 2.292m0-14.25a8.966
                     8.966 0 016-2.292c1.052 0 2.062.18 3 .512v14.25A8.987 8.987 0
                     0018 18a8.967 8.967 0 00-6 2.292m0-14.25v14.25" />
          </svg>
          Answer sourced from: {result.kb_section}
        </div>
      )}

      {/* SLA */}
      {result.sla_deadline && (
        <div className="flex items-center gap-2 text-xs text-slate-500">
          <svg className="w-3.5 h-3.5 text-slate-400" fill="none" viewBox="0 0 24 24"
               stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round"
                  d="M12 6v6h4.5m4.5 0a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
          SLA deadline: {new Date(result.sla_deadline).toLocaleString()}
        </div>
      )}

      <button type="button" onClick={onReset} className="btn-secondary w-full">
        Submit Another Request
      </button>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function Field({
  label, error, hint, required, children,
}: {
  label: string;
  error?: string;
  hint?: string;
  required?: boolean;
  children: React.ReactNode;
}) {
  return (
    <div>
      <label className="label-base">
        {label}
        {required && <span className="text-red-500 ml-0.5">*</span>}
      </label>
      {children}
      {error ? (
        <p className="mt-1.5 text-xs text-red-600 flex items-center gap-1">
          <svg className="w-3 h-3 flex-shrink-0" fill="currentColor" viewBox="0 0 20 20">
            <path fillRule="evenodd" clipRule="evenodd"
                  d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7 4a1 1 0 11-2 0 1 1 0
                     012 0zm-1-9a1 1 0 00-1 1v4a1 1 0 102 0V6a1 1 0 00-1-1z" />
          </svg>
          {error}
        </p>
      ) : hint ? (
        <p className="mt-1.5 text-xs text-slate-400">{hint}</p>
      ) : null}
    </div>
  );
}

function MetaBadge({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg bg-slate-50 border border-slate-100 px-3 py-2 text-center">
      <div className="text-xs text-slate-400 mb-0.5">{label}</div>
      <div className="text-sm font-semibold text-slate-800 capitalize">{value}</div>
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

function inputClass(hasError: boolean) {
  return `input-base ${hasError ? 'border-red-300 focus:border-red-400 focus:ring-red-200' : ''}`;
}
