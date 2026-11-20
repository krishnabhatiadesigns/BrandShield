export type Role = 'creator' | 'manager' | 'approver' | 'admin'
export type ContentType = 'social' | 'ad' | 'email' | 'document'
export type Severity = 'low' | 'medium' | 'high'
export type EvidenceStatus = 'supported' | 'contradicted' | 'unsupported' | 'needs_verification'
export type Decision = 'pending' | 'accepted' | 'edited' | 'rejected'
export interface Session {
  token: string
  role: Role
  display_name: string
  workspace_id: number
  workspace_name: string
}

export interface Me {
  user_id: string
  display_name: string
  role: Role
  workspace_id: number
  workspace_name: string
  llm_enabled: boolean
}

export interface WorkspaceMember {
  user_id: string
  email: string | null
  display_name: string
  role: Role
  is_active: boolean
  created_at: string
}

export interface Workspace {
  id: number
  name: string
  role: Role
  organization_id: number
  organization_name: string
}

export interface Finding {
  id: number
  category: string
  severity: Severity
  span_start: number | null
  span_end: number | null
  affected_text: string
  rule: string
  explanation: string
  source_passage_id: number | null
  source_quote: string | null
  source_title: string | null
  source_rule_id: number | null
  source_rule_version: number | null
  source_rule_title: string | null
  source_rule_text: string | null
  evidence_status: EvidenceStatus
  confidence: number
  suggestion: string | null
  creator_decision: Decision
  edited_text: string | null
  detector: string
}

export interface Version {
  id: number
  version_no: number
  body: string
  status: string
  review_state: string
  created_at: string
  created_by: string
}

export interface ReviewRun {
  llm_status: string
  llm_message: string
  deterministic_count: number
  llm_count: number
  duration_ms: number
}

export interface Comment {
  id: number
  author: string
  body: string
  created_at: string
}

export interface Approval {
  id: number
  version_id: number
  decision: string
  reason: string | null
  reviewer: string
  high_severity_signoff: boolean
  created_at: string
}

export interface ContentDetail {
  id: number
  title: string
  content_type: ContentType
  status: string
  created_by: string
  created_at: string
  updated_at: string
  current_version: Version | null
  findings: Finding[]
  review_run: ReviewRun | null
  comments: Comment[]
  approvals: Approval[]
}

export interface ContentSummary {
  id: number
  title: string
  content_type: ContentType
  status: string
  created_by: string
  updated_at: string
  version_no: number
  open_high: number
  needs_verification: number
}

export interface SampleInfo {
  key: string
  title: string
  content_type: ContentType
  body: string
}

export interface Passage {
  id: number
  source: string
  section: string | null
  page: number | null
  text: string
}

export interface Term {
  id: number
  term: string
  kind: string
  replacement: string | null
  notes: string | null
}

export interface Fact {
  id: number
  fact_key: string
  value: string
  unit: string | null
  source_passage_id: number | null
}

export interface PaletteColor {
  id: number
  name: string
  hex: string
  role: string | null
}

export interface BrandProfile {
  workspace_id: number
  workspace_name: string
  company_context: string
  passages: Passage[]
  terms: Term[]
  facts: Fact[]
  palette: PaletteColor[]
  rules: GuidelineRule[]
  disclaimers: Record<string, string | null>
}

export interface GuidelineRule {
  id: number
  category: 'tone' | 'messaging' | 'claim' | 'terminology' | 'fact' | 'disclaimer' | 'visual' | 'logo' | 'typography' | 'other'
  title: string
  description: string
  good_example: string | null
  bad_example: string | null
  severity: Severity
  mandatory: boolean
  content_types: ContentType[]
  source_passage_id: number | null
  enabled: boolean
  version: number
  effective_date: string
}

export interface GuidelineRulePayload {
  category: GuidelineRule['category']
  title: string
  description: string
  good_example: string | null
  bad_example: string | null
  severity: Severity
  mandatory: boolean
  content_types: ContentType[]
  source_passage_id: number | null
  enabled: boolean
  effective_date?: string
}

export interface HistoryVersion {
  version_id: number
  version_no: number
  status: string
  created_by: string
  created_at: string
  body: string
  finding_count: number
  approvals: { decision: string; reason: string | null; reviewer: string; created_at: string }[]
}

export interface AuditEvent {
  id: number
  actor: string
  action: string
  entity_type: string
  entity_id: number | null
  detail: string | null
  created_at: string
}

export interface VisualIssue {
  category: string
  severity: Severity
  rule: string
  explanation: string
  affected_text: string
  suggestion: string | null
}

export interface VisualCheckResponse {
  issues: VisualIssue[]
  contrast_ratio: number | null
  palette_match: {
    input: string
    closest: string
    closest_hex: string
    delta_e: number
    on_brand: boolean
  }[]
  image?: {
    filename: string
    format: string
    width: number
    height: number
    colors: { hex: string; percentage: number }[]
  }
  limitations?: string[]
}
