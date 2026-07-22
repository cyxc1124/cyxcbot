import { CommandAliasCard } from './CommandAliasCard'
import { LoadErrorBanner } from './LoadErrorBanner'
import { PageLoading } from './LoadingSpinner'
import {
  RUST_PLAYER_COMMAND_FIELDS,
  type RustPlayerCommandId,
} from '../constants/commandAliases'
import { useRustPlayerCommands } from '../hooks/useRustPlayerCommands'

export function RustPlayerCommandsTab() {
  const { form, loading, error, saving, retryLoad, updateField, handleReset, handleSubmit } =
    useRustPlayerCommands()

  if (loading && !error && RUST_PLAYER_COMMAND_FIELDS.every((field) => !form[field.id])) {
    return <PageLoading />
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-6">
      <p className="text-sm text-muted-foreground">
        自定义 Rust 群管相关命令的触发词，保存后立即生效。关闭后该命令不再响应；已填写的触发词会保留，方便随时重新启用。触发词会与 RCON
        绑定及全局命令做冲突检测。
      </p>

      {error && <LoadErrorBanner message={error} onRetry={retryLoad} />}

      {RUST_PLAYER_COMMAND_FIELDS.map((field) => {
        const value = form[field.id]
        if (!value) return null
        return (
          <CommandAliasCard
            key={field.id}
            field={field}
            value={value}
            disabled={saving}
            onToggle={(enabled) => updateField(field.id as RustPlayerCommandId, { enabled })}
            onTextChange={(text) => updateField(field.id as RustPlayerCommandId, { text })}
            onReset={() => handleReset(field.id as RustPlayerCommandId)}
          />
        )
      })}

      <button type="submit" className="btn-primary" disabled={saving}>
        {saving ? '保存中…' : '保存群管命令'}
      </button>
    </form>
  )
}
