import { useEffect, useState } from 'react'
import { supabase } from '../../lib/supabase'
import { useAuth } from '../auth/AuthProvider'

export function useUnread() {
  const { user } = useAuth()
  const [count, setCount] = useState(0)

  useEffect(() => {
    if (!user) return
    let alive = true
    const load = async () => {
      const { count } = await supabase
        .from('notifications').select('*', { count: 'exact', head: true }).is('read_at', null)
      if (alive) setCount(count ?? 0)
    }
    load()
    const timer = setInterval(load, 60000)
    window.addEventListener('notifs-changed', load)
    return () => {
      alive = false
      clearInterval(timer)
      window.removeEventListener('notifs-changed', load)
    }
  }, [user?.id])

  return count
}