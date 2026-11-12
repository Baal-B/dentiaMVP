import { useState } from 'react'

const KEY = 'dentia.topK'

export function useTopK() {
  const [topK, setTopK] = useState(() => {
    try {
      const v = parseInt(localStorage.getItem(KEY), 10)
      return v >= 1 && v <= 8 ? v : 3
    } catch {
      return 3
    }
  })
  const update = (v) => {
    setTopK(v)
    try { localStorage.setItem(KEY, String(v)) } catch { /* storage unavailable */ }
  }
  return [topK, update]
}