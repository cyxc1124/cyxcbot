import { useEffect } from 'react'

/**
 * Run an async loader on mount and when `callback` changes.
 * Data fetching via useEffect is intentional for this admin SPA.
 */
export function useMountAsync(callback: () => void | Promise<void>) {
  useEffect(() => {
    void callback()
  }, [callback])
}
