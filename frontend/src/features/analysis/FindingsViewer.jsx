import { useState } from 'react'
import { labelFr, pct } from '../../lib/findings'

export default function FindingsViewer({ url, findings, decisions, selectedId, onSelect }) {
  const [size, setSize] = useState(null)
  const [zoom, setZoom] = useState(1)

  return (
    <div>
      <div className="clinic-zoom">
        {[1, 2, 3].map((z) => (
          <button
            key={z}
            type="button"
            className={'clinic-btn clinic-btn-ghost' + (zoom === z ? ' active' : '')}
            onClick={() => setZoom(z)}
          >
            {z}×
          </button>
        ))}
      </div>

      <div className="clinic-viewer">
        <div className="clinic-viewer-inner" style={{ width: `${zoom * 100}%` }}>
          <img
            src={url}
            alt="Radiographie"
            draggable={false}
            onLoad={(e) => setSize({ w: e.target.naturalWidth, h: e.target.naturalHeight })}
          />
          {size &&
            findings.map((f) => {
              const [x1, y1, x2, y2] = f.bbox_xyxy
              const cls = ['clinic-box', decisions[f.id] ?? 'undecided', f.id === selectedId ? 'selected' : '']
                .join(' ')
              return (
                <button
                  key={f.id}
                  type="button"
                  className={cls}
                  title={`${labelFr(f.label)} — ${pct(f.confidence)}`}
                  style={{
                    left: `${(x1 / size.w) * 100}%`,
                    top: `${(y1 / size.h) * 100}%`,
                    width: `${((x2 - x1) / size.w) * 100}%`,
                    height: `${((y2 - y1) / size.h) * 100}%`,
                  }}
                  onClick={() => onSelect(f.id)}
                >
                  <span className="clinic-box-tag">{f.id}</span>
                </button>
              )
            })}
        </div>
      </div>
    </div>
  )
}