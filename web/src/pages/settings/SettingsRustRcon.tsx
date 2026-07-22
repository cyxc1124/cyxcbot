import { ConfirmDialog } from '../../components/ConfirmDialog'
import { LoadErrorBanner } from '../../components/LoadErrorBanner'
import { PageLoading } from '../../components/LoadingSpinner'
import { ToggleSwitch } from '../../components/ToggleSwitch'
import { useRustRconBindings } from '../../hooks/useRustRconBindings'

export function SettingsRustRconPage() {
  const {
    bindings,
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
  } = useRustRconBindings()

  if (loading && bindings.length === 0 && !error) {
    return <PageLoading />
  }

  return (
    <div className="space-y-6">
      <div className="card space-y-4">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h3 className="font-semibold text-foreground">Rust RCON</h3>
            <p className="mt-1 text-sm text-muted-foreground">
              配置 Rust 服务器 RCON 连接，并为每个服务器定义群内触发词。在群内发送{' '}
              <code className="font-mono text-xs">@机器人 触发词 命令</code>{' '}
              即可向对应服务器发送 RCON 指令（插件逻辑后续接入）。
            </p>
            <p className="mt-2 text-xs text-muted-foreground">
              示例：<code className="font-mono">@机器人 rcon1 status</code>、
              <code className="font-mono">@机器人 rcon2 say 大家好</code>
            </p>
          </div>
          {!showForm && (
            <button type="button" className="btn-primary shrink-0" onClick={openCreate}>
              添加绑定
            </button>
          )}
        </div>

        {error && <LoadErrorBanner message={error} onRetry={retryLoad} />}

        {!showForm && bindings.length === 0 && !error && (
          <p className="text-sm text-muted-foreground">尚未配置任何 RCON 绑定。</p>
        )}

        {!showForm && bindings.length > 0 && (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[720px] text-left text-sm">
              <thead>
                <tr className="border-b border-border text-muted-foreground">
                  <th className="pb-3 pr-4 font-medium">触发词</th>
                  <th className="pb-3 pr-4 font-medium">名称</th>
                  <th className="pb-3 pr-4 font-medium">地址</th>
                  <th className="pb-3 pr-4 font-medium">端口</th>
                  <th className="pb-3 pr-4 font-medium">密码</th>
                  <th className="pb-3 pr-4 font-medium">允许 QQ</th>
                  <th className="pb-3 pr-4 font-medium">启用</th>
                  <th className="pb-3 font-medium text-right">操作</th>
                </tr>
              </thead>
              <tbody>
                {bindings.map((binding) => {
                  const toggling = togglingId === binding.id
                  return (
                    <tr
                      key={binding.id}
                      className="border-b border-border last:border-0"
                    >
                      <td className="py-3.5 pr-4 font-mono text-foreground">
                        {binding.alias}
                      </td>
                      <td className="py-3.5 pr-4 text-foreground">
                        {binding.name ?? '—'}
                      </td>
                      <td className="py-3.5 pr-4 font-mono text-xs text-muted-foreground">
                        {binding.host}
                      </td>
                      <td className="py-3.5 pr-4 font-mono text-xs text-muted-foreground">
                        {binding.port}
                      </td>
                      <td className="py-3.5 pr-4 text-xs text-muted-foreground">
                        {binding.password.configured
                          ? binding.password.preview ?? '已配置'
                          : '未配置'}
                      </td>
                      <td className="py-3.5 pr-4 font-mono text-xs text-muted-foreground">
                        {binding.allowed_qq_ids.length > 0
                          ? binding.allowed_qq_ids.join(', ')
                          : '—'}
                      </td>
                      <td className="py-3.5 pr-4">
                        <div className="inline-flex items-center gap-2">
                          <span
                            className={`text-xs ${
                              binding.enabled
                                ? 'text-emerald-600 dark:text-emerald-400'
                                : 'text-muted-foreground'
                            }`}
                          >
                            {binding.enabled ? '已启用' : '已关闭'}
                          </span>
                          <ToggleSwitch
                            checked={binding.enabled}
                            disabled={toggling}
                            onChange={() => void handleToggleEnabled(binding)}
                          />
                        </div>
                      </td>
                      <td className="py-3.5 text-right">
                        <div className="inline-flex gap-2">
                          <button
                            type="button"
                            className="btn-secondary text-xs"
                            onClick={() => openEdit(binding)}
                          >
                            编辑
                          </button>
                          <button
                            type="button"
                            className="btn-danger text-xs"
                            onClick={() => setDeleteTarget(binding)}
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

      {showForm && (
        <form className="card space-y-4" onSubmit={(e) => void handleSubmit(e)}>
          <div className="flex items-center justify-between gap-3">
            <h3 className="font-semibold text-foreground">
              {editingId ? '编辑 RCON 绑定' : '添加 RCON 绑定'}
            </h3>
            <button type="button" className="btn-secondary text-sm" onClick={resetForm}>
              取消
            </button>
          </div>

          <div className="grid gap-4 sm:grid-cols-2">
            <div>
              <label className="label" htmlFor="rcon-alias">
                触发词
              </label>
              <input
                id="rcon-alias"
                className="input mt-1 font-mono"
                placeholder="例如 rcon1"
                value={form.alias}
                disabled={saving}
                onChange={(e) => setForm((prev) => ({ ...prev, alias: e.target.value }))}
              />
              <p className="mt-1 text-xs text-muted-foreground">
                群内使用 <code className="font-mono">@机器人 {form.alias || '触发词'} 命令</code>
              </p>
            </div>

            <div>
              <label className="label" htmlFor="rcon-name">
                显示名称（可选）
              </label>
              <input
                id="rcon-name"
                className="input mt-1"
                placeholder="例如 主服 / 测试服"
                value={form.name}
                disabled={saving}
                onChange={(e) => setForm((prev) => ({ ...prev, name: e.target.value }))}
              />
            </div>

            <div>
              <label className="label" htmlFor="rcon-host">
                服务器地址
              </label>
              <input
                id="rcon-host"
                className="input mt-1 font-mono"
                placeholder="例如 192.168.1.10"
                value={form.host}
                disabled={saving}
                onChange={(e) => setForm((prev) => ({ ...prev, host: e.target.value }))}
              />
            </div>

            <div>
              <label className="label" htmlFor="rcon-port">
                端口
              </label>
              <input
                id="rcon-port"
                type="number"
                min={1}
                max={65535}
                className="input mt-1 font-mono"
                value={form.port}
                disabled={saving}
                onChange={(e) => setForm((prev) => ({ ...prev, port: e.target.value }))}
              />
            </div>

            <div className="sm:col-span-2">
              <label className="label" htmlFor="rcon-allowed-qq">
                允许执行的 QQ 号
              </label>
              <textarea
                id="rcon-allowed-qq"
                className="input mt-1 min-h-24 font-mono text-sm"
                placeholder="每行一个 QQ 号"
                value={form.allowedQqText}
                disabled={saving}
                onChange={(e) =>
                  setForm((prev) => ({ ...prev, allowedQqText: e.target.value }))
                }
              />
              <p className="mt-1 text-xs text-muted-foreground">
                仅列表中的 QQ 号可触发此绑定的 RCON 命令；也支持逗号、分号分隔。
              </p>
            </div>

            <div className="sm:col-span-2">
              <label className="label" htmlFor="rcon-password">
                RCON 密码
              </label>
              <input
                id="rcon-password"
                type="password"
                className="input mt-1 font-mono"
                placeholder={editingId ? '留空表示不修改' : '必填'}
                value={form.password}
                disabled={saving}
                autoComplete="new-password"
                onChange={(e) => setForm((prev) => ({ ...prev, password: e.target.value }))}
              />
            </div>
          </div>

          <div className="flex items-center gap-3">
            <ToggleSwitch
              checked={form.enabled}
              disabled={saving}
              onChange={(enabled) => setForm((prev) => ({ ...prev, enabled }))}
            />
            <span className="text-sm text-foreground">
              {form.enabled ? '启用此绑定' : '关闭此绑定（保留配置）'}
            </span>
          </div>

          <button type="submit" className="btn-primary" disabled={saving}>
            {saving ? '保存中…' : editingId ? '保存更改' : '创建绑定'}
          </button>
        </form>
      )}

      <ConfirmDialog
        open={deleteTarget !== null}
        title="删除 RCON 绑定"
        message={
          deleteTarget ? (
            <>
              确定删除触发词「<span className="font-mono">{deleteTarget.alias}</span>
              」的 RCON 绑定？此操作不可撤销。
            </>
          ) : (
            ''
          )
        }
        confirmLabel="删除"
        loading={deleting}
        onCancel={() => {
          if (!deleting) setDeleteTarget(null)
        }}
        onConfirm={() => void handleDelete()}
      />
    </div>
  )
}
