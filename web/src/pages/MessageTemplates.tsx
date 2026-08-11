import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Navigate, useParams } from 'react-router-dom'
import { useLoadingOnKeyChange } from '../hooks/useLoadingOnKeyChange'
import { useMountAsync } from '../hooks/useMountAsync'
import { createRetryHandler } from '../utils/retryLoad'
import { getSettings, patchSettings } from '../api/client'
import { ConfirmDialog } from '../components/ConfirmDialog'
import { LoadErrorBanner } from '../components/LoadErrorBanner'
import { PageLoading } from '../components/LoadingSpinner'
import {
  allTemplateFields,
  bilibiliTemplateFields,
  douyinTemplateFields,
  xTemplateFields,
  PREVIEW_SAMPLE_VALUES,
  PREVIEW_SEGMENT_LABELS,
  templateCategoryLabels,
  templatesFromSettings,
  type TemplateCategory,
  type TemplateField,
  type TemplateKey,
} from '../constants/messageTemplates'
import { useToast } from '../contexts/ToastContext'
import { formatApiError } from '../utils/apiError'
import { insertIntoTextarea, renderStrictTemplatePreview } from '../utils/messageTemplate'

const PLATFORM_FIELDS: Record<TemplateCategory, TemplateField[]> = {
  bilibili: bilibiliTemplateFields,
  x: xTemplateFields,
  douyin: douyinTemplateFields,
}

const PLATFORM_DESCRIPTIONS: Record<TemplateCategory, string> = {
  bilibili: '自定义动态、直播推送与 B 站链接解析文案',
  x: '自定义推文推送与 X 链接解析文案',
  douyin: '自定义抖音链接解析文案',
}

function isTemplatePlatform(value: string | undefined): value is TemplateCategory {
  return value === 'bilibili' || value === 'x' || value === 'douyin'
}

function VariablePanel({
  field,
  disabled,
  onInsert,
}: {
  field: TemplateField
  disabled: boolean
  onInsert: (token: string) => void
}) {
  return (
    <aside className="flex min-h-0 w-full shrink-0 flex-col lg:w-52 lg:self-stretch">
      <div className="shrink-0">
        <h4 className="text-sm font-medium text-foreground">可用变量</h4>
        <p className="mt-1 text-xs text-muted-foreground">点击插入到光标位置</p>
      </div>
      <ul className="mt-3 min-h-0 max-h-48 flex-1 space-y-2 overflow-y-auto pr-1 lg:max-h-none">
        {field.variables.map((variable) => (
          <li key={variable.key}>
            <button
              type="button"
              disabled={disabled}
              onClick={() => onInsert(`{${variable.key}}`)}
              className="w-full rounded-lg border border-border px-3 py-2 text-left transition-colors hover:border-primary hover:bg-accent disabled:opacity-50"
            >
              <code className="text-xs font-semibold text-primary">
                {'{'}{variable.key}{'}'}
              </code>
              <p className="mt-0.5 text-xs text-muted-foreground">{variable.label}</p>
              <p className="mt-0.5 text-[11px] text-muted-foreground">{variable.description}</p>
            </button>
          </li>
        ))}
      </ul>
    </aside>
  )
}

function TemplateDetailPanel({
  field,
  value,
  savedValue,
  disabled,
  saving,
  onChange,
  onSave,
  onReset,
  onBack,
}: {
  field: TemplateField
  value: string
  savedValue: string
  disabled: boolean
  saving: boolean
  onChange: (value: string) => void
  onSave: () => void
  onReset: () => void
  onBack: () => void
}) {
  const textareaRef = useRef<HTMLTextAreaElement>(null)
  const dirty = value !== savedValue
  const previewVariables = (() => {
    const base = { ...PREVIEW_SAMPLE_VALUES }
    if (field.key === 'link_template_video') {
      base.url = 'https://www.bilibili.com/video/BV1xx411c7mD'
    } else if (field.key === 'link_template_douyin') {
      base.url = 'https://www.douyin.com/video/7123456789012345678'
      base.author = '抖音用户'
      base.title = '示例抖音视频'
    } else if (field.key === 'link_template_x') {
      base.name = 'Elon Musk'
      base.username = 'elonmusk'
      base.url = 'https://x.com/elonmusk/status/1234567890'
      base.media = '[推文图片]'
      base.text = 'Hello from X!'
      base.tweet_id = '1234567890'
    } else if (
      field.key === 'live_template_start' ||
      field.key === 'live_template_end' ||
      field.key === 'link_template_live'
    ) {
      base.url = 'https://live.bilibili.com/12345'
    } else if (field.category === 'x') {
      base.name = 'Elon Musk'
      base.url = 'https://x.com/elonmusk/status/1234567890'
      base.media = '[推文图片]'
    }
    return base
  })()
  const preview = renderStrictTemplatePreview(value, previewVariables, PREVIEW_SEGMENT_LABELS)

  const handleInsert = (token: string) => {
    const textarea = textareaRef.current
    if (!textarea) {
      onChange(value + token)
      return
    }
    const { nextValue, cursor } = insertIntoTextarea(textarea, value, token)
    onChange(nextValue)
    requestAnimationFrame(() => {
      textarea.focus()
      textarea.setSelectionRange(cursor, cursor)
    })
  }

  return (
    <div className="flex h-full min-h-0 flex-col">
      <div className="shrink-0 flex flex-wrap items-start justify-between gap-3 border-b border-border pb-4 border-border">
        <div className="min-w-0 flex-1">
          <button
            type="button"
            className="mb-2 text-sm text-primary hover:underline lg:hidden"
            onClick={onBack}
          >
            ← 返回列表
          </button>
          <h3 className="text-lg font-semibold text-foreground">{field.label}</h3>
          <p className="mt-1 text-sm text-muted-foreground">{field.description}</p>
        </div>
        <div className="flex shrink-0 flex-wrap items-center gap-2">
          <button
            type="button"
            className="btn-secondary text-sm"
            disabled={disabled || saving}
            onClick={onReset}
          >
            恢复默认
          </button>
          <button
            type="button"
            className="btn-primary text-sm"
            disabled={disabled || saving || !dirty}
            onClick={onSave}
          >
            {saving ? '保存中…' : '保存'}
          </button>
        </div>
      </div>

      <div className="flex min-h-0 flex-1 flex-col gap-4 pt-6 lg:flex-row lg:gap-6">
        <div className="min-h-0 min-w-0 flex-1 overflow-y-auto pr-1">
          <div className="space-y-4">
            <div>
              <label className="label" htmlFor={`template-${field.key}`}>
                模板内容
              </label>
              <textarea
                id={`template-${field.key}`}
                ref={textareaRef}
                className="input mt-1 min-h-32 resize-y font-mono text-sm"
                rows={6}
                maxLength={500}
                value={value}
                disabled={disabled || saving}
                onChange={(e) => onChange(e.target.value)}
              />
              <p className="mt-1 text-xs text-muted-foreground">{value.length}/500</p>
            </div>

            <div>
              <h4 className="mb-2 text-sm font-medium text-foreground">效果预览</h4>
              <div className="rounded-lg border border-border bg-muted px-4 py-3">
                <pre className="whitespace-pre-wrap font-sans text-sm leading-relaxed text-foreground">
                  {preview}
                </pre>
              </div>
              <p className="mt-2 text-xs text-muted-foreground">
                预览严格按模板顺序渲染；{'{media}'}、{'{card}'}、{'{cover}'} 在推送时替换为实际图片。
              </p>
            </div>
          </div>
        </div>

        <VariablePanel field={field} disabled={disabled || saving} onInsert={handleInsert} />
      </div>
    </div>
  )
}

type UnsavedPrompt =
  | { kind: 'switch'; targetKey: TemplateKey; label: string }
  | { kind: 'back'; label: string }

export function MessageTemplatesPage() {
  const { platform: platformParam } = useParams<{ platform: string }>()
  const { showToast } = useToast()
  const [form, setForm] = useState(templatesFromSettings(null))
  const [savedForm, setSavedForm] = useState(templatesFromSettings(null))
  const [selectedKey, setSelectedKey] = useState<TemplateKey | null>(null)
  const [draftValues, setDraftValues] = useState<Partial<Record<TemplateKey, string>>>({})
  const [loading, setLoading] = useLoadingOnKeyChange('message-templates')
  const [error, setError] = useState('')
  const [saving, setSaving] = useState(false)
  const [unsavedPrompt, setUnsavedPrompt] = useState<UnsavedPrompt | null>(null)

  const platform = isTemplatePlatform(platformParam) ? platformParam : null
  const platformFields = platform ? PLATFORM_FIELDS[platform] : []

  const load = useCallback(async () => {
    try {
      const settings = await getSettings()
      const next = templatesFromSettings(settings)
      setForm(next)
      setSavedForm(next)
      setDraftValues({})
      setError('')
    } catch (err) {
      setError(formatApiError(err, '加载失败'))
    } finally {
      setLoading(false)
    }
  }, [setLoading])

  const retryLoad = useMemo(() => createRetryHandler(load, setLoading), [load, setLoading])

  useMountAsync(load)

  useEffect(() => {
    setSelectedKey(null)
    setUnsavedPrompt(null)
  }, [platform])

  const getCurrentValue = (key: TemplateKey) => draftValues[key] ?? form[key]

  const isDirty = (key: TemplateKey) => getCurrentValue(key) !== savedForm[key]

  const discardDraftForKey = (key: TemplateKey) => {
    setDraftValues((current) => {
      const next = { ...current }
      delete next[key]
      return next
    })
  }

  const selectTemplate = (key: TemplateKey) => {
    if (key === selectedKey) return
    if (selectedKey && isDirty(selectedKey)) {
      const field = allTemplateFields.find((item) => item.key === selectedKey)
      setUnsavedPrompt({
        kind: 'switch',
        targetKey: key,
        label: field?.label ?? '当前模板',
      })
      return
    }
    setSelectedKey(key)
  }

  const clearSelection = () => {
    if (selectedKey && isDirty(selectedKey)) {
      const field = allTemplateFields.find((item) => item.key === selectedKey)
      setUnsavedPrompt({
        kind: 'back',
        label: field?.label ?? '当前模板',
      })
      return
    }
    setSelectedKey(null)
  }

  const handleUnsavedConfirm = () => {
    if (!unsavedPrompt || !selectedKey) {
      setUnsavedPrompt(null)
      return
    }
    discardDraftForKey(selectedKey)
    if (unsavedPrompt.kind === 'switch') {
      setSelectedKey(unsavedPrompt.targetKey)
    } else {
      setSelectedKey(null)
    }
    setUnsavedPrompt(null)
  }

  const updateCurrent = (value: string) => {
    if (!selectedKey) return
    setDraftValues((current) => ({ ...current, [selectedKey]: value }))
  }

  const handleSave = async () => {
    if (!selectedKey) return
    const field = allTemplateFields.find((item) => item.key === selectedKey)
    if (!field) return

    const value = getCurrentValue(selectedKey).trim() || field.defaultValue
    setSaving(true)
    try {
      const updated = await patchSettings({ [selectedKey]: value })
      const next = templatesFromSettings(updated)
      setForm(next)
      setSavedForm(next)
      setDraftValues((current) => {
        const copy = { ...current }
        delete copy[selectedKey]
        return copy
      })
      showToast('success', '模板已保存')
    } catch (err) {
      showToast('error', formatApiError(err, '保存失败'))
    } finally {
      setSaving(false)
    }
  }

  const handleReset = () => {
    if (!selectedKey) return
    const field = getTemplateFieldSafe(selectedKey)
    if (!field) return
    setDraftValues((current) => ({ ...current, [selectedKey]: field.defaultValue }))
  }

  const selectedField = selectedKey
    ? platformFields.find((item) => item.key === selectedKey) ?? null
    : null
  const showSplit = selectedKey !== null
  const listHiddenOnMobile = showSplit && selectedField

  if (!platform) {
    return <Navigate to="/templates/bilibili" replace />
  }

  const pageTitle = `${templateCategoryLabels[platform]}消息模板`
  const pageDescription = PLATFORM_DESCRIPTIONS[platform]

  if (loading && !error) {
    return (
      <div className="flex h-[calc(100dvh-4rem-2rem)] flex-col gap-6 overflow-hidden lg:h-[calc(100dvh-4rem-4rem)]">
        <div className="shrink-0">
          <h2 className="text-2xl font-bold text-foreground">{pageTitle}</h2>
          <p className="mt-1 text-sm text-muted-foreground">{pageDescription}</p>
        </div>
        <PageLoading />
      </div>
    )
  }

  return (
    <div className="flex h-[calc(100dvh-4rem-2rem)] flex-col gap-6 overflow-hidden lg:h-[calc(100dvh-4rem-4rem)]">
      <div className="shrink-0">
        <h2 className="text-2xl font-bold text-foreground">{pageTitle}</h2>
        <p className="mt-1 text-sm text-muted-foreground">{pageDescription}</p>
      </div>

      {error && (
        <div className="shrink-0">
          <LoadErrorBanner message={error} onRetry={retryLoad} />
        </div>
      )}

      <div
        className={`flex min-h-0 flex-1 overflow-hidden rounded-lg border border-border ${
          showSplit ? 'divide-x divide-border' : ''
        }`}
      >
        <aside
          className={`flex min-h-0 flex-col bg-muted/40 ${
            listHiddenOnMobile ? 'hidden lg:flex' : ''
          } ${showSplit ? 'w-full lg:w-72' : 'w-full'}`}
        >
          <div className="flex min-h-0 flex-1 flex-col">
            <div className="shrink-0 border-b border-border px-3 py-2.5 border-border">
              <p className="text-xs font-medium text-muted-foreground">模板列表</p>
            </div>
            <nav className="min-h-0 flex-1 overflow-y-auto p-2">
              <ul>
                {platformFields.map((field) => {
                  const isSelected = selectedKey === field.key
                  const dirty = isDirty(field.key)
                  return (
                    <li key={field.key}>
                      <button
                        type="button"
                        onClick={() => selectTemplate(field.key)}
                        className={`mb-1 w-full rounded-lg px-3 py-2.5 text-left transition-colors ${
                          isSelected
                            ? 'bg-sidebar-accent text-sidebar-primary'
                            : 'hover:bg-accent'
                        }`}
                      >
                        <div className="flex items-start justify-between gap-2">
                          <p className="text-sm font-medium">{field.label}</p>
                          {dirty && (
                            <span
                              className="mt-1.5 h-2 w-2 shrink-0 rounded-full bg-amber-500"
                              title="有未保存的修改"
                            />
                          )}
                        </div>
                        <p className="mt-0.5 line-clamp-2 font-mono text-xs text-muted-foreground">
                          {getCurrentValue(field.key)}
                        </p>
                      </button>
                    </li>
                  )
                })}
              </ul>
            </nav>
          </div>
        </aside>

        {showSplit && selectedField && (
          <main className="min-h-0 min-w-0 flex-1 overflow-hidden bg-card p-4 lg:p-6">
            <TemplateDetailPanel
              field={selectedField}
              value={getCurrentValue(selectedKey)}
              savedValue={savedForm[selectedKey]}
              disabled={Boolean(error)}
              saving={saving}
              onChange={updateCurrent}
              onSave={() => void handleSave()}
              onReset={handleReset}
              onBack={clearSelection}
            />
          </main>
        )}

        {!showSplit && !error && (
          <main className="hidden min-h-0 min-w-0 flex-1 items-center justify-center overflow-y-auto bg-card p-6 text-sm text-muted-foreground lg:flex">
            请从左侧选择一个模板
          </main>
        )}
      </div>

      <ConfirmDialog
        open={unsavedPrompt !== null}
        title="未保存的修改"
        message={
          unsavedPrompt ? (
            <>
              「{unsavedPrompt.label}」有未保存的修改，
              {unsavedPrompt.kind === 'switch' ? '切换模板' : '返回列表'}
              后将丢失这些更改。
            </>
          ) : (
            ''
          )
        }
        confirmLabel={unsavedPrompt?.kind === 'switch' ? '仍要切换' : '仍要返回'}
        cancelLabel="继续编辑"
        onCancel={() => setUnsavedPrompt(null)}
        onConfirm={handleUnsavedConfirm}
      />
    </div>
  )
}

function getTemplateFieldSafe(key: TemplateKey): TemplateField | undefined {
  return allTemplateFields.find((item) => item.key === key)
}
