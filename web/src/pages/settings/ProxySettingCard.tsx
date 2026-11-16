import { ProxyPicker } from '../../components/ProxyPicker'
import { proxyAddress } from './proxyForm'
import { useSettingsForm } from './SettingsContext'

type ProxyField = 'x_proxy_id' | 'ai_image_openai_proxy_id'

/**
 * 某个功能选用哪个代理。默认选择后立即保存；传入 value/onChange 时随所在表单一起保存，
 * 避免立即保存刷新设置时冲掉同页其他未保存的修改。
 */
export function ProxySettingCard({ field, title, description, value, onChange }: {
  field: ProxyField
  title: string
  description: string
  value?: string
  onChange?: (proxyId: string) => void
}) {
  const { settings, formDisabled, saving, savePartial } = useSettingsForm()
  const proxies = settings?.proxies ?? []
  const saved = settings?.[field] ?? ''
  const current = proxies.find((proxy) => proxy.id === saved)
  const selected = value ?? saved

  return (
    <div className="card space-y-4">
      <div>
        <h3 className="font-semibold text-foreground">{title}</h3>
        <p className="mt-1 text-sm text-muted-foreground">{description}</p>
      </div>
      <div className="rounded-lg border border-border bg-muted/30 px-3 py-2 text-sm">
        <span className="text-muted-foreground">当前：</span>
        {current ? (
          <span className="text-emerald-600 dark:text-emerald-400">
            经代理「{current.name}」（{proxyAddress(current)}）连接
          </span>
        ) : (
          <span className="text-foreground">直接连接，未使用代理</span>
        )}
        {selected !== saved && <span className="ml-2 text-xs text-amber-600 dark:text-amber-400">（修改尚未保存）</span>}
      </div>
      <div>
        <label className="label" htmlFor={`proxy-${field}`}>使用的代理</label>
        <ProxyPicker id={`proxy-${field}`} value={selected} proxies={proxies} disabled={formDisabled || saving}
          onChange={onChange ?? ((proxyId) => { void savePartial({ [field]: proxyId }) })} />
      </div>
    </div>
  )
}
