import { useState, type FormEvent } from 'react'
import { patchSettings } from '../../api/client'
import { useToast } from '../../contexts/ToastContext'
import { formatApiError } from '../../utils/apiError'
import { useSettingsForm } from './SettingsContext'

function parseQqInput(raw: string): string[] {
  return [
    ...new Set(
      raw
        .split(/[\s,，;；]+/)
        .map((item) => item.trim())
        .filter((item) => item.length > 0),
    ),
  ]
}

function formatQqInput(qqList: string[]): string {
  return qqList.join('\n')
}

function validateQqList(list: string[]): string[] | null {
  const invalid = list.filter((qq) => !/^\d+$/.test(qq))
  if (invalid.length > 0) return invalid
  return null
}

export function SettingsBotPage() {
  const { showToast } = useToast()
  const { settings, setSettings, formDisabled, load } = useSettingsForm()
  const [saving, setSaving] = useState(false)
  const [superuserText, setSuperuserText] = useState('')
  const [statusCheckText, setStatusCheckText] = useState('')
  const [sharedMediaDir, setSharedMediaDir] = useState('')
  const [syncedSettings, setSyncedSettings] = useState(settings)

  if (settings !== syncedSettings) {
    setSyncedSettings(settings)
    if (settings) {
      setSuperuserText(formatQqInput(settings.nonebot_superusers))
      setStatusCheckText(formatQqInput(settings.status_check_allowed_qq))
      setSharedMediaDir(settings.link_parser_shared_media_dir)
    }
  }

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault()
    const superusers = parseQqInput(superuserText)
    const statusCheck = parseQqInput(statusCheckText)
    const invalidSuper = validateQqList(superusers)
    const invalidStatus = validateQqList(statusCheck)
    if (invalidSuper) {
      showToast('error', `超级用户 QQ 号格式无效：${invalidSuper.join('、')}`)
      return
    }
    if (invalidStatus) {
      showToast('error', `状态查询 QQ 号格式无效：${invalidStatus.join('、')}`)
      return
    }

    setSaving(true)
    try {
      const updated = await patchSettings({
        nonebot_superusers: superusers,
        status_check_allowed_qq: statusCheck,
        link_parser_shared_media_dir: sharedMediaDir.trim(),
      })
      setSettings(updated)
      setSuperuserText(formatQqInput(updated.nonebot_superusers))
      setStatusCheckText(formatQqInput(updated.status_check_allowed_qq))
      setSharedMediaDir(updated.link_parser_shared_media_dir)
      showToast('success', '机器人设置已保存')
      await load()
    } catch (err) {
      showToast('error', formatApiError(err, '保存失败'))
    } finally {
      setSaving(false)
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-6">
      <div className="card space-y-4">
        <div>
          <h3 className="font-semibold text-foreground">NoneBot 超级用户</h3>
          <p className="mt-1 text-sm text-muted-foreground">
            对应 NoneBot 的 <code className="font-mono text-xs">SUPERUSER</code>{' '}
            权限。超级用户可查询机器人状态，并在其他插件中享有更高权限。保存后会同步到运行中的机器人，无需重启。
          </p>
        </div>

        <div>
          <label className="label" htmlFor="nonebot_superusers">
            超级用户 QQ 号
          </label>
          <textarea
            id="nonebot_superusers"
            className="input min-h-32 font-mono text-sm"
            placeholder={'每行一个 QQ 号，例如：\n120674547'}
            value={superuserText}
            disabled={formDisabled || saving}
            onChange={(e) => setSuperuserText(e.target.value)}
          />
        </div>
      </div>

      <div className="card space-y-4">
        <div>
          <h3 className="font-semibold text-foreground">状态查询权限</h3>
          <p className="mt-1 text-sm text-muted-foreground">
            允许非超级用户使用{' '}
            <code className="rounded bg-secondary px-1 py-0.5 text-xs bg-secondary">/status</code>{' '}
            、<code className="rounded bg-secondary px-1 py-0.5 text-xs bg-secondary">/状态</code>{' '}
            查询运行状态（任意群或好友均可触发）。超级用户已默认拥有此权限。按群/好友的细粒度开关请在「群组」或「好友」页的「状态查询」Tab 中配置。
          </p>
        </div>

        <div>
          <label className="label" htmlFor="status_check_allowed_qq">
            额外允许的 QQ 号
          </label>
          <textarea
            id="status_check_allowed_qq"
            className="input min-h-32 font-mono text-sm"
            placeholder={'每行一个 QQ 号'}
            value={statusCheckText}
            disabled={formDisabled || saving}
            onChange={(e) => setStatusCheckText(e.target.value)}
          />
          <p className="mt-2 text-xs text-muted-foreground">
            也可使用逗号、分号或空格分隔。无权限用户发送命令时机器人不会回复。
          </p>
        </div>
      </div>

      <div className="card space-y-4">
        <div>
          <h3 className="font-semibold text-foreground">链接解析共享媒体目录</h3>
          <p className="mt-1 text-sm text-muted-foreground">
            B 站 / 抖音链接解析发视频（及抖音图集本地文件）时写入此目录，并以{' '}
            <code className="font-mono text-xs">file://</code>{' '}
            交给协议端读取（不再走 base64）。分离部署时请把机器草与协议端 /
            QQ 数据目录挂到同一路径。留空则使用平台默认。
          </p>
        </div>

        <div>
          <label className="label" htmlFor="link_parser_shared_media_dir">
            目录路径
          </label>
          <input
            id="link_parser_shared_media_dir"
            className="input font-mono text-sm"
            placeholder={
              settings?.link_parser_shared_media_dir_default ||
              '/root/.config/QQ/tmp（Linux）或 data/tmp（Windows / macOS）'
            }
            value={sharedMediaDir}
            disabled={formDisabled || saving}
            onChange={(e) => setSharedMediaDir(e.target.value)}
          />
          <p className="mt-2 text-xs text-muted-foreground">
            当前生效：
            <code className="ml-1 font-mono">
              {settings?.link_parser_shared_media_dir_resolved ||
                settings?.link_parser_shared_media_dir_default ||
                '—'}
            </code>
            。默认：Linux 在{' '}
            <code className="font-mono">/root/.config/QQ/tmp</code>{' '}
            可写时用该路径，否则与 Windows / macOS 一样用{' '}
            <code className="font-mono">data/tmp</code>
            。K8s / Docker 仍挂载 QQ 数据根目录，文件写入其下 tmp。
          </p>
        </div>
      </div>

      <button type="submit" className="btn-primary" disabled={saving || formDisabled}>
        {saving ? '保存中…' : '保存设置'}
      </button>
    </form>
  )
}
