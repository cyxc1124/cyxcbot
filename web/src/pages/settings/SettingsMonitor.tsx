import { ToggleSwitch } from '../../components/ToggleSwitch'
import { useSettingsForm } from './SettingsContext'

function SettingToggleRow({
  label,
  checked,
  disabled,
  onChange,
}: {
  label: string
  checked: boolean
  disabled: boolean
  onChange: (checked: boolean) => void
}) {
  return (
    <div className="flex items-center gap-4 py-2">
      <span className="min-w-0 flex-1 text-sm text-slate-700 dark:text-slate-300">{label}</span>
      <div className="flex w-[5.75rem] shrink-0 items-center justify-end gap-2">
        <span
          className={`w-10 shrink-0 text-right text-xs ${
            checked ? 'text-emerald-600 dark:text-emerald-400' : 'text-slate-400'
          }`}
        >
          {checked ? '已启用' : '已关闭'}
        </span>
        <ToggleSwitch checked={checked} disabled={disabled} onChange={onChange} />
      </div>
    </div>
  )
}

export function SettingsMonitorPage() {
  const { settings, setSettings, formDisabled, saving, handleSubmit } = useSettingsForm()

  return (
    <form onSubmit={handleSubmit} className="space-y-6">
      <div className="card space-y-4">
        <h3 className="font-semibold text-slate-900 dark:text-white">动态监控</h3>
        <div className="max-w-xs">
          <label className="label" htmlFor="dynamic_interval">
            检查间隔（秒）
          </label>
          <input
            id="dynamic_interval"
            type="number"
            min={30}
            max={3600}
            className="input"
            value={settings?.dynamic_monitor_interval ?? ''}
            disabled={formDisabled}
            onChange={(e) =>
              setSettings((s) =>
                s ? { ...s, dynamic_monitor_interval: Number(e.target.value) } : s,
              )
            }
          />
        </div>
        <div className="border-t border-slate-100 pt-1 dark:border-slate-800">
          <SettingToggleRow
            label="启用动态截图（Playwright）"
            checked={settings?.dynamic_enable_screenshot ?? false}
            disabled={formDisabled || saving}
            onChange={(checked) =>
              setSettings((s) => (s ? { ...s, dynamic_enable_screenshot: checked } : s))
            }
          />
        </div>
      </div>

      <div className="card space-y-4">
        <h3 className="font-semibold text-slate-900 dark:text-white">直播监控</h3>
        <div className="max-w-xs">
          <label className="label" htmlFor="live_interval">
            检查间隔（秒）
          </label>
          <input
            id="live_interval"
            type="number"
            min={30}
            max={3600}
            className="input"
            value={settings?.live_monitor_interval ?? ''}
            disabled={formDisabled}
            onChange={(e) =>
              setSettings((s) =>
                s ? { ...s, live_monitor_interval: Number(e.target.value) } : s,
              )
            }
          />
        </div>
        <div className="divide-y divide-slate-100 border-t border-slate-100 pt-1 dark:divide-slate-800 dark:border-slate-800">
          <SettingToggleRow
            label="通知包含详细房间信息"
            checked={settings?.live_monitor_include_info ?? false}
            disabled={formDisabled || saving}
            onChange={(checked) =>
              setSettings((s) => (s ? { ...s, live_monitor_include_info: checked } : s))
            }
          />
          <SettingToggleRow
            label="启用 WebSocket 实时监控"
            checked={settings?.live_monitor_use_websocket ?? false}
            disabled={formDisabled || saving}
            onChange={(checked) =>
              setSettings((s) => (s ? { ...s, live_monitor_use_websocket: checked } : s))
            }
          />
        </div>
      </div>

      <div className="card space-y-4">
        <div>
          <h3 className="font-semibold text-slate-900 dark:text-white">链接解析</h3>
          <p className="mt-1 text-sm text-slate-500">
            群聊/好友中自动识别 B 站视频、直播间与 b23 短链并回复卡片。文案可在「消息模板」中配置。
          </p>
        </div>
        <div className="divide-y divide-slate-100 border-t border-slate-100 pt-1 dark:divide-slate-800 dark:border-slate-800">
          <SettingToggleRow
            label="启用链接解析"
            checked={settings?.bilibili_link_parser_enabled ?? false}
            disabled={formDisabled || saving}
            onChange={(checked) =>
              setSettings((s) => (s ? { ...s, bilibili_link_parser_enabled: checked } : s))
            }
          />
          <SettingToggleRow
            label="启用视频链接解析"
            checked={settings?.bilibili_link_parser_video_enabled ?? false}
            disabled={
              formDisabled ||
              saving ||
              !(settings?.bilibili_link_parser_enabled ?? false)
            }
            onChange={(checked) =>
              setSettings((s) =>
                s ? { ...s, bilibili_link_parser_video_enabled: checked } : s,
              )
            }
          />
          <SettingToggleRow
            label="启用直播链接解析"
            checked={settings?.bilibili_link_parser_live_enabled ?? false}
            disabled={
              formDisabled ||
              saving ||
              !(settings?.bilibili_link_parser_enabled ?? false)
            }
            onChange={(checked) =>
              setSettings((s) =>
                s ? { ...s, bilibili_link_parser_live_enabled: checked } : s,
              )
            }
          />
        </div>
      </div>

      <button type="submit" className="btn-primary" disabled={saving || formDisabled}>
        {saving ? '保存中…' : '保存设置'}
      </button>
    </form>
  )
}
