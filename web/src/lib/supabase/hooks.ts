import { useEffect, useMemo, useState } from 'react'
import { ROUTES } from '@/lib/constants'
import { createClient } from './client'
import type { Session } from '@supabase/supabase-js'

export function useSession() {
  const [session, setSession] = useState<Session | null>(null)
  const [status, setStatus] = useState<'loading' | 'authenticated' | 'unauthenticated'>('loading')
  const supabase = useMemo(() => createClient(), [])

  useEffect(() => {
    supabase.auth.getSession().then(({ data: { session } }) => {
      setSession(session)
      setStatus(session ? 'authenticated' : 'unauthenticated')
    })

    const { data: { subscription } } = supabase.auth.onAuthStateChange((_event, session) => {
      setSession(session)
      setStatus(session ? 'authenticated' : 'unauthenticated')
    })

    return () => subscription.unsubscribe()
  }, [supabase])

  return { data: session, status }
}

export const signOut = async () => {
  const supabase = createClient()
  await supabase.auth.signOut()
  // A full page load, not a client-side push: it drops every query cached for
  // the user who just left. Replace, so Back does not return to their pages.
  window.location.replace(ROUTES.LOGIN)
}
