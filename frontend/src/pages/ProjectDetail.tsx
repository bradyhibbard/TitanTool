/**
 * ProjectDetail page
 *
 * Workflow:
 *   1. Upload PDF
 *   2. Select page → run detection
 *   3. Review legend entries (enable/disable, rename)
 *   4. View results → navigate to TakeoffResults
 */
import { useRef, useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  Upload, Play, ChevronRight, AlertCircle, RefreshCw, FileText
} from 'lucide-react'
import {
  getProject, uploadPdf, startDetection, getJob, getJobs, getLegendEntries,
} from '../api/client'
import StatusBadge from '../components/StatusBadge'
import LegendManager from '../components/LegendManager'
import Spinner from '../components/Spinner'

export default function ProjectDetail() {
  const { id } = useParams<{ id: string }>()
  const qc = useQueryClient()
  const fileRef = useRef<HTMLInputElement>(null)
  const [pageIndex, setPageIndex] = useState(0)

  const { data: project, isLoading: projLoading } = useQuery({
    queryKey: ['project', id],
    queryFn: () => getProject(id!),
    refetchInterval: 3000,
  })

  const { data: jobs = [] } = useQuery({
    queryKey: ['jobs', id],
    queryFn: () => getJobs(id!),
    refetchInterval: 3000,
    enabled: !!id,
  })

  const latestJob = jobs[0]
  const isDetecting = project?.status === 'detecting' || latestJob?.status === 'running' || latestJob?.status === 'pending'

  const uploadMut = useMutation({
    mutationFn: (file: File) => uploadPdf(id!, file),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['project', id] }),
  })

  const detectMut = useMutation({
    mutationFn: () => startDetection(id!, pageIndex),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['jobs', id] }),
  })

  if (projLoading) {
    return <div className="flex justify-center py-20"><Spinner className="text-titan-600 w-8 h-8" /></div>
  }

  if (!project) {
    return <div className="text-center py-20 text-gray-500">Project not found.</div>
  }

  return (
    <div className="space-y-6">
      {/* Breadcrumb */}
      <div className="flex items-center gap-2 text-sm text-gray-500">
        <Link to="/" className="hover:text-titan-600">Projects</Link>
        <ChevronRight size={14} />
        <span className="text-gray-900 font-medium">{project.name}</span>
      </div>

      {/* Header */}
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">{project.name}</h1>
          {project.description && <p className="text-sm text-gray-500 mt-1">{project.description}</p>}
        </div>
        <StatusBadge status={project.status} className="text-sm px-3 py-1" />
      </div>

      {/* Step 1 — Upload PDF */}
      <section className="card p-5 space-y-4">
        <h2 className="font-semibold text-gray-800 flex items-center gap-2">
          <span className="w-6 h-6 rounded-full bg-titan-600 text-white text-xs flex items-center justify-center font-bold">1</span>
          Upload Floor Plan PDF
        </h2>

        {project.pdf_filename ? (
          <div className="flex items-center gap-3 text-sm text-gray-700">
            <FileText size={18} className="text-titan-600 shrink-0" />
            <span className="font-medium">{project.pdf_filename}</span>
            <span className="text-gray-400">· {project.page_count} page{project.page_count !== 1 ? 's' : ''}</span>
            <button
              className="ml-auto btn-secondary text-xs px-2 py-1"
              onClick={() => fileRef.current?.click()}
            >
              Replace
            </button>
          </div>
        ) : (
          <button
            className="w-full border-2 border-dashed border-gray-300 rounded-xl py-10 flex flex-col items-center gap-2 text-gray-400 hover:border-titan-400 hover:text-titan-600 transition-colors"
            onClick={() => fileRef.current?.click()}
            disabled={uploadMut.isPending}
          >
            {uploadMut.isPending ? <Spinner className="text-titan-600" /> : <Upload size={28} />}
            <span className="text-sm font-medium">
              {uploadMut.isPending ? 'Uploading…' : 'Click to upload PDF'}
            </span>
          </button>
        )}

        <input
          ref={fileRef}
          type="file"
          accept=".pdf"
          className="hidden"
          onChange={e => {
            const file = e.target.files?.[0]
            if (file) uploadMut.mutate(file)
            e.target.value = ''
          }}
        />
      </section>

      {/* Step 2 — Run Detection */}
      {project.pdf_path && (
        <section className="card p-5 space-y-4">
          <h2 className="font-semibold text-gray-800 flex items-center gap-2">
            <span className="w-6 h-6 rounded-full bg-titan-600 text-white text-xs flex items-center justify-center font-bold">2</span>
            Run Symbol Detection
          </h2>

          <div className="flex flex-wrap items-end gap-3">
            <label className="space-y-1">
              <span className="text-xs font-medium text-gray-600">Page to analyze</span>
              <select
                className="input pr-8"
                value={pageIndex}
                onChange={e => setPageIndex(Number(e.target.value))}
              >
                {Array.from({ length: project.page_count || 1 }, (_, i) => (
                  <option key={i} value={i}>Page {i + 1}</option>
                ))}
              </select>
            </label>

            <button
              className="btn-primary"
              onClick={() => detectMut.mutate()}
              disabled={isDetecting || detectMut.isPending}
            >
              {isDetecting
                ? <><Spinner className="text-white" /> Detecting…</>
                : <><Play size={15} /> {latestJob?.status === 'done' ? 'Re-run Detection' : 'Start Detection'}</>
              }
            </button>

            {project.status === 'done' && (
              <Link to={`/projects/${id}/results`} className="btn-secondary">
                View Results <ChevronRight size={15} />
              </Link>
            )}
          </div>

          {/* Job status */}
          {latestJob && (
            <div className={`rounded-lg px-4 py-3 text-sm flex items-start gap-2 ${
              latestJob.status === 'error' ? 'bg-red-50 text-red-700 border border-red-200' :
              latestJob.status === 'done' ? 'bg-green-50 text-green-700 border border-green-200' :
              'bg-blue-50 text-blue-700 border border-blue-200'
            }`}>
              {latestJob.status === 'error' && <AlertCircle size={16} className="shrink-0 mt-0.5" />}
              {latestJob.status === 'running' && <Spinner className="shrink-0 mt-0.5" />}
              <div>
                <p className="font-medium">
                  {latestJob.status === 'error' ? 'Detection failed' :
                   latestJob.status === 'running' ? 'Detection in progress…' :
                   latestJob.status === 'done' ? 'Detection complete!' :
                   'Detection queued'}
                </p>
                {latestJob.error_message && (
                  <p className="text-xs mt-1 font-mono opacity-80">{latestJob.error_message}</p>
                )}
              </div>
            </div>
          )}
        </section>
      )}

      {/* Step 3 — Legend review */}
      {latestJob && (latestJob.status === 'running' || latestJob.status === 'done') && latestJob.legend_crop_path && (
        <section className="card p-5 space-y-4">
          <h2 className="font-semibold text-gray-800 flex items-center gap-2">
            <span className="w-6 h-6 rounded-full bg-titan-600 text-white text-xs flex items-center justify-center font-bold">3</span>
            Review Legend Symbols
          </h2>
          <p className="text-sm text-gray-500">
            Enable or disable symbols to control what gets counted. You can also rename them.
          </p>
          <LegendManager
            projectId={id!}
            jobId={latestJob.id}
            legendImageUrl={`/api/images/legend/${id}/${latestJob.id}`}
          />
        </section>
      )}

      {/* Go to results */}
      {project.status === 'done' && (
        <div className="flex justify-end">
          <Link to={`/projects/${id}/results`} className="btn-primary px-6 py-2.5">
            View Takeoff Results <ChevronRight size={16} />
          </Link>
        </div>
      )}
    </div>
  )
}
