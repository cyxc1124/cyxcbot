import { useState } from 'react'
import {
  createVisionProvider,
  deleteVisionProvider,
  getVisionBalance,
  listVisionModels,
  testVisionProvider,
  updateVisionProvider,
} from '../../api/client'
import type { AiImageVisionProvider, ProxyEntry, VisionApiType, VisionModelInfo, VisionProvidersResult } from '../../api/types'
import { ChoiceCardGroup } from '../../components/ChoiceCardGroup'
import { ConfirmDialog } from '../../components/ConfirmDialog'
import { Icon } from '../../components/Icon'
import { ProxyPicker } from '../../components/ProxyPicker'
import { ToggleSwitch } from '../../components/ToggleSwitch'
import { useToast } from '../../contexts/ToastContext'
import { formatApiError } from '../../utils/apiError'
import {
  DEFAULT_VISION_BASE_URLS,
  balanceProviderName,
  describeBalance,
  describeTest,
  draftFromProvider,
  isDirty,
  needsKeyReentry,
  newDraft,
  probePayload,
  providerChanges,
  providerInput,
  providerSummary,
  sortModels,
  switchApiType,
  validateDraft,
  type VisionProviderDraft,
} from './aiImageVisionForm'

const API_TYPE_OPTIONS = [
  { value: 'openai', label: 'OpenAI 兼容', description: 'Chat Completions：OpenAI 及兼容该格式的服务', icon: <Icon name="globe" className="size-5" /> },
  { value: 'anthropic', label: 'Anthropic', description: 'Messages API：Claude 及兼容该格式的服务', icon: <Icon name="globe" className="size-5" /> },
] as const

const MODEL_PLACEHOLDERS: Record<VisionApiType, string> = {
  openai: '如 gpt-4o',
  anthropic: '如 claude-sonnet-4-5',
}

const BADGE = 'rounded bg-amber-500/15 px-1.5 py-px text-[10px] font-medium text-amber-600 dark:text-amber-400'

type Probe = 'models' | 'test' | 'balance'
type Busy = Probe | 'save' | 'toggle' | 'delete'
type Outcome = { success: boolean; lines: string[] }

export function VisionProviderCard({ provider, initialDraft, index, proxies, disabled, onProvidersChange, onDiscardNew }: {
  /** 已保存的供应商；新建卡片省略 */
  provider?: AiImageVisionProvider
  initialDraft?: VisionProviderDraft
  index: number
  proxies: ProxyEntry[]
  disabled: boolean
  /** 保存、启停或删除成功后的完整列表 */
  onProvidersChange: (result: VisionProvidersResult) => void
  onDiscardNew?: () => void
}) {
  const { showToast } = useToast()
  const [draft, setDraft] = useState(() => (provider ? draftFromProvider(provider) : initialDraft ?? newDraft()))
  // 已保存的供应商默认收起，新建的默认展开。
  const [expanded, setExpanded] = useState(!provider)
  const [busy, setBusy] = useState<Busy | null>(null)
  const [models, setModels] = useState<VisionModelInfo[]>([])
  const [outcomes, setOutcomes] = useState<Partial<Record<Probe, Outcome>>>({})
  const [confirmDelete, setConfirmDelete] = useState(false)

  const id = (field: string) => `vision-${draft.key}-${field}`
  const update = (patch: Partial<VisionProviderDraft>) => setDraft({ ...draft, ...patch })
  const record = (action: Probe, outcome: Outcome) => setOutcomes((current) => ({ ...current, [action]: outcome }))
  const reentry = needsKeyReentry(draft, provider)
  const dirty = isDirty(draft, provider)
  const enabled = provider ? provider.enabled : draft.enabled
  const balanceProvider = balanceProviderName(draft)
  const locked = disabled || busy !== null
  const title = (provider ? provider.name : draft.name.trim()) || `新视觉模型 ${index + 1}`
  const proxyName = (proxyId: string) => proxies.find((proxy) => proxy.id === proxyId)?.name ?? ''
  const summary = provider
    ? providerSummary(provider, provider.api_key_configured, proxyName(provider.proxy_id))
    : providerSummary(draft, draft.api_key.trim() !== '', proxyName(draft.proxy_id))

  const run = async (action: Probe) => {
    if (reentry) {
      record(action, { success: false, lines: ['已修改接口类型或地址，请先重新填写 API Key。'] })
      return
    }
    setBusy(action)
    try {
      const payload = probePayload(draft)
      if (action === 'models') {
        const result = await listVisionModels(payload)
        if (result.success) setModels(sortModels(result.models))
        record(action, { success: result.success, lines: [result.message] })
      } else if (action === 'test') {
        const result = await testVisionProvider(payload)
        record(action, { success: result.success, lines: describeTest(result) })
      } else {
        const result = await getVisionBalance(payload)
        record(action, { success: result.success, lines: describeBalance(result) })
      }
    } catch (err) {
      record(action, { success: false, lines: [formatApiError(err, '请求失败')] })
    } finally {
      setBusy(null)
    }
  }

  const save = async () => {
    const error = validateDraft(draft, provider)
    if (error) {
      showToast('error', error)
      return
    }
    setBusy('save')
    try {
      const result = provider
        ? await updateVisionProvider(provider.id, providerChanges(draft))
        : await createVisionProvider(providerInput(draft))
      const saved = result.providers.find((item) => item.id === result.id)
      if (saved) setDraft(draftFromProvider(saved))
      setExpanded(false)
      showToast('success', `已保存「${saved?.name ?? draft.name.trim()}」`)
      onProvidersChange(result)
    } catch (err) {
      showToast('error', formatApiError(err, '保存失败'))
    } finally {
      setBusy(null)
    }
  }

  const toggle = async (next: boolean) => {
    if (!provider) {
      update({ enabled: next })
      return
    }
    setBusy('toggle')
    try {
      onProvidersChange(await updateVisionProvider(provider.id, { enabled: next }))
      showToast('success', `已${next ? '启用' : '停用'}「${provider.name}」`)
    } catch (err) {
      showToast('error', formatApiError(err, '保存失败'))
    } finally {
      setBusy(null)
    }
  }

  const remove = async () => {
    if (!provider) return
    setBusy('delete')
    try {
      const result = await deleteVisionProvider(provider.id)
      setConfirmDelete(false)
      showToast('success', `已删除「${provider.name}」`)
      onProvidersChange(result)
    } catch (err) {
      showToast('error', formatApiError(err, '删除失败'))
    } finally {
      setBusy(null)
    }
  }

  const results = (['models', 'test', 'balance'] as const).filter((action) => outcomes[action])

  return (
    <div className="card">
      <div className="flex items-center gap-3">
        <button type="button" className="flex min-w-0 flex-1 items-center gap-3 rounded-lg text-left"
          aria-expanded={expanded} aria-controls={id('body')} onClick={() => setExpanded(!expanded)}>
          <Icon name="chevron-down" className={`size-4 shrink-0 text-muted-foreground transition-transform ${expanded ? '' : '-rotate-90'}`} />
          <span className="min-w-0">
            <span className="flex flex-wrap items-center gap-2">
              <span id={id('title')} className="truncate font-semibold text-foreground">{title}</span>
              {!provider && <span className={BADGE}>新建，未保存</span>}
              {provider && dirty && <span className={BADGE}>有未保存修改</span>}
            </span>
            <span className="mt-0.5 block truncate text-xs text-muted-foreground">{summary}</span>
          </span>
        </button>
        <div className="flex shrink-0 items-center gap-2">
          <span className={`text-xs ${enabled ? 'text-emerald-600 dark:text-emerald-400' : 'text-muted-foreground'}`}>
            {enabled ? '已启用' : '已停用'}
          </span>
          <ToggleSwitch checked={enabled} disabled={locked} busy={busy === 'toggle'} ariaLabelledBy={id('title')}
            onChange={(next) => void toggle(next)} />
        </div>
      </div>

      {expanded && (
        <form id={id('body')} className="mt-4 space-y-4 border-t border-border pt-4"
          onSubmit={(event) => { event.preventDefault(); void save() }}>
          <ChoiceCardGroup label="接口类型" value={draft.api_type} options={API_TYPE_OPTIONS} disabled={disabled}
            onChange={(apiType) => setDraft(switchApiType(draft, apiType))} />

          <div className="grid gap-4 sm:grid-cols-2">
            <div>
              <label className="label" htmlFor={id('name')}>名称</label>
              <input id={id('name')} className="input" maxLength={32} value={draft.name} placeholder="回复中显示的名称"
                disabled={disabled} onChange={(event) => update({ name: event.target.value })} />
            </div>
            <div>
              <div className="flex items-center justify-between">
                <label className="label" htmlFor={id('model')}>模型</label>
                <button type="button" className="text-xs text-primary hover:underline disabled:opacity-50"
                  disabled={locked} onClick={() => void run('models')}>
                  {busy === 'models' ? '获取中…' : '获取模型列表'}
                </button>
              </div>
              <input id={id('model')} className="input font-mono text-sm" maxLength={128} value={draft.model}
                placeholder={MODEL_PLACEHOLDERS[draft.api_type]} disabled={disabled}
                onChange={(event) => update({ model: event.target.value })} />
              {models.length > 0 && (
                <select id={id('model-list')} aria-label="从获取的模型中选择" className="input mt-2 text-sm" value=""
                  disabled={disabled} onChange={(event) => { if (event.target.value) update({ model: event.target.value }) }}>
                  <option value="">从获取的 {models.length} 个模型中选择…</option>
                  {models.map((model) => (
                    <option key={model.id} value={model.id}>
                      {model.id}{model.name ? `（${model.name}）` : ''}
                      {model.vision === true ? ' · 支持图片' : model.vision === false ? ' · 不支持图片' : ''}
                    </option>
                  ))}
                </select>
              )}
            </div>
            <div className="sm:col-span-2">
              <label className="label" htmlFor={id('base-url')}>接口地址（可选）</label>
              <input id={id('base-url')} className="input font-mono text-sm" maxLength={256} value={draft.base_url}
                placeholder={DEFAULT_VISION_BASE_URLS[draft.api_type]} disabled={disabled}
                onChange={(event) => update({ base_url: event.target.value })} />
              <p className="mt-2 text-xs text-muted-foreground">
                {draft.api_type === 'anthropic'
                  ? '留空使用官方地址。填写服务根地址，请求时追加 /v1/messages。'
                  : '留空使用官方地址。填写到版本路径（如 …/v1），请求时追加 /chat/completions；本地服务可使用 http://。'}
              </p>
            </div>
            <div className="sm:col-span-2">
              <label className="label" htmlFor={id('api-key')}>API Key</label>
              <input id={id('api-key')} type="password" autoComplete="new-password" className="input font-mono text-sm"
                value={draft.api_key} disabled={disabled}
                placeholder={draft.clear_key ? '保存后清除密钥' : draft.api_key_configured ? '已配置，留空保留原密钥' : '未配置；无需鉴权的本地服务可留空'}
                onChange={(event) => update({ api_key: event.target.value })} />
              {reentry && (
                <p className="mt-2 text-xs text-amber-600 dark:text-amber-400">已修改接口类型或地址，请重新填写 API Key。</p>
              )}
              {draft.api_key_configured && (
                <button type="button" className="mt-2 text-xs text-primary hover:underline disabled:opacity-50" disabled={disabled}
                  onClick={() => update({ api_key: '', clear_key: !draft.clear_key })}>
                  {draft.clear_key ? '撤销清除密钥' : '清除密钥'}
                </button>
              )}
            </div>
          </div>

          <div>
            <label className="label" htmlFor={id('proxy')}>代理</label>
            <ProxyPicker id={id('proxy')} value={draft.proxy_id} proxies={proxies} disabled={disabled}
              onChange={(proxyId) => update({ proxy_id: proxyId })} />
            <p className="mt-2 text-xs text-muted-foreground">
              检测、获取模型、测试和查询余额都经所选代理连接；不使用代理时直接连接，并仍遵循运行环境的代理变量。
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-3">
            <button type="button" className="btn-secondary" disabled={locked || !draft.model.trim()}
              title={draft.model.trim() ? '用生成的测试图走一遍检测请求' : '请先填写模型'} onClick={() => void run('test')}>
              {busy === 'test' ? '测试中…' : '测试响应'}
            </button>
            {balanceProvider && (
              <button type="button" className="btn-secondary" disabled={locked} onClick={() => void run('balance')}>
                {busy === 'balance' ? '查询中…' : `查询 ${balanceProvider} 余额`}
              </button>
            )}
          </div>

          {results.length > 0 && (
            <div className="space-y-2 rounded-lg border border-border bg-muted/30 px-3 py-2 text-xs" aria-live="polite">
              {results.map((action) => (
                <div key={action} className={outcomes[action]!.success ? 'text-foreground' : 'text-destructive'}>
                  {outcomes[action]!.lines.map((line, lineIndex) => <p key={lineIndex} className="break-words">{line}</p>)}
                </div>
              ))}
            </div>
          )}

          <div className="flex flex-wrap items-center gap-3 border-t border-border pt-4">
            <button type="submit" className="btn-primary" disabled={locked || !dirty}>
              {busy === 'save' ? '保存中…' : provider ? '保存此模型' : '创建此模型'}
            </button>
            {provider ? (
              <button type="button" className="btn-secondary" disabled={locked || !dirty}
                onClick={() => setDraft(draftFromProvider(provider))}>
                放弃修改
              </button>
            ) : (
              <button type="button" className="btn-secondary" disabled={busy !== null} onClick={onDiscardNew}>
                取消添加
              </button>
            )}
            {provider && (
              <button type="button" className="btn-danger ml-auto" disabled={locked} onClick={() => setConfirmDelete(true)}>
                删除
              </button>
            )}
          </div>
        </form>
      )}

      <ConfirmDialog
        open={confirmDelete}
        title="删除视觉模型"
        message={`确定删除「${provider?.name ?? ''}」？保存的 API Key 会一并删除，无法恢复。`}
        confirmLabel="删除"
        loading={busy === 'delete'}
        onCancel={() => { if (busy !== 'delete') setConfirmDelete(false) }}
        onConfirm={() => void remove()}
      />
    </div>
  )
}
