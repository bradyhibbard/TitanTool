/**
 * LegendManager
 *
 * Shows the electrical legend image with the auto-detected symbol icons
 * overlaid. The user can toggle each symbol on/off and rename it.
 * Changes are sent to the backend via PATCH /api/legend/{id}.
 */
import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ToggleLeft, ToggleRight, Edit2, Check, X } from 'lucide-react'
import { getLegendEntries, updateLegendEntry } from '../api/client'
import type { LegendEntry } from '../api/client'
import Spinner from './Spinner'

interface Props {
  projectId: string
  jobId: string
  legendImageUrl: string
}

export default function LegendManager({ projectId, jobId, legendImageUrl }: Props) {
  const qc = useQueryClient()
  const { data: entries = [], isLoading } = useQuery({
    queryKey: ['legend', projectId],
    queryFn: () => getLegendEntries(projectId),
  })

  const patchMut = useMutation({
    mutationFn: ({ id, patch }: { id: string; patch: Parameters<typeof updateLegendEntry>[1] }) =>
      updateLegendEntry(id, patch),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['legend', projectId] }),
  })

  const [editing, setEditing] = useState<string | null>(null)
  const [editName, setEditName] = useState('')

  if (isLoading) return <Spinner />

  return (
    <div className="space-y-4">
      <div className="rounded-lg border border-gray-200 overflow-hidden">
        <img src={legendImageUrl} alt="Electrical legend" className="w-full" />
      </div>

      <div className="space-y-2">
        <h3 className="text-sm font-semibold text-gray-700">Detected Symbols</h3>
        {entries.length === 0 && (
          <p className="text-sm text-gray-500">No symbols detected yet. Run detection first.</p>
        )}
        {entries.map(entry => (
          <div
            key={entry.id}
            className="flex items-center gap-3 px-3 py-2 rounded-lg border border-gray-200 bg-white"
          >
            {/* Toggle */}
            <button
              onClick={() => patchMut.mutate({ id: entry.id, patch: { enabled: !entry.enabled } })}
              className="shrink-0 text-gray-400 hover:text-titan-600 transition-colors"
              title={entry.enabled ? 'Disable' : 'Enable'}
            >
              {entry.enabled
                ? <ToggleRight size={22} className="text-titan-600" />
                : <ToggleLeft size={22} />}
            </button>

            {/* Name */}
            {editing === entry.id ? (
              <div className="flex flex-1 items-center gap-2">
                <input
                  className="input flex-1"
                  value={editName}
                  onChange={e => setEditName(e.target.value)}
                  autoFocus
                />
                <button
                  className="text-green-600 hover:text-green-700"
                  onClick={() => {
                    patchMut.mutate({ id: entry.id, patch: { symbol_name: editName } })
                    setEditing(null)
                  }}
                ><Check size={16} /></button>
                <button
                  className="text-red-500 hover:text-red-600"
                  onClick={() => setEditing(null)}
                ><X size={16} /></button>
              </div>
            ) : (
              <span className="flex-1 text-sm font-medium text-gray-800">{entry.symbol_name}</span>
            )}

            {/* Edit button */}
            {editing !== entry.id && (
              <button
                onClick={() => { setEditing(entry.id); setEditName(entry.symbol_name) }}
                className="shrink-0 text-gray-400 hover:text-titan-600 transition-colors"
              ><Edit2 size={14} /></button>
            )}

            {/* Template preview */}
            {entry.template_path && (
              <img
                src={`/output/${projectId}/${entry.symbol_slug}/template.png`}
                alt={entry.symbol_name}
                className="w-8 h-8 object-contain border border-gray-200 rounded bg-white"
                onError={e => { (e.target as HTMLImageElement).style.display = 'none' }}
              />
            )}
          </div>
        ))}
      </div>
    </div>
  )
}
