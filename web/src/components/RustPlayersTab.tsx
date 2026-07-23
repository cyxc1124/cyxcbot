import { ConfirmDialog } from './ConfirmDialog'
import { LoadErrorBanner } from './LoadErrorBanner'
import { PageLoading } from './LoadingSpinner'
import { useRustPlayers } from '../hooks/useRustPlayers'
import { useState } from 'react'

export function RustPlayersTab() {
  const {
    items,
    checkInConfig,
    rconBindings,
    loading,
    error,
    retryLoad,
    configForm,
    setConfigForm,
    savingConfig,
    savingRowKeys,
    unbindingUserIds,
    draftPoints,
    setDraftPoints,
    rowKey,
    handleSaveConfig,
    handleSavePoints,
    handleUnbind,
  } = useRustPlayers()

  const [unbindTarget, setUnbindTarget] = useState<{ userId: string; steamId: string } | null>(
    null,
  )

  if (loading && items.length === 0 && !error) {
    return <PageLoading />
  }

  return (
    <div className="space-y-6">
      <div className="card space-y-4">
        <div>
          <h3 className="font-semibold text-foreground">签到积分范围</h3>
          <p className="mt-1 text-sm text-muted-foreground">
            群成员发送 <code className="font-mono text-xs">@机器人 签到</code>{' '}
            时随机获得基础积分（每日一次）；已绑定 SteamID 且在游戏内在线时可领取在线加成，离线签到后上线可再次签到补领。
            签到、绑定、查积分、商城等 Rust 群管指令均需本群开启 Rust RCON，未开启时会被静默忽略。
          </p>
        </div>

        <div className="flex flex-wrap items-end gap-4">
          <label className="space-y-1">
            <span className="text-xs text-muted-foreground">最小积分</span>
            <input
              type="number"
              min={0}
              max={1000000}
              className="input w-28"
              value={configForm.min_points}
              disabled={savingConfig}
              onChange={(e) =>
                setConfigForm((prev) => ({ ...prev, min_points: e.target.value }))
              }
            />
          </label>
          <label className="space-y-1">
            <span className="text-xs text-muted-foreground">最大积分</span>
            <input
              type="number"
              min={0}
              max={1000000}
              className="input w-28"
              value={configForm.max_points}
              disabled={savingConfig}
              onChange={(e) =>
                setConfigForm((prev) => ({ ...prev, max_points: e.target.value }))
              }
            />
          </label>
          <label className="space-y-1">
            <span className="text-xs text-muted-foreground">在线加成积分</span>
            <input
              type="number"
              min={0}
              max={1000000}
              className="input w-28"
              value={configForm.online_bonus_points}
              disabled={savingConfig}
              onChange={(e) =>
                setConfigForm((prev) => ({
                  ...prev,
                  online_bonus_points: e.target.value,
                }))
              }
            />
          </label>
          <label className="space-y-1">
            <span className="text-xs text-muted-foreground">RCON 服务器</span>
            <select
              className="input min-w-40"
              value={configForm.rcon_binding_id}
              disabled={savingConfig}
              onChange={(e) =>
                setConfigForm((prev) => ({ ...prev, rcon_binding_id: e.target.value }))
              }
            >
              <option value="0">首个启用的绑定</option>
              {rconBindings
                .filter((binding) => binding.enabled)
                .map((binding) => (
                  <option key={binding.id} value={String(binding.id)}>
                    {binding.name || binding.alias} ({binding.host}:{binding.port})
                  </option>
                ))}
            </select>
          </label>
          <button
            type="button"
            className="btn-primary"
            disabled={savingConfig}
            onClick={() => void handleSaveConfig()}
          >
            {savingConfig ? '保存中…' : '保存配置'}
          </button>
          {checkInConfig && (
            <span className="text-xs text-muted-foreground">
              当前生效：基础 {checkInConfig.min_points}–{checkInConfig.max_points}，
              在线加成 {checkInConfig.online_bonus_points}
            </span>
          )}
        </div>
      </div>

      <div className="card space-y-4">
        <div>
          <h3 className="font-semibold text-foreground">积分与 SteamID 绑定</h3>
          <p className="mt-1 text-sm text-muted-foreground">
            用户通过 <code className="font-mono text-xs">@机器人 绑定 SteamID64</code>{' '}
            绑定账号（不可自助换绑）；查询积分：
            <code className="font-mono text-xs">@机器人 我的积分</code> 或{' '}
            <code className="font-mono text-xs">@机器人 积分</code>。
            触发词在「群管命令」Tab 中配置。
          </p>
        </div>

        {error && <LoadErrorBanner message={error} onRetry={retryLoad} />}

        {!error && items.length === 0 && (
          <p className="text-sm text-muted-foreground">尚无签到或绑定记录。</p>
        )}

        {items.length > 0 && (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[720px] text-left text-sm">
              <thead>
                <tr className="border-b border-border text-muted-foreground">
                  <th className="pb-3 pr-4 font-medium">群号</th>
                  <th className="pb-3 pr-4 font-medium">QQ 号</th>
                  <th className="pb-3 pr-4 font-medium">积分</th>
                  <th className="pb-3 pr-4 font-medium">SteamID</th>
                  <th className="pb-3 font-medium text-right">操作</th>
                </tr>
              </thead>
              <tbody>
                {items.map((item) => {
                  const key = rowKey(item)
                  const saving = savingRowKeys.has(key)
                  const unbinding = unbindingUserIds.has(item.user_id)
                  return (
                    <tr key={key} className="border-b border-border last:border-0">
                      <td className="py-3.5 pr-4 font-mono text-xs text-muted-foreground">
                        {item.group_id ?? '—'}
                      </td>
                      <td className="py-3.5 pr-4 font-mono text-xs text-muted-foreground">
                        {item.user_id}
                      </td>
                      <td className="py-3.5 pr-4">
                        <div className="flex items-center gap-2">
                          <input
                            type="number"
                            min={0}
                            max={1000000}
                            className="input w-24 text-xs"
                            disabled={saving || !item.group_id}
                            value={draftPoints[key] ?? String(item.points)}
                            onChange={(e) =>
                              setDraftPoints((prev) => ({ ...prev, [key]: e.target.value }))
                            }
                          />
                          <button
                            type="button"
                            className="text-xs text-primary hover:underline disabled:opacity-50"
                            disabled={saving || !item.group_id}
                            onClick={() => void handleSavePoints(item)}
                          >
                            {saving ? '保存中…' : '保存'}
                          </button>
                        </div>
                      </td>
                      <td className="py-3.5 pr-4 font-mono text-xs text-muted-foreground">
                        {item.steam_id ?? '—'}
                      </td>
                      <td className="py-3.5 text-right">
                        {item.steam_id ? (
                          <button
                            type="button"
                            className="text-xs text-destructive hover:underline disabled:opacity-50"
                            disabled={unbinding}
                            onClick={() =>
                              setUnbindTarget({
                                userId: item.user_id,
                                steamId: item.steam_id!,
                              })
                            }
                          >
                            {unbinding ? '解除中…' : '解除绑定'}
                          </button>
                        ) : (
                          <span className="text-xs text-muted-foreground">—</span>
                        )}
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
        open={unbindTarget !== null}
        title="解除 SteamID 绑定"
        message={
          unbindTarget
            ? `确定解除 QQ ${unbindTarget.userId} 与 SteamID ${unbindTarget.steamId} 的绑定？用户需重新发送绑定指令才能再次绑定。`
            : ''
        }
        confirmLabel="解除绑定"
        loading={unbindTarget !== null && unbindingUserIds.has(unbindTarget.userId)}
        onConfirm={() => {
          if (!unbindTarget) return
          void handleUnbind(unbindTarget.userId).then(() => setUnbindTarget(null))
        }}
        onCancel={() => setUnbindTarget(null)}
      />
    </div>
  )
}
