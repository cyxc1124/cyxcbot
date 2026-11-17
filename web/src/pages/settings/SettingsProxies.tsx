import { useState } from 'react'
import { Link } from 'react-router-dom'
import type { ProxiesResult } from '../../api/types'
import { ProxyCard } from './ProxyCard'
import { newProxyDraft, proxyAddress, proxyUsages, type ProxyDraft } from './proxyForm'
import { useSettingsForm } from './SettingsContext'

export function SettingsProxiesPage() {
  const { settings, setSettings, formDisabled } = useSettingsForm()
  const [newDrafts, setNewDrafts] = useState<ProxyDraft[]>([])
  const proxies = settings?.proxies ?? []
  const usages = proxyUsages(settings)

  // 只替换代理列表，其他卡片里未保存的修改保持不变。
  const apply = (result: ProxiesResult) => {
    setSettings((current) => (current ? { ...current, proxies: result.proxies } : current))
  }
  const dropNew = (key: string) => setNewDrafts((current) => current.filter((draft) => draft.key !== key))

  return (
    <div className="space-y-6">
      <p className="text-sm text-muted-foreground">
        在这里集中添加出站代理，可以添加多个。代理本身不会自动生效：需要访问境外接口的功能在各自的设置页选择使用哪个代理，
        也可以选择直接连接。QQ 图片下载、B 站与抖音请求不经过这些代理。
      </p>

      <div className="card space-y-3">
        <div>
          <h3 className="font-semibold text-foreground">各功能使用的代理</h3>
          <p className="mt-1 text-sm text-muted-foreground">服务器无法直接访问对应服务时，为该功能选择一个可用的代理。</p>
        </div>
        <ul className="divide-y divide-border text-sm">
          {usages.map((usage) => {
            const selected = proxies.find((proxy) => proxy.id === usage.proxyId)
            return (
              <li key={usage.label} className="flex flex-wrap items-center justify-between gap-2 py-2">
                <span className="text-foreground">{usage.label}</span>
                <span className="flex items-center gap-3">
                  {selected ? (
                    <span className="text-emerald-600 dark:text-emerald-400">「{selected.name}」{proxyAddress(selected)}</span>
                  ) : usage.proxyId ? (
                    <span className="text-amber-600 dark:text-amber-400">所选代理已删除，当前直接连接</span>
                  ) : (
                    <span className="text-muted-foreground">直接连接</span>
                  )}
                  <Link to={usage.to} className="text-xs text-primary hover:underline">去设置</Link>
                </span>
              </li>
            )
          })}
        </ul>
      </div>

      {proxies.length === 0 && newDrafts.length === 0 ? (
        <div className="card text-sm text-muted-foreground">
          还没有添加代理，所有功能都直接连接。点击下方「添加代理」填写代理地址，测试可用后再到对应功能中选择它。
        </div>
      ) : (
        <div className="space-y-3">
          {proxies.map((proxy, index) => (
            <ProxyCard key={proxy.id} proxy={proxy} index={index} disabled={formDisabled}
              usages={usages.filter((usage) => usage.proxyId === proxy.id)}
              onProxiesChange={apply} />
          ))}
          {newDrafts.map((draft, offset) => (
            <ProxyCard key={draft.key} initialDraft={draft} index={proxies.length + offset} usages={[]} disabled={formDisabled}
              onProxiesChange={(result) => { dropNew(draft.key); apply(result) }}
              onDiscardNew={() => dropNew(draft.key)} />
          ))}
        </div>
      )}

      <div className="flex flex-wrap items-center gap-3">
        <button type="button" className="btn-secondary" disabled={formDisabled}
          onClick={() => setNewDrafts([...newDrafts, newProxyDraft()])}>
          添加代理
        </button>
        <span className="text-xs text-muted-foreground">已保存 {proxies.length} 个代理；每个代理单独保存，点击标题展开或收起。</span>
      </div>
    </div>
  )
}
