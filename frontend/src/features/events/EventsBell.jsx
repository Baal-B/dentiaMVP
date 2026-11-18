import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { BellRing } from 'lucide-react'
import { supabase } from '../../lib/supabase'

// called by the Events page: marks this doctor's event notifications as read
export async function markEventsSeen() {
  await supabase.from('notifications').update({ read_at: new Date().toISOString() })
    .eq('kind', 'event').is('read_at', null)
}

export default function EventsBell() {
  const [n, setN] = useState(0)
  const load = useCallback(async () => {
    const { count } = await supabase.from('notifications')
      .select('id', { count: 'exact', head: true }).eq('kind', 'event').is('read_at', null)
    setN(count || 0)
  }, [])
  useEffect(() => {
    load()
    const t = setInterval(load, 60000)
    window.addEventListener('notifs-changed', load)
    return () => { clearInterval(t); window.removeEventListener('notifs-changed', load) }
  }, [load])

  return (
    <Link to="/events" className="ev-bell" title="Événements et congrès" aria-label="Événements et congrès">
      <BellRing size={18} />
      <span>Événements</span>
      {n > 0 && <span className="ev-bell-badge">{n}</span>}
    </Link>
  )
}