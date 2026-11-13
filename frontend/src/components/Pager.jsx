import { ChevronLeft, ChevronRight } from 'lucide-react'

export default function Pager({ pager }) {
  if (pager.pages <= 1) return null
  const { page, pages, setPage } = pager
  return (
    <div className="clinic-pager">
      <button type="button" className="clinic-btn clinic-btn-ghost" disabled={page === 0}
        onClick={() => setPage(page - 1)} aria-label="Page précédente"><ChevronLeft size={18} /></button>
      <span>Page {page + 1} / {pages}</span>
      <button type="button" className="clinic-btn clinic-btn-ghost" disabled={page >= pages - 1}
        onClick={() => setPage(page + 1)} aria-label="Page suivante"><ChevronRight size={18} /></button>
    </div>
  )
}