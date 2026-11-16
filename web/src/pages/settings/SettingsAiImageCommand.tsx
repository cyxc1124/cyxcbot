import { useState, type FormEvent } from 'react'
import { CommandAliasCard } from '../../components/CommandAliasCard'
import { AI_IMAGE_COMMAND_FIELDS } from '../../constants/commandAliases'
import { useToast } from '../../contexts/ToastContext'
import { buildForm, parseLines } from './commandsForm'
import { useSettingsForm } from './SettingsContext'

const FIELD = AI_IMAGE_COMMAND_FIELDS[0]

export function SettingsAiImageCommandPage() {
  const { showToast } = useToast()
  const { settings, formDisabled, saving, savePartial } = useSettingsForm()
  const [form, setForm] = useState(() => buildForm(settings, AI_IMAGE_COMMAND_FIELDS))
  const [syncedSettings, setSyncedSettings] = useState(settings)
  const value = form[FIELD.id]!
  const disabled = formDisabled || saving

  if (settings !== syncedSettings) {
    setSyncedSettings(settings)
    setForm(buildForm(settings, AI_IMAGE_COMMAND_FIELDS))
  }

  const update = (patch: Partial<typeof value>) => setForm({ ...form, [FIELD.id]: { ...value, ...patch } })

  const handleSubmit = (event: FormEvent) => {
    event.preventDefault()
    const triggers = parseLines(value.text)
    if (value.enabled && triggers.length === 0) {
      showToast('error', `「${FIELD.label}」已启用但未填写触发词`)
      return
    }
    void savePartial({ command_aliases: { [FIELD.id]: { enabled: value.enabled, triggers } } })
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-6">
      <div className="space-y-2 text-sm text-muted-foreground">
        <p>
          在 OneBot 群聊或私聊中引用一张图片，再发送触发词即可检测；官方 QQ Bot 暂不支持引用图片。保存后立即生效，关闭后不再响应，已填写的触发词会保留。
        </p>
        <p>
          可直接发送触发词、加命令前缀发送，或 @机器人 后发送；群聊中引用消息后 @机器人，或回复机器人的消息时，消息以触发词开头或结尾也会触发（如「这张是ai吗？」）。触发词会与其他命令做冲突检查。
        </p>
        {settings && settings.command_prefixes.length > 0 && (
          <p className="text-xs">
            当前生效的命令前缀：
            <code className="mx-1 rounded bg-secondary px-1.5 py-0.5 font-mono">{settings.command_prefixes.join(' ')}</code>
          </p>
        )}
      </div>

      <CommandAliasCard
        field={FIELD}
        value={value}
        disabled={disabled}
        onToggle={(enabled) => update({ enabled })}
        onTextChange={(text) => update({ text })}
        onReset={() => update({ enabled: true, text: FIELD.defaultTriggers.join('\n') })}
      />

      <button type="submit" className="btn-primary" disabled={disabled}>{saving ? '保存中…' : '保存设置'}</button>
    </form>
  )
}
