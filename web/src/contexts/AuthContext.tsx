import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react'
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

interface AuthState {
  initialized: boolean | null
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
  const [user, setUser] = useState<User | null>(null)
  const [loading, setLoading] = useState(true)

  const refresh = useCallback(async () => {
    setLoading(true)
    try {
      const status = await getSetupStatus()
      setInitialized(status.initialized)

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
    } catch {
      setUser(null)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void refresh()
  }, [refresh])

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
      user,
      loading,
      isAuthenticated: !!user,
      refresh,
      login,
      setup,
      logout,
    }),
    [initialized, user, loading, refresh, login, setup, logout],
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
