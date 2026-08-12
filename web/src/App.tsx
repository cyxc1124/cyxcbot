import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import { Layout } from './components/Layout'
import { ToastContainer } from './components/ToastContainer'
import { AuthProvider } from './contexts/AuthContext'
import { SidebarProvider } from './contexts/SidebarContext'
import { ToastProvider } from './contexts/ToastContext'
import { AboutPage } from './pages/About'
import { DashboardPage } from './pages/Dashboard'
import { DynamicMonitorPage } from './pages/DynamicMonitor'
import { LogsPage } from './pages/Logs'
import { GroupsPage } from './pages/Groups'
import { PrivatePage } from './pages/Private'
import { LiveMonitorPage } from './pages/LiveMonitor'
import { LoginPage } from './pages/Login'
import { MessageTemplatesPage } from './pages/MessageTemplates'
import { SettingsLayout } from './pages/settings/SettingsLayout'
import { SettingsAccountPage } from './pages/settings/SettingsAccount'
import { SettingsBotPage } from './pages/settings/SettingsBot'
import { SettingsCommandsPage } from './pages/settings/SettingsCommands'
import { SettingsDouyinAccountPage } from './pages/settings/SettingsDouyinAccount'
import {
  SettingsBilibiliMonitorPage,
  SettingsXMonitorPage,
} from './pages/settings/SettingsMonitor'
import { SettingsXAccountPage } from './pages/settings/SettingsXAccount'
import { XMonitorPage } from './pages/XMonitor'
import { RustRconPage } from './pages/RustRcon'
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
                <Route path="x" element={<XMonitorPage />} />
                <Route path="rust-rcon" element={<RustRconPage />} />
                <Route path="templates" element={<Navigate to="/templates/bilibili" replace />} />
                <Route path="templates/:platform" element={<MessageTemplatesPage />} />
                <Route path="groups" element={<GroupsPage />} />
                <Route path="private" element={<PrivatePage />} />
                <Route path="settings" element={<SettingsLayout />}>
                  <Route index element={<Navigate to="bilibili-monitor" replace />} />
                  <Route path="bilibili-monitor" element={<SettingsBilibiliMonitorPage />} />
                  <Route path="x-monitor" element={<SettingsXMonitorPage />} />
                  <Route path="monitor" element={<Navigate to="/settings/bilibili-monitor" replace />} />
                  <Route path="account" element={<SettingsAccountPage />} />
                  <Route path="douyin-account" element={<SettingsDouyinAccountPage />} />
                  <Route path="x-account" element={<SettingsXAccountPage />} />
                  <Route path="bot" element={<SettingsBotPage />} />
                  <Route path="commands" element={<SettingsCommandsPage />} />
                </Route>
                <Route path="logs" element={<LogsPage />} />
                <Route path="about" element={<AboutPage />} />
                <Route path="mappings" element={<Navigate to="/dynamic" replace />} />
                <Route path="settings/templates" element={<Navigate to="/templates/bilibili" replace />} />
                <Route path="audit" element={<Navigate to="/" replace />} />
                <Route path="events" element={<Navigate to="/" replace />} />
                <Route path="settings/data" element={<Navigate to="/settings/bilibili-monitor" replace />} />
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
