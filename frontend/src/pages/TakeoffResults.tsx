/**
 * TakeoffResults page
 *
 * Shows:
 *  - Floor plan image with detection overlays (interactive canvas)
 *  - Per-symbol count table with cost/time from presets
 *  - Grand total cost + hours
 *  - CSV export
 *  - Per-match feedback buttons (accept/reject for learning)
 */
import { useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { useMutation, useQuery } from '@tanstack/react-query'
import { ChevronRight, Download, ThumbsDown, ThumbsUp, Clock, DollarSign } from 'lucide-react'
import {
  getProject, getResults, getTakeoff, getJobs, submitFeedback,
} from '../api/client'
import type { Match, SymbolResult } from '../api/client'
import DetectionOverlay from '../components/DetectionOverlay'
import Spinner from '../components/Spinner'

export default function TakeoffResults() {
  const { id } = useParams<{ id: string }>()

  const { data: project } = useQuery({ queryKey: ['project', id], queryFn: () => getProject(id!) })
  const { data: results = [], isLoading: resultsLoading } = useQuery({
    queryKey: ['results', id], queryFn: () => getResults(id!),
  })
  const { data: takeoff } = useQuery({
    queryKey: ['takeoff', id], queryFn: () => getTakeoff(id!),
  })
  const { data: jobs = [] } = useQuery({
    queryKey: ['jobs', id], queryFn: () => getJobs(id!),
  })

  const latestJob = jobs[0]
  const [selectedMatch, setSelectedMatch] = useState<{
    result: SymbolResult; match: Match; idx: number
  } | null>(null)

  const feedbackMut = useMutation({
    mutationFn: ({ resultId, match, decision }: {
      resultId: string; match: Match; decision: 'accept' | 'reject'
    }) =>
      submitFeedback(resultId, {
        bbox: Array.from(match.bbox),
        decision,
        combined_score: match.combined_score,
        binary_score: match.binary_score,
        edge_score: match.edge_score,
        iou_score: match.iou_score,
      }),
    onSuccess: () => setSelectedMatch(null),
  })

  const pageImageUrl = latestJob ? `/api/images/page/${id}/${latestJob.id}` : ''

  if (resultsLoading) {
    return <div className="flex justify-center py-20"><Spinner className="text-titan-600 w-8 h-8" /></div>
  }

  return (
    <div className="space-y-6">
      {/* Breadcrumb */}
      <div className="flex items-center gap-2 text-sm text-gray-500">
        <Link to="/" className="hover:text-titan-600">Projects</Link>
        <ChevronRight size={14} />
        <Link to={`/projects/${id}`} className="hover:text-titan-600">{project?.name}</Link>
        <ChevronRight size={14} />
        <span className="text-gray-900 font-medium">Results</span>
      </div>

      <div className="flex items-center justify-between flex-wrap gap-3">
        <h1 className="text-2xl font-bold text-gray-900">Takeoff Results</h1>
        <div className="flex gap-2">
          <a
            href={`/api/projects/${id}/takeoff/export`}
            target="_blank"
            rel="noreferrer"
            className="btn-secondary"
          >
            <Download size={15} /> Export CSV
          </a>
          <Link to={`/projects/${id}`} className="btn-secondary">
            Back to Project
          </Link>
        </div>
      </div>

      <div className="grid lg:grid-cols-2 gap-6">
        {/* Left — floor plan with overlays */}
        <div className="space-y-3">
          <h2 className="font-semibold text-gray-700">Floor Plan — Detected Symbols</h2>
          {pageImageUrl && results.length > 0 ? (
            <DetectionOverlay
              imageUrl={pageImageUrl}
              results={results}
              onMatchClick={(result, match, idx) => setSelectedMatch({ result, match, idx })}
            />
          ) : (
            <div className="card p-10 text-center text-gray-400">
              No detection results to display.
            </div>
          )}
          <p className="text-xs text-gray-400">Click a bounding box to review a detection.</p>
        </div>

        {/* Right — counts + costs table */}
        <div className="space-y-4">
          {/* Summary cards */}
          {takeoff && (
            <div className="grid grid-cols-2 gap-3">
              <div className="card p-4 text-center">
                <div className="flex items-center justify-center gap-1.5 text-titan-600 mb-1">
                  <DollarSign size={18} />
                  <span className="text-xs font-medium text-gray-500">Total Cost</span>
                </div>
                <p className="text-2xl font-bold text-gray-900">
                  ${takeoff.grand_total_cost.toLocaleString(undefined, { minimumFractionDigits: 2 })}
                </p>
              </div>
              <div className="card p-4 text-center">
                <div className="flex items-center justify-center gap-1.5 text-green-600 mb-1">
                  <Clock size={18} />
                  <span className="text-xs font-medium text-gray-500">Total Hours</span>
                </div>
                <p className="text-2xl font-bold text-gray-900">{takeoff.grand_total_hours.toFixed(1)} h</p>
              </div>
            </div>
          )}

          {/* Per-symbol table */}
          <div className="card overflow-hidden">
            <table className="w-full text-sm">
              <thead className="bg-gray-50 border-b border-gray-200">
                <tr>
                  <th className="text-left px-4 py-2.5 font-semibold text-gray-600">Symbol</th>
                  <th className="text-center px-3 py-2.5 font-semibold text-gray-600">Count</th>
                  <th className="text-right px-4 py-2.5 font-semibold text-gray-600">Total $</th>
                  <th className="text-right px-4 py-2.5 font-semibold text-gray-600">Hrs</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {takeoff?.items.map(item => (
                  <tr key={item.symbol_slug} className="hover:bg-gray-50 transition-colors">
                    <td className="px-4 py-2.5 font-medium text-gray-800">{item.symbol_name}</td>
                    <td className="px-3 py-2.5 text-center">
                      <span className="badge bg-titan-100 text-titan-700 font-bold">
                        {item.match_count}
                      </span>
                    </td>
                    <td className="px-4 py-2.5 text-right text-gray-700">
                      {item.total_cost > 0 ? `$${item.total_cost.toFixed(2)}` : '—'}
                    </td>
                    <td className="px-4 py-2.5 text-right text-gray-700">
                      {item.total_hours > 0 ? `${item.total_hours.toFixed(1)}` : '—'}
                    </td>
                  </tr>
                ))}
                {(!takeoff || takeoff.items.length === 0) && (
                  <tr>
                    <td colSpan={4} className="px-4 py-6 text-center text-gray-400">
                      No results yet.
                    </td>
                  </tr>
                )}
              </tbody>
              {takeoff && takeoff.items.length > 0 && (
                <tfoot className="bg-gray-50 border-t-2 border-gray-200">
                  <tr>
                    <td className="px-4 py-2.5 font-bold text-gray-800">Total</td>
                    <td className="px-3 py-2.5 text-center font-bold text-gray-800">
                      {takeoff.items.reduce((s, i) => s + i.match_count, 0)}
                    </td>
                    <td className="px-4 py-2.5 text-right font-bold text-gray-800">
                      ${takeoff.grand_total_cost.toFixed(2)}
                    </td>
                    <td className="px-4 py-2.5 text-right font-bold text-gray-800">
                      {takeoff.grand_total_hours.toFixed(1)}
                    </td>
                  </tr>
                </tfoot>
              )}
            </table>
          </div>

          {/* Preset hint */}
          {takeoff && takeoff.items.some(i => i.total_cost === 0) && (
            <p className="text-xs text-amber-600 bg-amber-50 border border-amber-200 rounded-lg px-3 py-2">
              Some symbols have no cost preset.{' '}
              <Link to="/presets" className="underline font-medium">Configure presets →</Link>
            </p>
          )}
        </div>
      </div>

      {/* Match review panel (shown when a box is clicked) */}
      {selectedMatch && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
          <div className="card p-5 max-w-sm w-full space-y-4">
            <h3 className="font-semibold text-gray-800">Review Detection</h3>
            <p className="text-sm text-gray-500">
              <span className="font-medium">{selectedMatch.result.symbol_name}</span> — match #{selectedMatch.idx + 1}
            </p>
            <div className="grid grid-cols-2 gap-2 text-xs text-gray-500">
              <div>Combined: <span className="font-mono font-semibold text-gray-700">{selectedMatch.match.combined_score.toFixed(3)}</span></div>
              <div>Binary: <span className="font-mono font-semibold text-gray-700">{selectedMatch.match.binary_score.toFixed(3)}</span></div>
              <div>Edge: <span className="font-mono font-semibold text-gray-700">{selectedMatch.match.edge_score.toFixed(3)}</span></div>
              <div>IoU: <span className="font-mono font-semibold text-gray-700">{selectedMatch.match.iou_score.toFixed(3)}</span></div>
            </div>
            <p className="text-xs text-gray-400">
              Your feedback trains the model to improve future detections.
            </p>
            <div className="flex gap-2">
              <button
                className="flex-1 btn bg-red-50 text-red-600 border border-red-200 hover:bg-red-100 focus:ring-red-500"
                onClick={() =>
                  feedbackMut.mutate({
                    resultId: selectedMatch.result.id,
                    match: selectedMatch.match,
                    decision: 'reject',
                  })
                }
                disabled={feedbackMut.isPending}
              >
                <ThumbsDown size={15} /> Incorrect
              </button>
              <button
                className="flex-1 btn bg-green-50 text-green-600 border border-green-200 hover:bg-green-100 focus:ring-green-500"
                onClick={() =>
                  feedbackMut.mutate({
                    resultId: selectedMatch.result.id,
                    match: selectedMatch.match,
                    decision: 'accept',
                  })
                }
                disabled={feedbackMut.isPending}
              >
                <ThumbsUp size={15} /> Correct
              </button>
            </div>
            <button
              className="w-full btn-secondary text-xs"
              onClick={() => setSelectedMatch(null)}
            >
              Skip
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
