/**
 * Home page — project list + create new project
 */
import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Plus, Trash2, ChevronRight, FileText, Zap } from 'lucide-react'
import { createProject, deleteProject, getProjects } from '../api/client'
import StatusBadge from '../components/StatusBadge'
import Spinner from '../components/Spinner'

export default function Home() {
  const qc = useQueryClient()
  const { data: projects = [], isLoading } = useQuery({
    queryKey: ['projects'],
    queryFn: getProjects,
    refetchInterval: 5000,
  })

  const [name, setName] = useState('')
  const [desc, setDesc] = useState('')
  const [showForm, setShowForm] = useState(false)

  const createMut = useMutation({
    mutationFn: () => createProject(name.trim(), desc.trim()),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['projects'] })
      setName(''); setDesc(''); setShowForm(false)
    },
  })

  const deleteMut = useMutation({
    mutationFn: (id: string) => deleteProject(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['projects'] }),
  })

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Projects</h1>
          <p className="text-sm text-gray-500 mt-1">Each project is one set of floor plans.</p>
        </div>
        <button className="btn-primary" onClick={() => setShowForm(s => !s)}>
          <Plus size={16} /> New Project
        </button>
      </div>

      {/* Create form */}
      {showForm && (
        <div className="card p-5 space-y-4 border-titan-200 border-2">
          <h2 className="font-semibold text-gray-800">New Project</h2>
          <div className="space-y-3">
            <label className="space-y-1 block">
              <span className="text-xs font-medium text-gray-600">Project name *</span>
              <input
                className="input"
                placeholder="e.g. 123 Main St — Residential"
                value={name}
                onChange={e => setName(e.target.value)}
                autoFocus
              />
            </label>
            <label className="space-y-1 block">
              <span className="text-xs font-medium text-gray-600">Description</span>
              <input
                className="input"
                placeholder="Optional notes"
                value={desc}
                onChange={e => setDesc(e.target.value)}
              />
            </label>
          </div>
          <div className="flex gap-2 justify-end">
            <button className="btn-secondary" onClick={() => setShowForm(false)}>Cancel</button>
            <button
              className="btn-primary"
              onClick={() => createMut.mutate()}
              disabled={!name.trim() || createMut.isPending}
            >
              {createMut.isPending ? <Spinner className="text-white" /> : <Plus size={15} />}
              Create
            </button>
          </div>
        </div>
      )}

      {/* List */}
      {isLoading && (
        <div className="flex justify-center py-12">
          <Spinner className="text-titan-600 w-8 h-8" />
        </div>
      )}

      {!isLoading && projects.length === 0 && (
        <div className="card p-12 text-center text-gray-400">
          <Zap size={40} className="mx-auto mb-3 text-gray-300" />
          <p className="font-medium">No projects yet.</p>
          <p className="text-sm mt-1">Create your first project to start a takeoff.</p>
        </div>
      )}

      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {projects.map(project => (
          <div key={project.id} className="card p-4 flex flex-col gap-3 hover:shadow-md transition-shadow">
            <div className="flex items-start justify-between gap-2">
              <div className="flex-1 min-w-0">
                <h3 className="font-semibold text-gray-900 truncate">{project.name}</h3>
                {project.description && (
                  <p className="text-xs text-gray-500 mt-0.5 truncate">{project.description}</p>
                )}
              </div>
              <StatusBadge status={project.status} />
            </div>

            {project.pdf_filename && (
              <div className="flex items-center gap-1.5 text-xs text-gray-500">
                <FileText size={13} />
                <span className="truncate">{project.pdf_filename}</span>
                {project.page_count > 0 && (
                  <span className="shrink-0">· {project.page_count} page{project.page_count !== 1 ? 's' : ''}</span>
                )}
              </div>
            )}

            <div className="flex items-center justify-between mt-auto pt-2 border-t border-gray-100">
              <button
                className="text-xs text-red-500 hover:text-red-700 flex items-center gap-1 transition-colors"
                onClick={() => {
                  if (confirm(`Delete "${project.name}"?`)) deleteMut.mutate(project.id)
                }}
              >
                <Trash2 size={13} /> Delete
              </button>
              <Link
                to={`/projects/${project.id}`}
                className="btn-primary text-xs px-3 py-1.5"
              >
                Open <ChevronRight size={13} />
              </Link>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
