export type Role = "DENUNCIANTE" | "COLABORADOR" | "REVISOR" | "ADMIN";
export type Sensitivity = "GENERAL" | "RESTRINGIDO" | "INSTITUCIONAL";

export interface User {
  id: number;
  email: string;
  full_name: string;
  role: Role;
  alias: string;
  is_active: boolean;
  can_review_restricted: boolean;
  can_review_institutional: boolean;
  created_at: string;
  active_assignments?: number;
}

export interface FieldDef {
  key: string;
  label: string;
  type: "text" | "textarea" | "number" | "select" | "date" | "boolean";
  required?: boolean;
  public?: boolean;
  help?: string;
  options?: string[];
  max_length?: number;
  min?: number;
  max?: number;
  pattern?: string;
}

export interface DocumentPolicy {
  min_documents?: number;
  required_any?: string[][];
  note?: string;
}

export interface Category {
  id: number;
  slug: string;
  name: string;
  description: string;
  icon: string;
  parent_id: number | null;
  sensitivity: Sensitivity;
  configured_sensitivity: Sensitivity;
  min_sensitivity: Sensitivity;
  code_floor: Sensitivity;
  policy_text: string;
  field_schema: FieldDef[];
  own_field_schema: FieldDef[];
  document_policy: DocumentPolicy;
  active: boolean;
  children?: Category[];
}

export interface Meta {
  demo_mode: boolean;
  zones: string[];
  doc_types: Record<string, string>;
  protected_flags: Record<string, string>;
  policy_text: Record<Sensitivity, string>;
  disclaimer: string;
  limits_mb: { image: number; video: number; document: number };
  antivirus: { engine: string; available: boolean };
  ffmpeg_available: boolean;
}

export interface FileInfo {
  id: string;
  original_name: string;
  detected_type: string | null;
  media_class: "image" | "video" | "document" | null;
  size_bytes: number;
  sha256: string;
  status: string;
  status_detail: string | null;
  scan_engine: string | null;
  scanned_at: string | null;
  has_playback: boolean;
  duplicate_of_id: string | null;
  media_info: Record<string, unknown>;
  uploaded_at: string;
}

export interface SupportingDoc {
  id: number;
  doc_type: string;
  description: string;
  review_status: "PENDIENTE" | "ACEPTADO" | "OBSERVADO";
  review_note: string | null;
  created_at: string;
  file: FileInfo;
}

export interface CaseSummary {
  id: number;
  code: string;
  title: string;
  category: { id: number; name: string; slug: string; icon: string; parent_name: string | null };
  zone: string;
  incident_at: string;
  status: string;
  sensitivity: Sensitivity;
  publication_status: string;
  contributions_open: boolean;
  is_demo: boolean;
  created_at: string;
  submitted_at: string | null;
  pending_contributions?: number;
}

export interface HistoryEvent {
  id: number;
  event: string;
  detail: string;
  created_at: string;
  actor: string | null;
}

export interface PublicCardInfo {
  public_title: string;
  public_summary: string;
  zone: string;
  incident_date: string;
  public_fields: Record<string, unknown>;
  published_at: string | null;
  withdrawn_at: string | null;
  requested_by?: number;
  approved_by?: number | null;
}

export interface CaseDetail extends CaseSummary {
  description: string;
  specific_fields: Record<string, unknown>;
  field_labels: Record<string, string>;
  field_schema: FieldDef[];
  private_lat: number | null;
  private_lon: number | null;
  private_location_note: string | null;
  sensitive_flags: { key: string; label: string }[];
  status_reason: string | null;
  policy_text: string;
  documents: SupportingDoc[];
  public_card: PublicCardInfo | null;
  responsible: string;
  history: HistoryEvent[];
  decided_at: string | null;
  assigned_reviewers?: { id: number; full_name: string }[];
  decisions?: { decision: string; reason: string; reviewer: string; reviewer_id: number; created_at: string }[];
  reporter_alias?: string;
  contribution_counts?: Record<string, number>;
  can_publish?: boolean;
  publish_block_reason?: string;
  can_open_contributions?: boolean;
  contributions_block_reason?: string;
}

export interface PublicCase {
  code: string;
  public_title: string;
  public_summary: string;
  zone: string;
  incident_date: string;
  category: { name: string; slug: string; icon: string; parent_name: string | null };
  sensitivity: Sensitivity;
  public_fields: Record<string, unknown>;
  published_at: string;
  accepts_contributions: boolean;
  is_demo: boolean;
  contributions_received?: number;
}

export interface Correction {
  field: string;
  old_value: string | null;
  new_value: string | null;
  reason: string;
  author: string;
  created_at: string;
}

export interface ContributionValues {
  declared_at: string | null;
  declared_lat: number | null;
  declared_lon: number | null;
  description: string;
  location_note?: string | null;
}

export interface Contribution {
  id: number;
  code: string;
  case_id: number;
  case_code: string;
  case_title: string;
  type: "VIDEO" | "FOTO" | "DOCUMENTO" | "TEXTO";
  certainty: "BAJA" | "MEDIA" | "ALTA";
  status: string;
  classification: string | null;
  created_at: string;
  original: ContributionValues;
  effective: ContributionValues;
  corrections: Correction[];
  file: FileInfo | null;
  contributor_alias?: string;
  observations?: { id: number; text: string; author: string; created_at: string }[];
  distance_km?: number | null;
  time_diff_h?: number | null;
  data_quality?: string[];
  duplicate_of_code?: string;
  case?: { id: number; code: string; title: string; incident_at: string; zone: string; private_lat: number | null; private_lon: number | null };
}

export interface Notification {
  id: number;
  title: string;
  body: string;
  link: string | null;
  created_at: string;
  read: boolean;
}

export interface ReportSummary {
  id: number;
  code: string;
  case_id: number;
  case_code?: string;
  title: string;
  created_at: string;
  created_by: string | null;
  content_sha256: string;
  export_count: number;
}

export interface ReportEvidence {
  code: string;
  type: string;
  status: string;
  classification: string | null;
  declared_certainty: string;
  description: string;
  declared_at: string | null;
  declared_at_original: string | null;
  received_at: string;
  distance_km_approx: number | null;
  time_diff_h: number | null;
  corrections: { field: string; old_value: string | null; new_value: string | null; reason: string; at: string }[];
  observations: { text: string; author: string; at: string }[];
  file: { sha256: string; type: string; size_bytes: number; status: string; antivirus_engine: string; scanned_at: string; received_at: string } | null;
  declared_location?: { lat: number | null; lon: number | null; note: string | null };
}

export interface ReportFull extends ReportSummary {
  content: {
    report_code: string;
    demo_mode: boolean;
    generated_at: string;
    generated_by: { name: string; role: string };
    title: string;
    summary: string;
    disclaimer: string;
    case: {
      code: string;
      category: string;
      subcategory: string | null;
      sensitivity: string;
      status: string;
      publication_status: string;
      title: string;
      zone: string;
      incident_at_declared: string;
      incident_local: string;
      specific_fields: Record<string, unknown>;
      supporting_documents: { type: string; sha256: string; file_status: string; review_status: string }[];
      private_location?: { lat: number | null; lon: number | null; note: string | null };
    };
    evidence: ReportEvidence[];
    history: { event: string; detail: string; at: string; actor: string }[];
  };
}
