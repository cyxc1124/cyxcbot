import { ToggleSwitch } from './ToggleSwitch'
import type { LinkParserPolicyRow } from '../hooks/useLinkParserPolicies'

function PolicyToggleRow({
  checked,
  disabled,
  onChange,
}: {
  checked: boolean
  disabled: boolean
  onChange: (checked: boolean) => void
}) {
  return (
    <div className="inline-flex items-center gap-2">
      <span
        className={`text-xs ${checked ? 'text-emerald-600 dark:text-emerald-400' : 'text-muted-foreground'}`}
      >
        {checked ? '已启用' : '已关闭'}
      </span>
      <ToggleSwitch checked={checked} disabled={disabled} onChange={onChange} />
    </div>
  )
}

export function GlobalPolicyHint({ scope }: { scope: 'group' | 'user' }) {
  return (
    <div className="space-y-1">
      <p className="text-sm text-muted-foreground">
        在下方为每个{scope === 'group' ? '群' : '好友'}单独开启视频、直播或动态链接解析；均可关闭。开启「发送视频」时会额外下载并回传视频文件（需同时开启视频链接）。文案可在「消息模板」中配置。
      </p>
      {scope === 'group' && (
        <p className="text-sm text-muted-foreground">
          仅显示已启用「群消息」的群；关闭群消息的群不会响应任何消息，也无法配置链接解析。
        </p>
      )}
      {scope === 'user' && (
        <p className="text-sm text-muted-foreground">
          仅显示已启用「好友消息」的好友；关闭好友消息的用户不会响应任何指令，也无法配置链接解析。
        </p>
      )}
    </div>
  )
}

interface LinkParserPolicyTableProps<T extends LinkParserPolicyRow> {
  items: T[]
  getItemId: (item: T) => string
  getDisplayName: (item: T) => string | null | undefined
  idColumnLabel: string
  nameColumnLabel: string
  savingIds: Set<string>
  togglingAll: boolean
  editable?: boolean
  onPatch: (
    id: string,
    patch: Partial<
      Pick<T, 'video_enabled' | 'live_enabled' | 'dynamic_enabled' | 'send_video_enabled'>
    >,
  ) => void
  onReset: (id: string) => void
}

export function LinkParserPolicyTable<T extends LinkParserPolicyRow>({
  items,
  getItemId,
  getDisplayName,
  idColumnLabel,
  nameColumnLabel,
  savingIds,
  togglingAll,
  editable = true,
  onPatch,
  onReset,
}: LinkParserPolicyTableProps<T>) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[780px] text-left text-sm">
        <thead>
          <tr className="border-b border-border text-muted-foreground border-border">
            <th className="pb-3 pr-4 font-medium">{nameColumnLabel}</th>
            <th className="pb-3 pr-4 font-medium">{idColumnLabel}</th>
            <th className="pb-3 pr-4 font-medium">视频链接</th>
            <th className="pb-3 pr-4 font-medium">发送视频</th>
            <th className="pb-3 pr-4 font-medium">直播链接</th>
            <th className="pb-3 pr-4 font-medium">动态链接</th>
            <th className="pb-3 font-medium text-right">操作</th>
          </tr>
        </thead>
        <tbody>
          {items.map((item) => {
            const itemId = getItemId(item)
            const saving = savingIds.has(itemId) || togglingAll
            const disabled = saving || !editable
            return (
              <tr key={itemId} className="border-b border-border last:border-0 border-border">
                <td className="py-3.5 pr-4 font-medium text-foreground">
                  {getDisplayName(item) ?? '—'}
                  {saving && (
                    <span className="ml-2 text-[10px] text-muted-foreground">保存中…</span>
                  )}
                </td>
                <td className="py-3.5 pr-4 font-mono text-xs text-muted-foreground">{itemId}</td>
                <td className="py-3.5 pr-4">
                  <PolicyToggleRow
                    checked={item.video_enabled}
                    disabled={disabled}
                    onChange={(checked) =>
                      void onPatch(
                        itemId,
                        checked
                          ? { video_enabled: true }
                          : { video_enabled: false, send_video_enabled: false },
                      )
                    }
                  />
                </td>
                <td className="py-3.5 pr-4">
                  <PolicyToggleRow
                    checked={item.send_video_enabled}
                    disabled={disabled}
                    onChange={(checked) =>
                      void onPatch(
                        itemId,
                        checked
                          ? { send_video_enabled: true, video_enabled: true }
                          : { send_video_enabled: false },
                      )
                    }
                  />
                </td>
                <td className="py-3.5 pr-4">
                  <PolicyToggleRow
                    checked={item.live_enabled}
                    disabled={disabled}
                    onChange={(checked) => void onPatch(itemId, { live_enabled: checked })}
                  />
                </td>
                <td className="py-3.5 pr-4">
                  <PolicyToggleRow
                    checked={item.dynamic_enabled}
                    disabled={disabled}
                    onChange={(checked) =>
                      void onPatch(itemId, { dynamic_enabled: checked })
                    }
                  />
                </td>
                <td className="py-3.5 text-right">
                  {item.customized && (
                    <button
                      type="button"
                      className="btn-secondary text-xs"
                      disabled={disabled}
                      onClick={() => void onReset(itemId)}
                    >
                      恢复默认
                    </button>
                  )}
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}
