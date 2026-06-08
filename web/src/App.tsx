import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import { Layout } from './components/Layout'
import { ToastContainer } from './components/ToastContainer'
import { AuthProvider } from './contexts/AuthContext'
import { ToastProvider } from './contexts/ToastContext'
import { AboutPage } from './pages/About'
import { AuditPage } from './pages/Audit'
import { DashboardPage } from './pages/Dashboard'
import { DynamicMonitorPage } from './pages/DynamicMonitor'
import { EventsPage } from './pages/Events'
import { GroupsPage } from './pages/Groups'
import { LiveMonitorPage } from './pages/LiveMonitor'
import { LoginPage } from './pages/Login'
import { SettingsPage } from './pages/Settings'
import { SetupPage } from './pages/Setup'
import { AuthGuard, PublicGuard, SetupGuard } from './routes/Guards'

export default function App() {
  return (
    <AuthProvider>
      <ToastProvider>
        <BrowserRouter>
          <Routes>
            <Route element={<SetupGuard />}>
              <Route path="/setup" element={<SetupPage />} />
            </Route>

            <Route element={<PublicGuard />}>
              <Route path="/login" element={<LoginPage />} />
            </Route>

            <Route element={<AuthGuard />}>
              <Route element={<Layout />}>
                <Route index element={<DashboardPage />} />
                <Route path="dynamic" element={<DynamicMonitorPage />} />
                <Route path="live" element={<LiveMonitorPage />} />
                <Route path="groups" element={<GroupsPage />} />
                <Route path="settings" element={<SettingsPage />} />
                <Route path="audit" element={<AuditPage />} />
                <Route path="events" element={<EventsPage />} />
                <Route path="about" element={<AboutPage />} />
                <Route path="mappings" element={<Navigate to="/dynamic" replace />} />
              </Route>
            </Route>

            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
          <ToastContainer />
        </BrowserRouter>
      </ToastProvider>
    </AuthProvider>
  )
}
