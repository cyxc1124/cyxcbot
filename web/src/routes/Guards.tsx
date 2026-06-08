import { Navigate, Outlet } from 'react-router-dom'
import { PageLoading } from '../components/LoadingSpinner'
import { useAuth } from '../contexts/AuthContext'

export function SetupGuard() {
  const { initialized, loading } = useAuth()

  if (loading) return <PageLoading />
  if (initialized) return <Navigate to="/login" replace />

  return <Outlet />
}

export function PublicGuard() {
  const { initialized, isAuthenticated, loading } = useAuth()

  if (loading) return <PageLoading />
  if (!initialized) return <Navigate to="/setup" replace />
  if (isAuthenticated) return <Navigate to="/" replace />

  return <Outlet />
}

export function AuthGuard() {
  const { initialized, isAuthenticated, loading } = useAuth()

  if (loading) return <PageLoading />
  if (!initialized) return <Navigate to="/setup" replace />
  if (!isAuthenticated) return <Navigate to="/login" replace />

  return <Outlet />
}
