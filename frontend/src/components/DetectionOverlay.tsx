/**
 * DetectionOverlay
 *
 * Renders a floor-plan image with colored bounding boxes for each detected
 * symbol. Clicking a box highlights it and fires onMatchClick.
 */
import { useRef, useEffect, useState } from 'react'
import type { Match, SymbolResult } from '../api/client'

// One color per symbol (cycles if more than COLORS.length)
const COLORS = [
  '#ef4444', '#3b82f6', '#22c55e', '#f59e0b',
  '#8b5cf6', '#ec4899', '#06b6d4', '#84cc16',
]

interface Props {
  imageUrl: string
  results: SymbolResult[]
  onMatchClick?: (result: SymbolResult, match: Match, idx: number) => void
}

export default function DetectionOverlay({ imageUrl, results, onMatchClick }: Props) {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const imgRef = useRef<HTMLImageElement | null>(null)
  const [hovered, setHovered] = useState<string | null>(null)  // "resultId-matchIdx"
  const [imgNaturalSize, setImgNaturalSize] = useState({ w: 1, h: 1 })
  const [canvasSize, setCanvasSize] = useState({ w: 800, h: 600 })

  // Flatten all matches with metadata for hit-testing
  const flatMatches: Array<{ key: string; result: SymbolResult; match: Match; matchIdx: number; color: string }> = []
  results.forEach((result, ri) => {
    result.matches.forEach((match, mi) => {
      flatMatches.push({
        key: `${result.id}-${mi}`,
        result,
        match,
        matchIdx: mi,
        color: COLORS[ri % COLORS.length],
      })
    })
  })

  // Draw all boxes on the canvas
  function draw() {
    const canvas = canvasRef.current
    const img = imgRef.current
    if (!canvas || !img) return

    const ctx = canvas.getContext('2d')!
    const scaleX = canvas.width / imgNaturalSize.w
    const scaleY = canvas.height / imgNaturalSize.h

    ctx.clearRect(0, 0, canvas.width, canvas.height)
    ctx.drawImage(img, 0, 0, canvas.width, canvas.height)

    for (const fm of flatMatches) {
      const [x1, y1, x2, y2] = fm.match.bbox
      const sx = x1 * scaleX
      const sy = y1 * scaleY
      const sw = (x2 - x1) * scaleX
      const sh = (y2 - y1) * scaleY

      const isHovered = hovered === fm.key
      ctx.strokeStyle = fm.color
      ctx.lineWidth = isHovered ? 3 : 2
      ctx.strokeRect(sx, sy, sw, sh)

      if (isHovered) {
        ctx.fillStyle = fm.color + '33'
        ctx.fillRect(sx, sy, sw, sh)
      }
    }
  }

  // Load image
  useEffect(() => {
    const img = new Image()
    img.onload = () => {
      imgRef.current = img
      setImgNaturalSize({ w: img.naturalWidth, h: img.naturalHeight })
    }
    img.src = imageUrl
  }, [imageUrl])

  // Resize canvas to container
  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    const observer = new ResizeObserver(entries => {
      for (const entry of entries) {
        const { width } = entry.contentRect
        const ratio = imgNaturalSize.h / imgNaturalSize.w
        setCanvasSize({ w: Math.floor(width), h: Math.floor(width * ratio) })
      }
    })
    observer.observe(canvas.parentElement!)
    return () => observer.disconnect()
  }, [imgNaturalSize])

  useEffect(() => {
    if (canvasRef.current) {
      canvasRef.current.width = canvasSize.w
      canvasRef.current.height = canvasSize.h
    }
    draw()
  }, [canvasSize, hovered, results, imgNaturalSize])

  // Hit-test on mouse move / click
  function getHitMatch(e: React.MouseEvent<HTMLCanvasElement>) {
    const canvas = canvasRef.current!
    const rect = canvas.getBoundingClientRect()
    const mx = (e.clientX - rect.left) * (canvas.width / rect.width)
    const my = (e.clientY - rect.top) * (canvas.height / rect.height)
    const scaleX = canvas.width / imgNaturalSize.w
    const scaleY = canvas.height / imgNaturalSize.h

    for (const fm of flatMatches) {
      const [x1, y1, x2, y2] = fm.match.bbox
      if (mx >= x1 * scaleX && mx <= x2 * scaleX && my >= y1 * scaleY && my <= y2 * scaleY) {
        return fm
      }
    }
    return null
  }

  return (
    <div className="w-full overflow-auto rounded-lg border border-gray-200 bg-gray-900">
      <canvas
        ref={canvasRef}
        style={{ display: 'block', width: '100%', cursor: 'crosshair' }}
        onMouseMove={e => {
          const hit = getHitMatch(e)
          setHovered(hit?.key ?? null)
        }}
        onMouseLeave={() => setHovered(null)}
        onClick={e => {
          const hit = getHitMatch(e)
          if (hit && onMatchClick) {
            onMatchClick(hit.result, hit.match, hit.matchIdx)
          }
        }}
      />
      {/* Legend */}
      {results.length > 0 && (
        <div className="flex flex-wrap gap-3 p-3 bg-gray-800">
          {results.map((r, i) => (
            <div key={r.id} className="flex items-center gap-1.5 text-xs text-gray-200">
              <span
                className="inline-block w-3 h-3 rounded-sm border border-white/20"
                style={{ backgroundColor: COLORS[i % COLORS.length] }}
              />
              {r.symbol_name} ({r.match_count})
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
