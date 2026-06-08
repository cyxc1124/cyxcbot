import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import { Layout } from './components/Layout'
import { ToastContainer } from './components/ToastContainer'
import { AuthProvider } from './contexts/AuthContext'
import { SidebarProvider } from './contexts/SidebarContext'
import { ToastProvider } from './contexts/ToastContext'
import { AboutPage } from './pages/About'
import { AuditPage } from './pages/Audit'
import { DashboardPage } from './pages/Dashboard'
import { DynamicMonitorPage } from './pages/DynamicMonitor'
import { EventsPage } from './pages/Events'
import { GroupsPage } from './pages/Groups'
import { LiveMonitorPage } from './pages/LiveMonitor'
import { LoginPage } from './pages/Login'
import { SettingsLayout } from './pages/settings/SettingsLayout'
import { SettingsAccountPage } from './pages/settings/SettingsAccount'
import { SettingsBotPage } from './pages/settings/SettingsBot'
import { SettingsDataPage } from './pages/settings/SettingsData'
import { SettingsMonitorPage } from './pages/settings/SettingsMonitor'
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
              <Route element={<SidebarProvider><Layout /></SidebarProvider>}>
                <Route index element={<DashboardPage />} />
                <Route path="dynamic" element={<DynamicMonitorPage />} />
                <Route path="live" element={<LiveMonitorPage />} />
                <Route path="groups" element={<GroupsPage />} />
                <Route path="settings" element={<SettingsLayout />}>
                  <Route index element={<Navigate to="monitor" replace />} />
                  <Route path="monitor" element={<SettingsMonitorPage />} />
                  <Route path="account" element={<SettingsAccountPage />} />
                  <Route path="bot" element={<SettingsBotPage />} />
                  <Route path="data" element={<SettingsDataPage />} />
                </Route>
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
