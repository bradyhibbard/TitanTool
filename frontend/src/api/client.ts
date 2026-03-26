import axios from 'axios'

const api = axios.create({ baseURL: '/api' })

// ── Types ────────────────────────────────────────────────────────────────────

export interface Project {
  id: string
  name: string
  description: string
  pdf_filename: string | null
  page_count: number
  status: 'created' | 'ready' | 'detecting' | 'done' | 'error'
  created_at: string
  updated_at: string
}

export interface DetectionJob {
  id: string
  project_id: string
  page_index: number
  status: 'pending' | 'running' | 'done' | 'error'
  error_message: string | null
  page_image_path: string | null
  legend_crop_path: string | null
  legend_bbox: [number, number, number, number] | null
  plan_bbox: [number, number, number, number] | null
  started_at: string | null
  finished_at: string | null
  created_at: string
}

export interface SymbolResult {
  id: string
  job_id: string
  project_id: string
  symbol_name: string
  symbol_slug: string
  template_path: string | null
  matches: Match[]
  match_count: number
  debug_matches_image_path: string | null
  created_at: string
}

export interface Match {
  bbox: [number, number, number, number]
  combined_score: number
  binary_score: number
  edge_score: number
  iou_score: number
  density_score: number
  contour_score: number
  decision_source: string
  template_rotation: number
}

export interface SymbolPreset {
  id: string
  symbol_slug: string
  symbol_name: string
  material_cost: number
  labor_cost: number
  install_minutes: number
  notes: string
  updated_at: string
}

export interface LegendEntry {
  id: string
  project_id: string
  job_id: string
  symbol_name: string
  symbol_slug: string
  icon_bbox_in_legend: [number, number, number, number] | null
  template_path: string | null
  enabled: boolean
  detection_overrides: Record<string, unknown>
}

export interface TakeoffSummaryItem {
  symbol_name: string
  symbol_slug: string
  match_count: number
  material_cost: number
  labor_cost: number
  install_minutes: number
  total_cost: number
  total_hours: number
}

export interface TakeoffSummary {
  project_id: string
  project_name: string
  page_index: number
  items: TakeoffSummaryItem[]
  grand_total_cost: number
  grand_total_hours: number
}

// ── Projects ─────────────────────────────────────────────────────────────────

export const getProjects = () => api.get<Project[]>('/projects').then(r => r.data)

export const getProject = (id: string) =>
  api.get<Project>(`/projects/${id}`).then(r => r.data)

export const createProject = (name: string, description = '') =>
  api.post<Project>('/projects', { name, description }).then(r => r.data)

export const deleteProject = (id: string) =>
  api.delete(`/projects/${id}`).then(r => r.data)

export const uploadPdf = (projectId: string, file: File) => {
  const form = new FormData()
  form.append('file', file)
  return api.post<Project>(`/projects/${projectId}/upload`, form, {
    headers: { 'Content-Type': 'multipart/form-data' },
  }).then(r => r.data)
}

// ── Detection jobs ────────────────────────────────────────────────────────────

export const startDetection = (projectId: string, pageIndex = 0) =>
  api.post<DetectionJob>(`/projects/${projectId}/detect`, {
    page_index: pageIndex,
    skip_review: true,
  }).then(r => r.data)

export const getJob = (jobId: string) =>
  api.get<DetectionJob>(`/jobs/${jobId}`).then(r => r.data)

export const getJobs = (projectId: string) =>
  api.get<DetectionJob[]>(`/projects/${projectId}/jobs`).then(r => r.data)

// ── Results ───────────────────────────────────────────────────────────────────

export const getResults = (projectId: string) =>
  api.get<SymbolResult[]>(`/projects/${projectId}/results`).then(r => r.data)

// ── Legend entries ────────────────────────────────────────────────────────────

export const getLegendEntries = (projectId: string) =>
  api.get<LegendEntry[]>(`/projects/${projectId}/legend`).then(r => r.data)

export const updateLegendEntry = (
  entryId: string,
  patch: { enabled?: boolean; symbol_name?: string; detection_overrides?: Record<string, unknown> },
) => api.patch<LegendEntry>(`/legend/${entryId}`, patch).then(r => r.data)

// ── Presets ───────────────────────────────────────────────────────────────────

export const getPresets = () => api.get<SymbolPreset[]>('/presets').then(r => r.data)

export const upsertPreset = (
  slug: string,
  data: Omit<SymbolPreset, 'id' | 'symbol_slug' | 'updated_at'>,
) => api.put<SymbolPreset>(`/presets/${slug}`, data).then(r => r.data)

export const deletePreset = (slug: string) =>
  api.delete(`/presets/${slug}`).then(r => r.data)

// ── Takeoff summary ───────────────────────────────────────────────────────────

export const getTakeoff = (projectId: string) =>
  api.get<TakeoffSummary>(`/projects/${projectId}/takeoff`).then(r => r.data)

export const exportTakeoffCsv = (projectId: string) => {
  window.open(`/api/projects/${projectId}/takeoff/export`, '_blank')
}

// ── Feedback ──────────────────────────────────────────────────────────────────

export const submitFeedback = (
  resultId: string,
  feedback: {
    bbox: number[]
    decision: 'accept' | 'reject'
    combined_score?: number
    binary_score?: number
    edge_score?: number
    iou_score?: number
  },
) => api.post(`/results/${resultId}/feedback`, feedback).then(r => r.data)

// ── Learning stats ────────────────────────────────────────────────────────────

export const getLearningStats = () =>
  api.get('/learning/stats').then(r => r.data)
