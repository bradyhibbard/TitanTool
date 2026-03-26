/**
 * Presets page — manage global cost/time presets for all symbol types.
 */
import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Plus, BookOpen } from 'lucide-react'
import { getPresets, upsertPreset } from '../api/client'
import PresetEditor from '../components/PresetEditor'
import Spinner from '../components/Spinner'

export default function Presets() {
  const qc = useQueryClient()
  const { data: presets = [], isLoading } = useQuery({
    queryKey: ['presets'],
    queryFn: getPresets,
  })

  const [showNew, setShowNew] = useState(false)
  const [newName, setNewName] = useState('')

  const createMut = useMutation({
    mutationFn: () => {
      const slug = newName.trim().toLowerCase().replace(/\s+/g, '_').replace(/[^a-z0-9_]/g, '')
      return upsertPreset(slug, {
        symbol_name: newName.trim(),
        material_cost: 0,
        labor_cost: 0,
        install_minutes: 0,
        notes: '',
      })
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['presets'] })
      setNewName('')
      setShowNew(false)
    },
  })

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Symbol Presets</h1>
          <p className="text-sm text-gray-500 mt-1">
            Set material cost, labor cost, and install time for each symbol type.
            These apply across all projects.
          </p>
        </div>
        <button className="btn-primary" onClick={() => setShowNew(s => !s)}>
          <Plus size={15} /> Add Symbol
        </button>
      </div>

      {/* New symbol form */}
      {showNew && (
        <div className="card p-4 border-2 border-titan-200 space-y-3">
          <h3 className="font-semibold text-gray-800">New Symbol Preset</h3>
          <div className="flex gap-3">
            <input
              className="input flex-1"
              placeholder="Symbol name (e.g. Bath Fan)"
              value={newName}
              onChange={e => setNewName(e.target.value)}
              autoFocus
            />
            <button
              className="btn-primary"
              onClick={() => createMut.mutate()}
              disabled={!newName.trim() || createMut.isPending}
            >
              {createMut.isPending ? <Spinner className="text-white" /> : <Plus size={15} />}
              Create
            </button>
            <button className="btn-secondary" onClick={() => setShowNew(false)}>Cancel</button>
          </div>
        </div>
      )}

      {isLoading && (
        <div className="flex justify-center py-12">
          <Spinner className="text-titan-600 w-8 h-8" />
        </div>
      )}

      {!isLoading && presets.length === 0 && (
        <div className="card p-12 text-center text-gray-400">
          <BookOpen size={40} className="mx-auto mb-3 text-gray-300" />
          <p className="font-medium">No presets yet.</p>
          <p className="text-sm mt-1">
            Presets are created automatically when detection runs.<br />
            You can also add them manually above.
          </p>
        </div>
      )}

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {presets.map(preset => (
          <PresetEditor key={preset.id} preset={preset} />
        ))}
      </div>

      {/* Learning stats teaser */}
      <div className="card p-4 bg-gradient-to-r from-titan-50 to-blue-50 border-titan-200">
        <h3 className="font-semibold text-titan-800 mb-1 text-sm">Model Learning</h3>
        <p className="text-xs text-titan-700">
          Every time you mark a detection as Correct or Incorrect on the results page,
          TitanTool saves a training sample. Over time, this data will be used to fine-tune
          the symbol recognition model for your specific plan style.
        </p>
      </div>
    </div>
  )
}
