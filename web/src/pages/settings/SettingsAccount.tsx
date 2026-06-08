import { BilibiliAccountInfo } from '../../components/BilibiliAccountInfo'
import { BilibiliQrLogin } from '../../components/BilibiliQrLogin'
import { useToast } from '../../contexts/ToastContext'
import { useSettingsForm } from './SettingsContext'

export function SettingsAccountPage() {
  const { showToast } = useToast()
  const {
    settings,
    bilibili,
    formDisabled,
    load,
    testing,
    handleTestLogin,
    loggingOut,
    setShowLogoutConfirm,
  } = useSettingsForm()

  return (
    <div className="card space-y-4">
      <h3 className="font-semibold text-foreground">B 站账号</h3>
      <p className="text-sm text-muted-foreground">
        用于拉取 UP 主信息与直播状态，未登录时部分监控功能不可用
      </p>

      {bilibili && <BilibiliAccountInfo account={bilibili} />}

      {!bilibili?.logged_in && !formDisabled && (
        <BilibiliQrLogin
          onSuccess={() => {
            showToast('success', 'B 站扫码登录成功')
            void load()
          }}
          onError={(msg) => showToast('error', msg)}
        />
      )}

      {settings?.bilibili_cookie?.configured && (
        <div className="flex flex-wrap gap-3">
          <button
            type="button"
            className="btn-secondary"
            disabled={testing}
            onClick={() => void handleTestLogin()}
          >
            {testing ? '验证中…' : '验证登录状态'}
          </button>
          <button
            type="button"
            className="btn-danger"
            disabled={loggingOut}
            onClick={() => setShowLogoutConfirm(true)}
          >
            退出 B 站登录
          </button>
        </div>
      )}
    </div>
  )
}
