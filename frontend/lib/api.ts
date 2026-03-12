/**
 * API Client – SyncFlow Customer Success Frontend
 * Typed wrappers around the FastAPI backend endpoints.
 */

const BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface SupportFormData {
  name: string;
  email: string;
  subject: string;
  category: string;
  priority: string;
  message: string;
}

export interface SubmitResult {
  ticket_ref: string | null;
  customer_ref: string | null;
  customer_name: string | null;
  customer_plan: string | null;
  channel: string;
  response: string;
  subject_line: string | null;
  should_escalate: boolean;
  escalation_reason: string | null;
  escalation_queue: string | null;
  priority: string;
  sentiment: string;
  sentiment_score: number;
  agent_confidence: number;
  kb_used: boolean;
  kb_section: string | null;
  sla_deadline: string | null;
  processing_time_ms: number;
  processed_at: string;
}

export interface Ticket {
  ticket_ref: string;
  customer_id: string;
  channel: string;
  status: string;
  priority: string;
  topic: string | null;
  tags: string[];
  issue_summary: string;
  assigned_to: string;
  escalation_reason: string | null;
  escalation_queue: string | null;
  escalation_id: string | null;
  escalated_at: string | null;
  sla_deadline: string;
  sla_hours: number;
  sla_breached: boolean;
  agent_confidence: number | null;
  sentiment_at_open: string | null;
  kb_used: boolean;
  created_at: string;
  updated_at: string;
  resolved_at: string | null;
  resolution_time_s: number | null;
  conversation_refs: string[];
  message_count: number;
}

export interface TicketListResult {
  tickets: Ticket[];
  total: number;
  limit: number;
  offset: number;
}

export interface MetricsSummary {
  window_hours: number;
  since: string;
  generated_at: string;
  volume: {
    tickets_created: number;
    messages_processed: number;
    responses_generated: number;
    escalations: number;
    resolutions: number;
    sla_breaches: number;
  };
  quality: {
    avg_resolution_time_s: number | null;
    avg_agent_confidence: number | null;
    kb_usage_rate: number | null;
    auto_resolution_rate: number | null;
    escalation_rate: number | null;
  };
  channel_usage: Record<string, number>;
  escalation_reasons: Record<string, number>;
  escalation_queues: Record<string, number>;
}

export interface ChannelBreakdown {
  window_hours: number;
  channels: Record<string, {
    tickets: number;
    responses: number;
    escalations: number;
    avg_confidence: number | null;
  }>;
  generated_at: string;
}

export interface APIResponse<T> {
  success: boolean;
  data: T;
  error: string | null;
  timestamp: string;
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

async function apiFetch<T>(
  path: string,
  options?: RequestInit,
): Promise<APIResponse<T>> {
  const res = await fetch(`${BASE_URL}${path}`, {
    headers: { 'Content-Type': 'application/json', ...options?.headers },
    ...options,
  });

  if (!res.ok) {
    let errorMsg = `HTTP ${res.status}`;
    try {
      const body = await res.json();
      errorMsg = body?.detail || body?.error || errorMsg;
    } catch {}
    throw new Error(errorMsg);
  }

  return res.json();
}

// ---------------------------------------------------------------------------
// Support Form
// ---------------------------------------------------------------------------

export async function submitSupportForm(
  form: SupportFormData,
): Promise<APIResponse<SubmitResult>> {
  return apiFetch<SubmitResult>('/support/submit', {
    method: 'POST',
    body: JSON.stringify({
      channel:      'web_form',
      customer_ref: form.email || `guest_${Date.now()}`,
      name:         form.name,
      email:        form.email,
      subject:      form.subject,
      category:     form.category,
      priority:     form.priority,
      message:      form.message,
    }),
  });
}

// ---------------------------------------------------------------------------
// Tickets
// ---------------------------------------------------------------------------

export async function getTicket(
  ticketRef: string,
): Promise<APIResponse<Ticket>> {
  return apiFetch<Ticket>(`/tickets/${encodeURIComponent(ticketRef)}`);
}

export async function listTickets(params?: {
  status?: string;
  priority?: string;
  limit?: number;
  offset?: number;
}): Promise<APIResponse<TicketListResult>> {
  const qs = new URLSearchParams();
  if (params?.status)   qs.set('status',   params.status);
  if (params?.priority) qs.set('priority', params.priority);
  if (params?.limit)    qs.set('limit',    String(params.limit));
  if (params?.offset)   qs.set('offset',   String(params.offset));
  const query = qs.toString() ? `?${qs.toString()}` : '';
  return apiFetch<TicketListResult>(`/tickets${query}`);
}

// ---------------------------------------------------------------------------
// Metrics
// ---------------------------------------------------------------------------

export async function getMetricsSummary(
  hours = 24,
): Promise<APIResponse<MetricsSummary>> {
  return apiFetch<MetricsSummary>(`/metrics/summary?hours=${hours}`);
}

export async function getChannelBreakdown(
  hours = 24,
): Promise<APIResponse<ChannelBreakdown>> {
  return apiFetch<ChannelBreakdown>(`/metrics/channels?hours=${hours}`);
}

export async function checkHealth(): Promise<boolean> {
  try {
    const res = await fetch(`${BASE_URL}/health`);
    return res.ok;
  } catch {
    return false;
  }
}
