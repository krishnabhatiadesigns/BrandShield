import type {
  AuditEvent,
  BrandProfile,
  ContentDetail,
  GuidelineRule,
  GuidelineRulePayload,
  ContentSummary,
  HistoryVersion,
  Me,
  SampleInfo,
  Session,
  VisualCheckResponse,
  WorkspaceMember,
  Workspace,
} from './types'

const BASE = import.meta.env.VITE_API_URL ?? ''
const TOKEN_KEY = 'brandshield.token'
const TOKEN_TYPE_KEY = 'brandshield.token-type'
const WORKSPACE_KEY = 'brandshield.workspace-id'

export class ApiError extends Error {
  status: number
  constructor(message: string, status: number) {
    super(message)
    this.status = status
  }
}

export function getToken(): string | null {
  if (localStorage.getItem(TOKEN_TYPE_KEY) === 'supabase') {
    localStorage.removeItem(TOKEN_KEY)
    localStorage.removeItem(TOKEN_TYPE_KEY)
    return null
  }
  localStorage.removeItem(TOKEN_TYPE_KEY)
  return localStorage.getItem(TOKEN_KEY)
}

export function getWorkspaceId(): number | null {
  const value = Number(localStorage.getItem(WORKSPACE_KEY))
  return Number.isInteger(value) && value > 0 ? value : null
}

export function setWorkspaceId(id: number | null) {
  if (id) localStorage.setItem(WORKSPACE_KEY, String(id))
  else localStorage.removeItem(WORKSPACE_KEY)
}

export function setToken(token: string | null) {
  if (token) {
    localStorage.setItem(TOKEN_KEY, token)
  } else {
    localStorage.removeItem(TOKEN_KEY)
  }
  localStorage.removeItem(TOKEN_TYPE_KEY)
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const token = getToken()
  const headers = new Headers(init.headers)
  if (token) headers.set('X-Demo-Token', token)
  const workspaceId = getWorkspaceId()
  if (workspaceId) headers.set('X-Workspace-ID', String(workspaceId))
  if (init.body && !(init.body instanceof FormData)) {
    headers.set('Content-Type', 'application/json')
  }

  let res: Response
  try {
    res = await fetch(`${BASE}${path}`, { ...init, headers })
  } catch {
    throw new ApiError(
      'Could not reach the server. Check your connection and try again.',
      0,
    )
  }

  if (!res.ok) {
    let detail = `Request failed (${res.status}).`
    try {
      const data = await res.json()
      if (typeof data.detail === 'string') detail = data.detail
      else if (Array.isArray(data.detail)) detail = data.detail[0]?.msg ?? detail
    } catch {
      /* keep the default message */
    }
    throw new ApiError(detail, res.status)
  }
  if (res.status === 204) return undefined as T
  return (await res.json()) as T
}

export const api = {
  health: () => request<{ status: string; llm_enabled: boolean }>('/health'),

  demoSession: (role: string) =>
    request<Session>('/api/demo/session', {
      method: 'POST',
      body: JSON.stringify({ role }),
    }),

  logout: () => request<void>('/api/logout', { method: 'POST' }),

  me: () => request<Me>('/api/me'),
  workspaces: () => request<Workspace[]>('/api/workspaces'),
  createBrand: (name: string) =>
    request<Workspace>('/api/workspaces', {
      method: 'POST',
      body: JSON.stringify({ name }),
    }),

  members: () => request<WorkspaceMember[]>('/api/admin/members'),

  inviteMember: (payload: { email: string; display_name: string; role: string }) =>
    request<WorkspaceMember>('/api/admin/members', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),

  updateMember: (userId: string, payload: { role?: string; is_active?: boolean }) =>
    request<WorkspaceMember>(`/api/admin/members/${encodeURIComponent(userId)}`, {
      method: 'PATCH',
      body: JSON.stringify(payload),
    }),

  samples: () => request<SampleInfo[]>('/api/samples'),

  listContent: () => request<ContentSummary[]>('/api/content'),
  queue: () => request<ContentSummary[]>('/api/content/queue'),
  getContent: (id: number) => request<ContentDetail>(`/api/content/${id}`),

  createContent: (payload: { title: string; content_type: string; body: string }) =>
    request<ContentDetail>('/api/content', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),

  uploadContent: (file: File, title: string, contentType: string) => {
    const form = new FormData()
    form.append('file', file)
    const params = new URLSearchParams({ title, content_type: contentType })
    return request<ContentDetail>(`/api/content/upload?${params}`, {
      method: 'POST',
      body: form,
    })
  },

  review: (id: number) =>
    request<ContentDetail>(`/api/content/${id}/review`, { method: 'POST' }),

  decideFinding: (id: number, findingId: number, decision: string, editedText?: string) =>
    request<ContentDetail>(`/api/content/${id}/findings/${findingId}/decision`, {
      method: 'POST',
      body: JSON.stringify({ decision, edited_text: editedText ?? null }),
    }),

  revise: (id: number) =>
    request<ContentDetail>(`/api/content/${id}/revise`, { method: 'POST' }),

  editDraft: (id: number, body: string, note?: string) =>
    request<ContentDetail>(`/api/content/${id}/edit-draft`, {
      method: 'POST',
      body: JSON.stringify({ body, note: note ?? null }),
    }),

  submit: (id: number) =>
    request<ContentDetail>(`/api/content/${id}/submit`, { method: 'POST' }),

  sendBack: (id: number, note: string) =>
    request<ContentDetail>(`/api/content/${id}/send-back`, {
      method: 'POST',
      body: JSON.stringify({ note }),
    }),

  comment: (id: number, body: string) =>
    request<ContentDetail>(`/api/content/${id}/comments`, {
      method: 'POST',
      body: JSON.stringify({ body }),
    }),

  approve: (
    id: number,
    decision: string,
    reason: string | null,
    signoff: boolean,
  ) =>
    request<ContentDetail>(`/api/content/${id}/approval`, {
      method: 'POST',
      body: JSON.stringify({
        decision,
        reason,
        high_severity_signoff: signoff,
      }),
    }),

  history: (id: number) => request<HistoryVersion[]>(`/api/content/${id}/history`),
  contentAudit: (id: number) => request<AuditEvent[]>(`/api/content/${id}/audit`),
  audit: () => request<AuditEvent[]>('/api/audit'),

  brand: () => request<BrandProfile>('/api/brand'),
  createGuidelineRule: (payload: GuidelineRulePayload) =>
    request<GuidelineRule>('/api/brand/rules', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
  updateGuidelineRule: (id: number, payload: Partial<GuidelineRulePayload>) =>
    request<GuidelineRule>(`/api/brand/rules/${id}`, {
      method: 'PATCH',
      body: JSON.stringify(payload),
    }),
  guidelineRuleVersions: (id: number) =>
    request<{
      version: number
      snapshot: Record<string, unknown>
      effective_date: string
      created_by: string
      created_at: string
    }[]>(`/api/brand/rules/${id}/versions`),
  updateCompanyContext: (companyContext: string) =>
    request<void>('/api/brand/company-context', {
      method: 'PUT',
      body: JSON.stringify({ company_context: companyContext }),
    }),
  addTerm: (payload: { term: string; kind: string; replacement?: string; notes?: string }) =>
    request('/api/brand/terms', { method: 'POST', body: JSON.stringify(payload) }),
  addFact: (payload: { fact_key: string; value: string; unit?: string }) =>
    request('/api/brand/facts', { method: 'POST', body: JSON.stringify(payload) }),
  addPalette: (payload: { name: string; hex: string; role?: string }) =>
    request('/api/brand/palette', { method: 'POST', body: JSON.stringify(payload) }),
  addPassage: (payload: { source: string; section?: string; text: string }) =>
    request('/api/brand/passages', { method: 'POST', body: JSON.stringify(payload) }),
  uploadGuideline: (file: File, title: string) => {
    const form = new FormData()
    form.append('file', file)
    return request(`/api/brand/guidelines/upload?title=${encodeURIComponent(title)}`, {
      method: 'POST',
      body: form,
    })
  },

  visualCheck: (payload: {
    hex_colors: string[]
    text_hex?: string | null
    background_hex?: string | null
  }) =>
    request<VisualCheckResponse>('/api/visual/check', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),

  visualImageCheck: (file: File) => {
    const form = new FormData()
    form.append('file', file)
    return request<VisualCheckResponse>('/api/visual/image', {
      method: 'POST',
      body: form,
    })
  },

  operationsAnalytics: () =>
    request<{ submissions: number; approved_versions: number; findings: number; usage: { event_type: string; quantity: number }[] }>(
      '/api/operations/analytics',
    ),
  auditCsvUrl: () => `${BASE}/api/operations/exports/audit.csv`,
  downloadAuditCsv: async () => {
    const token = getToken()
    const headers = new Headers()
    if (token) headers.set('X-Demo-Token', token)
    const workspaceId = getWorkspaceId()
    if (workspaceId) headers.set('X-Workspace-ID', String(workspaceId))
    const response = await fetch(`${BASE}/api/operations/exports/audit.csv`, { headers })
    if (!response.ok) throw new ApiError('Could not export the audit log.', response.status)
    const blob = await response.blob()
    const url = URL.createObjectURL(blob)
    const anchor = document.createElement('a')
    anchor.href = url
    anchor.download = 'brandshield-audit.csv'
    anchor.click()
    URL.revokeObjectURL(url)
  },
  apiKeys: () => request<{ id: number; name: string; key_prefix: string; scopes: string; is_active: boolean; created_at: string }[]>(
    '/api/operations/api-keys',
  ),
  createApiKey: (name: string, scopes: string[]) =>
    request<{ key: string; name: string; prefix: string; scopes: string[]; warning: string }>(
      '/api/operations/api-keys',
      { method: 'POST', body: JSON.stringify({ name, scopes }) },
    ),
  webhooks: () => request<{ id: number; name: string; url: string; events: string; is_active: boolean; created_at: string }[]>(
    '/api/operations/webhooks',
  ),
  createWebhook: (payload: { name: string; url: string; secret: string; events: string[] }) =>
    request<{ id: number; name: string; url: string; events: string; is_active: boolean }>(
      '/api/operations/webhooks',
      { method: 'POST', body: JSON.stringify(payload) },
    ),
  assignment: (itemId: number, payload: { assignee_user_id?: string | null; assignee_name?: string | null; due_at?: string | null }) =>
    request<Record<string, unknown>>(`/api/operations/content/${itemId}/assignment`, {
      method: 'PUT',
      body: JSON.stringify(payload),
    }),
}
