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
import { SettingsAdvancedPage } from './pages/settings/SettingsAdvanced'
import { SettingsCommandsPage } from './pages/settings/SettingsCommands'
import { SettingsDouyinAccountPage } from './pages/settings/SettingsDouyinAccount'
import {
  SettingsBilibiliMonitorPage,
  SettingsXMonitorPage,
} from './pages/settings/SettingsMonitor'
import { SettingsOfficialQQPage } from './pages/settings/SettingsOfficialQQ'
import { SettingsXAccountPage } from './pages/settings/SettingsXAccount'
import { XMonitorPage } from './pages/XMonitor'
import { RustRconPage } from './pages/RustRcon'
import { LinkParserPage } from './pages/LinkParser'
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
                <Route path="bilibili/dynamic" element={<DynamicMonitorPage />} />
                <Route path="bilibili/live" element={<LiveMonitorPage />} />
                <Route path="x/subscriptions" element={<XMonitorPage />} />
                <Route path="bilibili/parser" element={<LinkParserPage platform="bilibili" />} />
                <Route path="x/parser" element={<LinkParserPage platform="x" />} />
                <Route path="douyin/parser" element={<LinkParserPage platform="douyin" />} />
                <Route path="bilibili/templates" element={<MessageTemplatesPage platform="bilibili" />} />
                <Route path="x/templates" element={<MessageTemplatesPage platform="x" />} />
                <Route path="douyin/templates" element={<MessageTemplatesPage platform="douyin" />} />
                <Route path="rust/remote/:tab" element={<RustRconPage area="remote" />} />
                <Route path="rust/players/:tab" element={<RustRconPage area="players" />} />
                <Route path="groups" element={<GroupsPage />} />
                <Route path="friends" element={<PrivatePage />} />
                <Route element={<SettingsLayout />}>
                  <Route path="bilibili/settings" element={<SettingsBilibiliMonitorPage />} />
                  <Route path="x/settings" element={<SettingsXMonitorPage />} />
                  <Route path="bilibili/account" element={<SettingsAccountPage />} />
                  <Route path="douyin/account" element={<SettingsDouyinAccountPage />} />
                  <Route path="x/account" element={<SettingsXAccountPage />} />
                  <Route path="system/connections" element={<SettingsOfficialQQPage />} />
                  <Route path="system/permissions" element={<SettingsBotPage />} />
                  <Route path="system/commands" element={<SettingsCommandsPage />} />
                  <Route path="system/advanced" element={<SettingsAdvancedPage />} />
                </Route>
                <Route path="logs" element={<LogsPage />} />
                <Route path="about" element={<AboutPage />} />
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
