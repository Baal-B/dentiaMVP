import { useAuth } from '../auth/AuthProvider'

export function useActingId() {
  const { user, profile } = useAuth()
  return profile?.role === 'secretary' ? profile.works_for : user?.id
}