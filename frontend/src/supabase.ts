import { createClient } from '@supabase/supabase-js'

const url = import.meta.env.VITE_SUPABASE_URL?.trim()
const key =
  import.meta.env.VITE_SUPABASE_PUBLISHABLE_KEY?.trim() ||
  import.meta.env.VITE_SUPABASE_ANON_KEY?.trim()

export const supabaseAuthEnabled = Boolean(url && key)
export const supabase =
  url && key
    ? createClient(url, key, {
      auth: {
        autoRefreshToken: true,
        detectSessionInUrl: true,
        persistSession: true,
      },
    })
    : null

export const demoAuthEnabled = import.meta.env.VITE_DEMO_AUTH_ENABLED !== 'false'
