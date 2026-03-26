/**
 * PresetEditor
 *
 * Inline editor for a single symbol cost/time preset.
 */
import { useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { Save, Trash2 } from 'lucide-react'
import { upsertPreset, deletePreset } from '../api/client'
import type { SymbolPreset } from '../api/client'

interface Props {
  preset: SymbolPreset
  onDelete?: () => void
}

export default function PresetEditor({ preset, onDelete }: Props) {
  const qc = useQueryClient()
  const [form, setForm] = useState({
    symbol_name: preset.symbol_name,
    material_cost: preset.material_cost,
    labor_cost: preset.labor_cost,
    install_minutes: preset.install_minutes,
    notes: preset.notes,
  })
  const [dirty, setDirty] = useState(false)

  const saveMut = useMutation({
    mutationFn: () => upsertPreset(preset.symbol_slug, form),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['presets'] })
      setDirty(false)
    },
  })

  const deleteMut = useMutation({
    mutationFn: () => deletePreset(preset.symbol_slug),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['presets'] })
      onDelete?.()
    },
  })

  function set(field: keyof typeof form, value: string | number) {
    setForm(f => ({ ...f, [field]: value }))
    setDirty(true)
  }

  return (
    <div className="card p-4 space-y-3">
      <div className="flex items-center justify-between gap-2">
        <input
          className="input font-semibold"
          value={form.symbol_name}
          onChange={e => set('symbol_name', e.target.value)}
          placeholder="Symbol name"
        />
        <span className="text-xs text-gray-400 whitespace-nowrap font-mono">{preset.symbol_slug}</span>
      </div>

      <div className="grid grid-cols-3 gap-3">
        <label className="space-y-1">
          <span className="text-xs text-gray-500 font-medium">Material $</span>
          <input
            type="number" min="0" step="0.01"
            className="input"
            value={form.material_cost}
            onChange={e => set('material_cost', parseFloat(e.target.value) || 0)}
          />
        </label>
        <label className="space-y-1">
          <span className="text-xs text-gray-500 font-medium">Labor $</span>
          <input
            type="number" min="0" step="0.01"
            className="input"
            value={form.labor_cost}
            onChange={e => set('labor_cost', parseFloat(e.target.value) || 0)}
          />
        </label>
        <label className="space-y-1">
          <span className="text-xs text-gray-500 font-medium">Install (min)</span>
          <input
            type="number" min="0" step="1"
            className="input"
            value={form.install_minutes}
            onChange={e => set('install_minutes', parseFloat(e.target.value) || 0)}
          />
        </label>
      </div>

      <label className="space-y-1 block">
        <span className="text-xs text-gray-500 font-medium">Notes</span>
        <input
          className="input"
          value={form.notes}
          onChange={e => set('notes', e.target.value)}
          placeholder="Optional notes"
        />
      </label>

      <div className="flex items-center justify-between">
        <button
          className="btn-danger text-xs px-3 py-1.5"
          onClick={() => deleteMut.mutate()}
          disabled={deleteMut.isPending}
        >
          <Trash2 size={13} /> Delete
        </button>
        <button
          className="btn-primary text-xs px-3 py-1.5"
          onClick={() => saveMut.mutate()}
          disabled={!dirty || saveMut.isPending}
        >
          <Save size={13} /> Save
        </button>
      </div>
    </div>
  )
}
