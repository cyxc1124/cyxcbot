import { useEffect, useState, type FormEvent } from 'react'
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

  useEffect(() => {
    if (settings) {
      setSuperuserText(formatQqInput(settings.nonebot_superusers))
      setStatusCheckText(formatQqInput(settings.status_check_allowed_qq))
    }
  }, [settings])

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
      })
      setSettings(updated)
      setSuperuserText(formatQqInput(updated.nonebot_superusers))
      setStatusCheckText(formatQqInput(updated.status_check_allowed_qq))
      showToast('success', '机器人权限已保存')
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
          <h3 className="font-semibold text-slate-900 dark:text-white">NoneBot 超级用户</h3>
          <p className="mt-1 text-sm text-slate-500">
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
            className="input min-h-[8rem] font-mono text-sm"
            placeholder={'每行一个 QQ 号，例如：\n120674547'}
            value={superuserText}
            disabled={formDisabled || saving}
            onChange={(e) => setSuperuserText(e.target.value)}
          />
        </div>
      </div>

      <div className="card space-y-4">
        <div>
          <h3 className="font-semibold text-slate-900 dark:text-white">状态查询权限</h3>
          <p className="mt-1 text-sm text-slate-500">
            允许非超级用户使用{' '}
            <code className="rounded bg-slate-100 px-1 py-0.5 text-xs dark:bg-slate-800">/status</code>{' '}
            、<code className="rounded bg-slate-100 px-1 py-0.5 text-xs dark:bg-slate-800">/状态</code>{' '}
            查询运行状态。超级用户已默认拥有此权限，无需重复填写。
          </p>
        </div>

        <div>
          <label className="label" htmlFor="status_check_allowed_qq">
            额外允许的 QQ 号
          </label>
          <textarea
            id="status_check_allowed_qq"
            className="input min-h-[8rem] font-mono text-sm"
            placeholder={'每行一个 QQ 号'}
            value={statusCheckText}
            disabled={formDisabled || saving}
            onChange={(e) => setStatusCheckText(e.target.value)}
          />
          <p className="mt-2 text-xs text-slate-500">
            也可使用逗号、分号或空格分隔。无权限用户发送命令时机器人不会回复。
          </p>
        </div>
      </div>

      <button type="submit" className="btn-primary" disabled={saving || formDisabled}>
        {saving ? '保存中…' : '保存设置'}
      </button>
    </form>
  )
}
