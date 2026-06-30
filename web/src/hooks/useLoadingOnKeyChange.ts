import { useCallback, useReducer } from 'react'

export type LoadingState = {
  key: string
  loading: boolean
}

export type LoadingAction =
  | { type: 'syncKey'; key: string }
  | { type: 'setLoading'; loading: boolean }

export function loadingReducer(state: LoadingState, action: LoadingAction): LoadingState {
  switch (action.type) {
    case 'syncKey':
      if (state.key === action.key) return state
      return { key: action.key, loading: true }
    case 'setLoading':
      return { ...state, loading: action.loading }
    default:
      return state
  }
}

/**
 * Keeps loading true on first render and whenever `key` changes.
 */
export function useLoadingOnKeyChange(key: string): [boolean, (value: boolean) => void] {
  const [state, dispatch] = useReducer(loadingReducer, { key, loading: true })

  if (state.key !== key) {
    dispatch({ type: 'syncKey', key })
  }

  const setLoading = useCallback(
    (loading: boolean) => dispatch({ type: 'setLoading', loading }),
    [],
  )

  return [state.loading, setLoading]
}
