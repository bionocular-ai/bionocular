import { useEffect, useState } from 'react'
import { createClient } from './client'
import type { Session, User } from '@supabase/supabase-js'

export function useSession() {
  const [session, setSession] = useState<Session | null>(null)
  const [status, setStatus] = useState<'loading' | 'authenticated' | 'unauthenticated'>('loading')
  const supabase = createClient()

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
  }, [])

  return { data: session, status }
}

export const signOut = async () => {
  const supabase = createClient()
  await supabase.auth.signOut()
  window.location.href = '/login'
}
