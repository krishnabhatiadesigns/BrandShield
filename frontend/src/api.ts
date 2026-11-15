import type {
  AuditEvent,
  BrandProfile,
  ContentDetail,
  ContentSummary,
  HistoryVersion,
  Me,
  SampleInfo,
  Session,
  VisualCheckResponse,
} from './types'

const BASE = import.meta.env.VITE_API_URL ?? ''
const TOKEN_KEY = 'brandshield.token'

export class ApiError extends Error {
  status: number
  constructor(message: string, status: number) {
    super(message)
    this.status = status
  }
}

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY)
}

export function setToken(token: string | null) {
  if (token) localStorage.setItem(TOKEN_KEY, token)
  else localStorage.removeItem(TOKEN_KEY)
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const token = getToken()
  const headers = new Headers(init.headers)
  if (token) headers.set('X-Demo-Token', token)
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

  me: () => request<Me>('/api/me'),

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
  audit: () => request<AuditEvent[]>('/api/audit'),

  brand: () => request<BrandProfile>('/api/brand'),
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
}
