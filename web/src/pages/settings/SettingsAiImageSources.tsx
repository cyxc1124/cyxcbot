import { useId, useState, type FormEvent } from 'react'
import { Link } from 'react-router-dom'
import type { Settings } from '../../api/types'
import { ToggleSwitch } from '../../components/ToggleSwitch'
import { ProxySettingCard } from './ProxySettingCard'
import { useSettingsForm } from './SettingsContext'

type Sources = { local: boolean; openaiC2pa: boolean; synthid: boolean; proxyId: string }

function sourcesFromSettings(settings: Settings | null): Sources {
  return {
    local: settings?.ai_image_local_c2pa_enabled ?? true,
    openaiC2pa: settings?.ai_image_openai_c2pa_enabled ?? true,
    synthid: settings?.ai_image_openai_synthid_enabled ?? true,
    proxyId: settings?.ai_image_openai_proxy_id ?? '',
  }
}

function SourceToggleRow({ label, description, checked, disabled, onChange }: {
  label: string
  description: string
  checked: boolean
  disabled: boolean
  onChange: (checked: boolean) => void
}) {
  const id = useId()
  return (
    <div className="flex items-center gap-4 rounded-lg border border-border bg-muted/30 px-3 py-3">
      <div className="min-w-0 flex-1">
        <div id={id} className="text-sm font-medium text-foreground">{label}</div>
        <p className="mt-0.5 text-xs text-muted-foreground">{description}</p>
      </div>
      <ToggleSwitch checked={checked} disabled={disabled} onChange={onChange} ariaLabelledBy={id} />
    </div>
  )
}

export function SettingsAiImageSourcesPage() {
  const { settings, formDisabled, saving, savePartial } = useSettingsForm()
  const [sources, setSources] = useState(() => sourcesFromSettings(settings))
  const [openaiApiKey, setOpenaiApiKey] = useState('')
  const [syncedSettings, setSyncedSettings] = useState(settings)
  const disabled = formDisabled || saving
  const keyConfigured = Boolean(settings?.ai_image_openai_api_key?.configured)
  const openaiEnabled = sources.openaiC2pa || sources.synthid

  if (settings !== syncedSettings) {
    setSyncedSettings(settings)
    setSources(sourcesFromSettings(settings))
    setOpenaiApiKey('')
  }

  const handleSubmit = (event: FormEvent) => {
    event.preventDefault()
    void savePartial({
      ai_image_local_c2pa_enabled: sources.local,
      ai_image_openai_c2pa_enabled: sources.openaiC2pa,
      ai_image_openai_synthid_enabled: sources.synthid,
      ai_image_openai_proxy_id: sources.proxyId,
      ...(openaiApiKey.trim() ? { ai_image_openai_api_key: openaiApiKey.trim() } : {}),
    })
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-6">
      <p className="text-sm text-muted-foreground">
        OneBot 群聊或私聊中引用一张图片发送 <Link to="/ai-image/command" className="text-primary hover:underline">触发词</Link>
        （默认「ai吗？」）即可检测。关闭的来源不会执行，也不会出现在回复中；可再接入{' '}
        <Link to="/ai-image/vision" className="text-primary hover:underline">视觉模型</Link> 共同判断。未检出不能证明图片由人类创作。
      </p>

      <div className="card space-y-4">
        <div>
          <h3 className="font-semibold text-foreground">检测来源</h3>
          <p className="mt-1 text-sm text-muted-foreground">
            OpenAI C2PA 与 SynthID 由同一次 OpenAI Content Provenance 请求返回：任一开启就会上传原图，两项都关闭时不调用 OpenAI。
          </p>
        </div>
        <SourceToggleRow label="本地 C2PA" checked={sources.local} disabled={disabled}
          description="在机器人本机读取并校验图片内嵌的 C2PA 凭证，可识别各厂商的 AI 生成声明；不上传图片，无接口费用。"
          onChange={(local) => setSources({ ...sources, local })} />
        <SourceToggleRow label="OpenAI C2PA" checked={sources.openaiC2pa} disabled={disabled}
          description="识别 OpenAI 签发的 AI 生成凭证并返回签名状态与签发者。"
          onChange={(openaiC2pa) => setSources({ ...sources, openaiC2pa })} />
        <SourceToggleRow label="SynthID（OpenAI）" checked={sources.synthid} disabled={disabled}
          description="检测 OpenAI 接口支持的 SynthID 水印；不检测所有厂商的水印。"
          onChange={(synthid) => setSources({ ...sources, synthid })} />
        {openaiEnabled && !keyConfigured && !openaiApiKey.trim() && (
          <p className="text-xs text-amber-600 dark:text-amber-400">
            尚未配置 OpenAI API Key，OpenAI C2PA / SynthID 会在回复中显示为未完成检测。
          </p>
        )}
      </div>

      <div className="card space-y-4">
        <div>
          <h3 className="font-semibold text-foreground">OpenAI API Key</h3>
          <p className="mt-1 text-sm text-muted-foreground">
            用于 OpenAI Content Provenance 接口。密钥加密保存，读取设置时不会返回；接口费用以 OpenAI 实际计费为准。
          </p>
        </div>
        <div>
          <label className="label" htmlFor="ai_image_openai_api_key">API Key</label>
          <input id="ai_image_openai_api_key" type="password" autoComplete="new-password"
            className="input font-mono text-sm" value={openaiApiKey} disabled={disabled}
            placeholder={keyConfigured ? '已配置，留空保留原密钥' : '未配置'}
            onChange={(event) => setOpenaiApiKey(event.target.value)} />
        </div>
        {keyConfigured && (
          <button type="button" className="btn-secondary" disabled={disabled}
            onClick={() => { void savePartial({ ai_image_openai_api_key: '' }) }}>
            清除检测密钥
          </button>
        )}
      </div>

      <ProxySettingCard
        field="ai_image_openai_proxy_id"
        title="OpenAI 来源检测的代理"
        description="OpenAI C2PA 与 SynthID 检测请求经此代理访问 api.openai.com，与下方按钮一起保存。不使用代理时直接连接，并仍遵循运行环境的代理变量。视觉模型的代理在每个模型中单独选择。"
        value={sources.proxyId}
        onChange={(proxyId) => setSources({ ...sources, proxyId })}
      />

      <button type="submit" className="btn-primary" disabled={disabled}>{saving ? '保存中…' : '保存设置'}</button>
    </form>
  )
}
