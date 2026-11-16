import { useState } from 'react'
import { Link } from 'react-router-dom'
import { createProxy, deleteProxy, testProxy, updateProxy } from '../../api/client'
import type { ProxiesResult, ProxyEntry, ProxyScheme } from '../../api/types'
import { ChoiceCardGroup } from '../../components/ChoiceCardGroup'
import { ConfirmDialog } from '../../components/ConfirmDialog'
import { Icon } from '../../components/Icon'
import { useToast } from '../../contexts/ToastContext'
import { formatApiError } from '../../utils/apiError'
import {
  PROXY_SCHEME_LABELS,
  describeProxyTest,
  isProxyDirty,
  needsPasswordReentry,
  newProxyDraft,
  proxyDraftFrom,
  proxyInput,
  proxySummary,
  proxyTestPayload,
  validateProxyDraft,
  type ProxyDraft,
  type ProxyUsage,
} from './proxyForm'

const SCHEME_OPTIONS = (['http', 'https', 'socks5'] as const).map((scheme) => ({
  value: scheme,
  label: PROXY_SCHEME_LABELS[scheme],
  icon: <Icon name="globe" className="size-5" />,
}))

const BADGE = 'rounded bg-amber-500/15 px-1.5 py-px text-[10px] font-medium text-amber-600 dark:text-amber-400'

type Busy = 'save' | 'test' | 'delete'
type Outcome = { success: boolean; lines: string[] }

export function ProxyCard({ proxy, initialDraft, index, usages, disabled, onProxiesChange, onDiscardNew }: {
  /** 已保存的代理；新建卡片省略 */
  proxy?: ProxyEntry
  initialDraft?: ProxyDraft
  index: number
  /** 正在使用该代理的功能 */
  usages: ProxyUsage[]
  disabled: boolean
  onProxiesChange: (result: ProxiesResult) => void
  onDiscardNew?: () => void
}) {
  const { showToast } = useToast()
  const [draft, setDraft] = useState(() => (proxy ? proxyDraftFrom(proxy) : initialDraft ?? newProxyDraft()))
  const [expanded, setExpanded] = useState(!proxy)
  const [busy, setBusy] = useState<Busy | null>(null)
  const [outcome, setOutcome] = useState<Outcome | null>(null)
  const [confirmDelete, setConfirmDelete] = useState(false)

  const id = (field: string) => `proxy-${draft.key}-${field}`
  const update = (patch: Partial<ProxyDraft>) => setDraft({ ...draft, ...patch })
  const reentry = needsPasswordReentry(draft, proxy)
  const dirty = isProxyDirty(draft, proxy)
  const locked = disabled || busy !== null
  const title = (proxy ? proxy.name : draft.name.trim()) || `新代理 ${index + 1}`
  const summary = proxySummary(proxy ?? { ...draft, password_configured: draft.password !== '' })
  const usageText = usages.length > 0 ? `${usages.length} 项功能在用` : '未被任何功能使用'

  const test = async () => {
    const error = reentry ? '修改主机后，请先重新填写密码。' : !draft.host.trim() ? '请先填写主机。' : null
    if (error) {
      setOutcome({ success: false, lines: [error] })
      return
    }
    setBusy('test')
    try {
      const result = await testProxy(proxyTestPayload(draft))
      setOutcome({ success: result.success, lines: describeProxyTest(result) })
    } catch (err) {
      setOutcome({ success: false, lines: [formatApiError(err, '测试失败')] })
    } finally {
      setBusy(null)
    }
  }

  const save = async () => {
    const error = validateProxyDraft(draft, proxy)
    if (error) {
      showToast('error', error)
      return
    }
    setBusy('save')
    try {
      const result = proxy ? await updateProxy(proxy.id, proxyInput(draft)) : await createProxy(proxyInput(draft))
      const saved = result.proxies.find((item) => item.id === result.id)
      if (saved) setDraft(proxyDraftFrom(saved))
      setExpanded(false)
      showToast('success', `已保存代理「${saved?.name ?? draft.name.trim()}」`)
      onProxiesChange(result)
    } catch (err) {
      showToast('error', formatApiError(err, '保存失败'))
    } finally {
      setBusy(null)
    }
  }

  const remove = async () => {
    if (!proxy) return
    setBusy('delete')
    try {
      const result = await deleteProxy(proxy.id)
      setConfirmDelete(false)
      showToast('success', `已删除代理「${proxy.name}」`)
      onProxiesChange(result)
    } catch (err) {
      showToast('error', formatApiError(err, '删除失败'))
    } finally {
      setBusy(null)
    }
  }

  return (
    <div className="card">
      <button type="button" className="flex w-full min-w-0 items-center gap-3 rounded-lg text-left"
        aria-expanded={expanded} aria-controls={id('body')} onClick={() => setExpanded(!expanded)}>
        <Icon name="chevron-down" className={`size-4 shrink-0 text-muted-foreground transition-transform ${expanded ? '' : '-rotate-90'}`} />
        <span className="min-w-0 flex-1">
          <span className="flex flex-wrap items-center gap-2">
            <span className="truncate font-semibold text-foreground">{title}</span>
            {!proxy && <span className={BADGE}>新建，未保存</span>}
            {proxy && dirty && <span className={BADGE}>有未保存修改</span>}
          </span>
          <span className="mt-0.5 block truncate text-xs text-muted-foreground">{summary}</span>
        </span>
        {proxy && (
          <span className={`shrink-0 text-xs ${usages.length > 0 ? 'text-emerald-600 dark:text-emerald-400' : 'text-muted-foreground'}`}>
            {usageText}
          </span>
        )}
      </button>

      {expanded && (
        <form id={id('body')} className="mt-4 space-y-4 border-t border-border pt-4"
          onSubmit={(event) => { event.preventDefault(); void save() }}>
          <ChoiceCardGroup<ProxyScheme> label="协议" value={draft.scheme} options={SCHEME_OPTIONS} disabled={disabled}
            onChange={(scheme) => update({ scheme })} />

          <div className="grid gap-4 sm:grid-cols-2">
            <div className="sm:col-span-2">
              <label className="label" htmlFor={id('name')}>名称</label>
              <input id={id('name')} className="input" maxLength={32} value={draft.name} placeholder="如 香港节点"
                disabled={disabled} onChange={(event) => update({ name: event.target.value })} />
            </div>
            <div>
              <label className="label" htmlFor={id('host')}>主机</label>
              <input id={id('host')} className="input font-mono text-sm" maxLength={255} value={draft.host}
                placeholder="127.0.0.1" disabled={disabled} onChange={(event) => update({ host: event.target.value })} />
            </div>
            <div>
              <label className="label" htmlFor={id('port')}>端口</label>
              <input id={id('port')} type="number" min={1} max={65535} className="input" value={draft.port}
                disabled={disabled} onChange={(event) => update({ port: Number(event.target.value) })} />
            </div>
            <div>
              <label className="label" htmlFor={id('username')}>用户名（可选）</label>
              <input id={id('username')} className="input" maxLength={128} value={draft.username} autoComplete="off"
                disabled={disabled} onChange={(event) => update({ username: event.target.value })} />
            </div>
            <div>
              <label className="label" htmlFor={id('password')}>密码（可选）</label>
              <input id={id('password')} type="password" autoComplete="new-password" className="input" value={draft.password}
                disabled={disabled}
                placeholder={draft.clear_password ? '保存后清除密码' : draft.password_configured ? '已配置，留空保留原密码' : '未配置'}
                onChange={(event) => update({ password: event.target.value })} />
              {reentry && (
                <p className="mt-2 text-xs text-amber-600 dark:text-amber-400">已修改主机，请重新填写密码。</p>
              )}
              {draft.password_configured && (
                <button type="button" className="mt-2 text-xs text-primary hover:underline disabled:opacity-50" disabled={disabled}
                  onClick={() => update({ password: '', clear_password: !draft.clear_password })}>
                  {draft.clear_password ? '撤销清除密码' : '清除密码'}
                </button>
              )}
            </div>
          </div>

          {proxy && (
            <div className="text-xs text-muted-foreground">
              {usages.length > 0 ? (
                <>
                  正在使用此代理：
                  {usages.map((usage, usageIndex) => (
                    <span key={usage.label}>
                      {usageIndex > 0 && '、'}
                      <Link to={usage.to} className="text-primary hover:underline">{usage.label}</Link>
                    </span>
                  ))}
                </>
              ) : '还没有功能使用此代理，可在各功能的设置页选择它。'}
            </div>
          )}

          <div className="flex flex-wrap items-center gap-3">
            <button type="button" className="btn-secondary" disabled={locked} onClick={() => void test()}>
              {busy === 'test' ? '测试中…' : '测试连接'}
            </button>
            <span className="text-xs text-muted-foreground">经此代理访问 X、OpenAI 与 Anthropic 接口，使用当前填写的内容，无需先保存。</span>
          </div>

          {outcome && (
            <div className={`space-y-1 rounded-lg border border-border bg-muted/30 px-3 py-2 text-xs ${outcome.success ? 'text-foreground' : 'text-destructive'}`}
              aria-live="polite">
              {outcome.lines.map((line, lineIndex) => <p key={lineIndex} className="break-words">{line}</p>)}
            </div>
          )}

          <div className="flex flex-wrap items-center gap-3 border-t border-border pt-4">
            <button type="submit" className="btn-primary" disabled={locked || !dirty}>
              {busy === 'save' ? '保存中…' : proxy ? '保存此代理' : '创建此代理'}
            </button>
            {proxy ? (
              <button type="button" className="btn-secondary" disabled={locked || !dirty}
                onClick={() => setDraft(proxyDraftFrom(proxy))}>
                放弃修改
              </button>
            ) : (
              <button type="button" className="btn-secondary" disabled={busy !== null} onClick={onDiscardNew}>
                取消添加
              </button>
            )}
            {proxy && (
              <button type="button" className="btn-danger ml-auto" disabled={locked || usages.length > 0}
                title={usages.length > 0 ? '仍有功能在使用，先在对应功能中改选其他代理或直接连接' : undefined}
                onClick={() => setConfirmDelete(true)}>
                删除
              </button>
            )}
          </div>
          {proxy && usages.length > 0 && (
            <p className="text-xs text-muted-foreground">仍有功能在使用此代理，先在上面列出的功能中改选其他代理或直接连接，才能删除。</p>
          )}
        </form>
      )}

      <ConfirmDialog
        open={confirmDelete}
        title="删除代理"
        message={`确定删除代理「${proxy?.name ?? ''}」？保存的密码会一并删除，无法恢复。`}
        confirmLabel="删除"
        loading={busy === 'delete'}
        onCancel={() => { if (busy !== 'delete') setConfirmDelete(false) }}
        onConfirm={() => void remove()}
      />
    </div>
  )
}
