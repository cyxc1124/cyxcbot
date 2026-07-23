import { ConfirmDialog } from './ConfirmDialog'
import { LoadErrorBanner } from './LoadErrorBanner'
import { PageLoading } from './LoadingSpinner'
import { ToggleSwitch } from './ToggleSwitch'
import { useRustShopItems } from '../hooks/useRustShopItems'

export function RustShopItemsTab() {
  const {
    items,
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
  } = useRustShopItems()

  if (loading && items.length === 0 && !error) {
    return <PageLoading />
  }

  return (
    <div className="space-y-6">
      <div className="card space-y-4">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h3 className="font-semibold text-foreground">积分商城商品</h3>
            <p className="mt-1 text-sm text-muted-foreground">
              配置可用积分兑换的游戏内物品。群成员发送{' '}
              <code className="font-mono text-xs">@机器人 商品列表</code>{' '}
              查看商品，发送{' '}
              <code className="font-mono text-xs">@机器人 兑换商品 物品ID</code>{' '}
              或{' '}
              <code className="font-mono text-xs">@机器人 兑换商品 商品中文名 数量</code>{' '}
              兑换。兑换成功后将通过 RCON 执行{' '}
              <code className="font-mono text-xs">give SteamID 物品ID 数量</code>
              （需该群已在「群权限」中开启 Rust RCON；未开启时指令会被静默忽略）。
            </p>
          </div>
          {!showForm && (
            <button type="button" className="btn-primary shrink-0" onClick={openCreate}>
              添加商品
            </button>
          )}
        </div>

        {error && <LoadErrorBanner message={error} onRetry={retryLoad} />}

        {showForm && (
          <form onSubmit={handleSubmit} className="space-y-4 rounded-lg border border-border p-4">
            <h4 className="font-medium text-foreground">
              {editingId === null ? '添加商品' : '编辑商品'}
            </h4>
            <div className="grid gap-4 sm:grid-cols-2">
              <label className="space-y-1">
                <span className="text-xs text-muted-foreground">商品中文名</span>
                <input
                  className="input w-full"
                  value={form.name}
                  disabled={saving}
                  onChange={(e) => setForm((prev) => ({ ...prev, name: e.target.value }))}
                />
              </label>
              <label className="space-y-1">
                <span className="text-xs text-muted-foreground">物品 ID</span>
                <input
                  className="input w-full font-mono text-xs"
                  value={form.item_id}
                  disabled={saving}
                  onChange={(e) => setForm((prev) => ({ ...prev, item_id: e.target.value }))}
                />
              </label>
              <label className="space-y-1">
                <span className="text-xs text-muted-foreground">所需积分</span>
                <input
                  type="number"
                  min={1}
                  max={1000000}
                  className="input w-full"
                  value={form.points_cost}
                  disabled={saving}
                  onChange={(e) =>
                    setForm((prev) => ({ ...prev, points_cost: e.target.value }))
                  }
                />
              </label>
              <label className="space-y-1">
                <span className="text-xs text-muted-foreground">排序（越小越靠前）</span>
                <input
                  type="number"
                  className="input w-full"
                  value={form.sort_order}
                  disabled={saving}
                  onChange={(e) =>
                    setForm((prev) => ({ ...prev, sort_order: e.target.value }))
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
              <button type="button" className="btn-secondary" disabled={saving} onClick={resetForm}>
                取消
              </button>
            </div>
          </form>
        )}

        {!showForm && items.length === 0 && !error && (
          <p className="text-sm text-muted-foreground">尚未添加任何商品。</p>
        )}

        {!showForm && items.length > 0 && (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[720px] text-left text-sm">
              <thead>
                <tr className="border-b border-border text-muted-foreground">
                  <th className="pb-3 pr-4 font-medium">商品中文名</th>
                  <th className="pb-3 pr-4 font-medium">物品 ID</th>
                  <th className="pb-3 pr-4 font-medium">所需积分</th>
                  <th className="pb-3 pr-4 font-medium">排序</th>
                  <th className="pb-3 pr-4 font-medium">启用</th>
                  <th className="pb-3 font-medium text-right">操作</th>
                </tr>
              </thead>
              <tbody>
                {items.map((item) => {
                  const toggling = togglingId === item.id
                  return (
                    <tr key={item.id} className="border-b border-border last:border-0">
                      <td className="py-3.5 pr-4">{item.name}</td>
                      <td className="py-3.5 pr-4 font-mono text-xs text-muted-foreground">
                        {item.item_id}
                      </td>
                      <td className="py-3.5 pr-4">{item.points_cost}</td>
                      <td className="py-3.5 pr-4 text-muted-foreground">{item.sort_order}</td>
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
        title="删除商品"
        message={
          deleteTarget
            ? `确定删除商品「${deleteTarget.name}」（${deleteTarget.item_id}）？此操作不可撤销。`
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
