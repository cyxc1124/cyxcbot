import { Navigate, Outlet } from 'react-router-dom'
import { LoadErrorBanner } from '../components/LoadErrorBanner'
import { PageLoading } from '../components/LoadingSpinner'
import { useAuth } from '../contexts/AuthContext'
import {
  shouldAllowSetupRoute,
  shouldLeaveSetupRoute,
  shouldRedirectToSetup,
} from './guardLogic'

function InitStatusError() {
  const { initError, refresh } = useAuth()

  return (
    <div className="flex min-h-screen items-center justify-center bg-linear-to-br from-muted to-secondary p-4 dark:from-background dark:to-card">
      <div className="card w-full max-w-md">
        <LoadErrorBanner
          message={initError ?? '无法获取初始化状态，请重试'}
          onRetry={() => void refresh()}
        />
      </div>
    </div>
  )
}

export function SetupGuard() {
  const { initialized, initError, loading } = useAuth()
  const state = { initialized, initError, loading }

  if (loading) return <PageLoading />
  if (initError) return <InitStatusError />
  if (shouldLeaveSetupRoute(state)) return <Navigate to="/login" replace />
  if (shouldAllowSetupRoute(state)) return <Outlet />

  return <PageLoading />
}

export function PublicGuard() {
  const { initialized, initError, isAuthenticated, loading } = useAuth()
  const state = { initialized, initError, loading }

  if (loading) return <PageLoading />
  if (initError) return <InitStatusError />
  if (shouldRedirectToSetup(state)) return <Navigate to="/setup" replace />
  if (isAuthenticated) return <Navigate to="/" replace />

  return <Outlet />
}

export function AuthGuard() {
  const { initialized, initError, isAuthenticated, loading } = useAuth()
  const state = { initialized, initError, loading }

  if (loading) return <PageLoading />
  if (initError) return <InitStatusError />
  if (shouldRedirectToSetup(state)) return <Navigate to="/setup" replace />
  if (!isAuthenticated) return <Navigate to="/login" replace />

  return <Outlet />
}
