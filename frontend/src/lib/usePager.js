import { useState } from 'react'

export function usePager(items, size = 5) {
  const [page, setPage] = useState(0)
  const pages = Math.max(1, Math.ceil(items.length / size))
  const current = Math.min(page, pages - 1)   // stays valid if the list shrinks
  return {
    page: current, pages, setPage, total: items.length,
    slice: items.slice(current * size, current * size + size),
  }
}