import { useState } from 'react'
import { Link } from 'react-router-dom'
import type { VisionProvidersResult } from '../../api/types'
import { ToggleSwitch } from '../../components/ToggleSwitch'
import { newDraft, type VisionProviderDraft } from './aiImageVisionForm'
import { useSettingsForm } from './SettingsContext'
import { VisionProviderCard } from './VisionProviderCard'

export function SettingsAiImageVisionPage() {
  const { settings, setSettings, formDisabled, saving, savePartial } = useSettingsForm()
  const [newDrafts, setNewDrafts] = useState<VisionProviderDraft[]>([])
  const providers = settings?.ai_image_vision_providers ?? []
  const proxies = settings?.proxies ?? []
  const enabledCount = providers.filter((provider) => provider.enabled).length
  const visionEnabled = settings?.ai_image_vision_enabled ?? true

  // 只替换供应商列表，其他卡片里未保存的修改保持不变。
  const apply = (result: VisionProvidersResult) => {
    setSettings((current) => (current ? { ...current, ai_image_vision_providers: result.providers } : current))
  }
  const dropNew = (key: string) => setNewDrafts((current) => current.filter((draft) => draft.key !== key))

  return (
    <div className="space-y-6">
      <div className="space-y-2 text-sm text-muted-foreground">
        <p>
          启用的视觉模型与 <Link to="/ai-image/sources" className="text-primary hover:underline">来源检测</Link>{' '}
          并行运行，各自给出「倾向 AI 生成 / 倾向非 AI 生成 / 无法判断」，回复中汇总多数意见。视觉模型只根据画面推测，可能误判，
          结论仅供参考；受信任的来源证据始终优先。
        </p>
        <p>
          数量不设上限，但每次检测都会把图片发给每个已启用的模型：启用越多，费用越高，回复也越长，耗时取决于最慢的模型（单个最多 60 秒）。
          大图、动图会缩放为不超过 2048 像素的首帧 JPEG 再发送；模型需支持图片输入，费用以各供应商计费为准。
        </p>
        <p>
          点击模型标题展开或收起详情。每个模型单独保存，标题栏的开关立即生效；「获取模型列表」「测试响应」「查询余额」使用当前填写的内容，
          无需先保存。测试只发送一张生成的测试图，会产生一次正常调用费用；余额查询目前支持 DeepSeek 与 Kimi 官方接口。
        </p>
      </div>

      <div className="card flex items-center gap-4">
        <div className="min-w-0 flex-1">
          <h3 id="ai-image-vision-enabled" className="font-semibold text-foreground">启用视觉模型</h3>
          <p className="mt-1 text-sm text-muted-foreground">
            总开关，切换后立即生效。关闭后检测时不调用任何视觉模型，回复中也不出现视觉模型结果；下方各模型的配置和启停状态保留，仍可编辑和测试。
          </p>
        </div>
        <ToggleSwitch checked={visionEnabled} disabled={formDisabled} busy={saving} ariaLabelledBy="ai-image-vision-enabled"
          onChange={(enabled) => void savePartial({ ai_image_vision_enabled: enabled })} />
      </div>

      {providers.length === 0 && newDrafts.length === 0 ? (
        <div className="card text-sm text-muted-foreground">尚未添加视觉模型，图片检测只使用来源检测。</div>
      ) : (
        <div className="space-y-3">
          {providers.map((provider, index) => (
            <VisionProviderCard key={provider.id} provider={provider} index={index} proxies={proxies} disabled={formDisabled}
              onProvidersChange={apply} />
          ))}
          {newDrafts.map((draft, offset) => (
            <VisionProviderCard key={draft.key} initialDraft={draft} index={providers.length + offset} proxies={proxies} disabled={formDisabled}
              onProvidersChange={(result) => { dropNew(draft.key); apply(result) }}
              onDiscardNew={() => dropNew(draft.key)} />
          ))}
        </div>
      )}

      <div className="flex flex-wrap items-center gap-3">
        <button type="button" className="btn-secondary" disabled={formDisabled}
          onClick={() => setNewDrafts([...newDrafts, newDraft()])}>
          添加视觉模型
        </button>
        <span className="text-xs text-muted-foreground">
          已保存 {providers.length} 个，启用 {enabledCount} 个{visionEnabled ? '' : '（总开关已关闭，检测时都不调用）'}。
        </span>
      </div>
    </div>
  )
}
