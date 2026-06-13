import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useState,
  type ReactNode,
} from 'react'
import { useLoadingOnKeyChange } from '../hooks/useLoadingOnKeyChange'
import { useMountAsync } from '../hooks/useMountAsync'
import {
  clearToken,
  getMe,
  getSetupStatus,
  getToken,
  postLogin,
  postSetup,
  setToken,
} from '../api/client'
import type { LoginRequest, SetupRequest, User } from '../api/types'
import { getInitErrorOnRefreshFailure } from './authRefresh'

interface AuthState {
  initialized: boolean | null
  initError: string | null
  user: User | null
  loading: boolean
  isAuthenticated: boolean
}

interface AuthContextValue extends AuthState {
  refresh: () => Promise<void>
  login: (data: LoginRequest) => Promise<void>
  setup: (data: SetupRequest) => Promise<void>
  logout: () => void
}

const AuthContext = createContext<AuthContextValue | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [initialized, setInitialized] = useState<boolean | null>(null)
  const [initError, setInitError] = useState<string | null>(null)
  const [user, setUser] = useState<User | null>(null)
  const [loading, setLoading] = useLoadingOnKeyChange('auth')

  const refresh = useCallback(async () => {
    setLoading(true)
    setInitError(null)
    let setupKnown = false

    try {
      const status = await getSetupStatus()
      setInitialized(status.initialized)
      setupKnown = true

      if (!status.initialized) {
        setUser(null)
        return
      }

      const token = getToken()
      if (!token) {
        setUser(null)
        return
      }

      const me = await getMe()
      setUser(me)
    } catch (err) {
      setUser(null)
      const errorMessage = getInitErrorOnRefreshFailure(setupKnown, err)
      if (errorMessage) {
        setInitError(errorMessage)
      }
    } finally {
      setLoading(false)
    }
  }, [setLoading])

  useMountAsync(refresh)

  const login = useCallback(async (data: LoginRequest) => {
    const { access_token } = await postLogin(data)
    setToken(access_token)
    const me = await getMe()
    setUser(me)
    setInitialized(true)
  }, [])

  const setup = useCallback(async (data: SetupRequest) => {
    const { access_token } = await postSetup(data)
    setToken(access_token)
    const me = await getMe()
    setUser(me)
    setInitialized(true)
  }, [])

  const logout = useCallback(() => {
    clearToken()
    setUser(null)
  }, [])

  const value = useMemo<AuthContextValue>(
    () => ({
      initialized,
      initError,
      user,
      loading,
      isAuthenticated: !!user,
      refresh,
      login,
      setup,
      logout,
    }),
    [initialized, initError, user, loading, refresh, login, setup, logout],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext)
  if (!ctx) {
    throw new Error('useAuth must be used within AuthProvider')
  }
  return ctx
}
