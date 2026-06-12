import { useState } from 'react'

/**
 * Keeps loading true on first render and whenever `key` changes.
 * Use with async loaders to avoid synchronous setState inside useEffect.
 */
export function useLoadingOnKeyChange(key: string): [boolean, (value: boolean) => void] {
  const [loading, setLoading] = useState(true)
  const [trackedKey, setTrackedKey] = useState(key)

  if (trackedKey !== key) {
    setTrackedKey(key)
    setLoading(true)
  }

  return [loading, setLoading]
}
