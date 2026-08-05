import { ConfirmDialog } from './ConfirmDialog'
import { LoadErrorBanner } from './LoadErrorBanner'
import { PageLoading } from './LoadingSpinner'
import { ToggleSwitch } from './ToggleSwitch'
import { useRustRconCustomCommands } from '../hooks/useRustRconCustomCommands'

export function RustRconCustomCommandsTab() {
  const {
    items,
    bindings,
    bindingLabel,
    loading,
    error,
    retryLoad,
    showForm,
    editingId,
    form,
    setForm,
    saving,
    togglingId,
    deleteTarget,
    setDeleteTarget,
    deleting,
    openCreate,
    openEdit,
    resetForm,
    handleSubmit,
    handleToggleEnabled,
    handleDelete,
  } = useRustRconCustomCommands()

  if (loading && items.length === 0 && !error) {
    return <PageLoading />
  }

  return (
    <div className="space-y-6">
      <div className="card space-y-4">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h3 className="font-semibold text-foreground">自定义指令</h3>
            <p className="mt-1 text-sm text-muted-foreground">
              配置群内快捷 RCON 指令。模板中可使用{' '}
              <code className="font-mono text-xs">{'{steamid}'}</code>{' '}
              占位符。群内用法：
              <code className="font-mono text-xs">@机器人 指令名 @群用户</code>
              （需对方已绑定 SteamID）或{' '}
              <code className="font-mono text-xs">@机器人 指令名 SteamID64</code>
              。每条指令单独配置允许执行的 QQ；群须开启 Rust 远控。
            </p>
          </div>
          {!showForm && (
            <button
              type="button"
              className="btn-primary shrink-0"
              onClick={openCreate}
              disabled={bindings.length === 0}
            >
              添加指令
            </button>
          )}
        </div>

        {error && <LoadErrorBanner message={error} onRetry={retryLoad} />}

        {bindings.length === 0 && !error && (
          <p className="text-sm text-muted-foreground">
            请先在「服务器绑定」中添加至少一台 RCON 服务器。
          </p>
        )}

        {showForm && (
          <form onSubmit={handleSubmit} className="space-y-4 rounded-lg border border-border p-4">
            <h4 className="font-medium text-foreground">
              {editingId === null ? '添加自定义指令' : '编辑自定义指令'}
            </h4>
            <div className="grid gap-4 sm:grid-cols-2">
              <label className="space-y-1">
                <span className="text-xs text-muted-foreground">指令名</span>
                <input
                  className="input w-full"
                  value={form.name}
                  disabled={saving}
                  placeholder="功能10"
                  onChange={(e) => setForm((prev) => ({ ...prev, name: e.target.value }))}
                />
              </label>
              <label className="space-y-1">
                <span className="text-xs text-muted-foreground">RCON 服务器</span>
                <select
                  className="input w-full"
                  value={form.binding_id}
                  disabled={saving}
                  onChange={(e) =>
                    setForm((prev) => ({ ...prev, binding_id: e.target.value }))
                  }
                >
                  <option value="">请选择</option>
                  {bindings.map((binding) => (
                    <option key={binding.id} value={binding.id}>
                      {binding.name
                        ? `${binding.alias}（${binding.name}）`
                        : binding.alias}
                      {binding.enabled ? '' : '（已禁用）'}
                    </option>
                  ))}
                </select>
              </label>
              <label className="space-y-1 sm:col-span-2">
                <span className="text-xs text-muted-foreground">命令模板</span>
                <input
                  className="input w-full font-mono text-xs"
                  value={form.template}
                  disabled={saving}
                  placeholder="giveto {steamid} wood 1"
                  onChange={(e) =>
                    setForm((prev) => ({ ...prev, template: e.target.value }))
                  }
                />
              </label>
              <label className="space-y-1 sm:col-span-2">
                <span className="text-xs text-muted-foreground">允许执行的 QQ 号</span>
                <textarea
                  className="input min-h-24 w-full font-mono text-xs"
                  value={form.allowedQqText}
                  disabled={saving}
                  placeholder={'每行一个 QQ 号\n123456789'}
                  onChange={(e) =>
                    setForm((prev) => ({ ...prev, allowedQqText: e.target.value }))
                  }
                />
              </label>
            </div>
            <label className="flex items-center gap-2 text-sm">
              <ToggleSwitch
                checked={form.enabled}
                disabled={saving}
                onChange={(enabled) => setForm((prev) => ({ ...prev, enabled }))}
              />
              启用
            </label>
            <div className="flex flex-wrap gap-2">
              <button type="submit" className="btn-primary" disabled={saving}>
                {saving ? '保存中…' : '保存'}
              </button>
              <button
                type="button"
                className="btn-secondary"
                disabled={saving}
                onClick={resetForm}
              >
                取消
              </button>
            </div>
          </form>
        )}

        {!showForm && items.length === 0 && !error && bindings.length > 0 && (
          <p className="text-sm text-muted-foreground">尚未添加任何自定义指令。</p>
        )}

        {!showForm && items.length > 0 && (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[860px] text-left text-sm">
              <thead>
                <tr className="border-b border-border text-muted-foreground">
                  <th className="pb-3 pr-4 font-medium">指令名</th>
                  <th className="pb-3 pr-4 font-medium">命令模板</th>
                  <th className="pb-3 pr-4 font-medium">服务器</th>
                  <th className="pb-3 pr-4 font-medium">允许 QQ</th>
                  <th className="pb-3 pr-4 font-medium">启用</th>
                  <th className="pb-3 font-medium text-right">操作</th>
                </tr>
              </thead>
              <tbody>
                {items.map((item) => {
                  const toggling = togglingId === item.id
                  return (
                    <tr key={item.id} className="border-b border-border last:border-0">
                      <td className="py-3.5 pr-4 font-mono">{item.name}</td>
                      <td className="py-3.5 pr-4 font-mono text-xs text-muted-foreground">
                        {item.template}
                      </td>
                      <td className="py-3.5 pr-4">{bindingLabel(item.binding_id)}</td>
                      <td className="py-3.5 pr-4 font-mono text-xs text-muted-foreground whitespace-pre-line">
                        {item.allowed_qq_ids.length > 0
                          ? item.allowed_qq_ids.join('\n')
                          : '—'}
                      </td>
                      <td className="py-3.5 pr-4">
                        <ToggleSwitch
                          checked={item.enabled}
                          disabled={toggling}
                          onChange={() => void handleToggleEnabled(item)}
                        />
                      </td>
                      <td className="py-3.5 text-right">
                        <div className="flex justify-end gap-3">
                          <button
                            type="button"
                            className="text-xs text-primary hover:underline"
                            onClick={() => openEdit(item)}
                          >
                            编辑
                          </button>
                          <button
                            type="button"
                            className="text-xs text-destructive hover:underline"
                            onClick={() => setDeleteTarget(item)}
                          >
                            删除
                          </button>
                        </div>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>

      <ConfirmDialog
        open={deleteTarget !== null}
        title="删除自定义指令"
        message={
          deleteTarget
            ? `确定删除指令「${deleteTarget.name}」？此操作不可撤销。`
            : ''
        }
        confirmLabel="删除"
        loading={deleting}
        onConfirm={() => void handleDelete()}
        onCancel={() => setDeleteTarget(null)}
      />
    </div>
  )
}
