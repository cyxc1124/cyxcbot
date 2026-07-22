import { ToggleSwitch } from './ToggleSwitch'
import type { RustRconPolicyRow } from '../hooks/useRustRconPolicies'

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

export function RustRconPolicyHint({ scope }: { scope: 'group' | 'user' }) {
  return (
    <div className="space-y-1">
      <p className="text-sm text-muted-foreground">
        在下方为每个{scope === 'group' ? '群' : '好友'}单独开启 Rust 远控命令；默认关闭。
        服务器连接与触发词在「Rust 远控 → 服务器绑定」中配置。
      </p>
      {scope === 'group' && (
        <p className="text-sm text-muted-foreground">
          仅显示已启用「群消息」的群；关闭群消息的群不会响应任何消息，也无法配置远控。
        </p>
      )}
      {scope === 'user' && (
        <p className="text-sm text-muted-foreground">
          仅显示已启用「好友消息」的好友；关闭好友消息的用户不会响应任何指令，也无法配置远控。
        </p>
      )}
    </div>
  )
}

interface RustRconPolicyTableProps<T extends RustRconPolicyRow> {
  items: T[]
  getItemId: (item: T) => string
  getDisplayName: (item: T) => string | null | undefined
  idColumnLabel: string
  nameColumnLabel: string
  savingIds: Set<string>
  togglingAll: boolean
  editable?: boolean
  onPatch: (id: string, enabled: boolean) => void
  onReset: (id: string) => void
}

export function RustRconPolicyTable<T extends RustRconPolicyRow>({
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
}: RustRconPolicyTableProps<T>) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[560px] text-left text-sm">
        <thead>
          <tr className="border-b border-border text-muted-foreground">
            <th className="pb-3 pr-4 font-medium">{nameColumnLabel}</th>
            <th className="pb-3 pr-4 font-medium">{idColumnLabel}</th>
            <th className="pb-3 pr-4 font-medium">Rust 远控</th>
            <th className="pb-3 font-medium text-right">操作</th>
          </tr>
        </thead>
        <tbody>
          {items.map((item) => {
            const itemId = getItemId(item)
            const saving = savingIds.has(itemId) || togglingAll
            const disabled = saving || !editable
            return (
              <tr key={itemId} className="border-b border-border last:border-0">
                <td className="py-3.5 pr-4 font-medium text-foreground">
                  {getDisplayName(item) ?? '—'}
                  {saving && (
                    <span className="ml-2 text-[10px] text-muted-foreground">保存中…</span>
                  )}
                </td>
                <td className="py-3.5 pr-4 font-mono text-xs text-muted-foreground">{itemId}</td>
                <td className="py-3.5 pr-4">
                  <PolicyToggleRow
                    checked={item.enabled}
                    disabled={disabled}
                    onChange={(checked) => onPatch(itemId, checked)}
                  />
                </td>
                <td className="py-3.5 text-right">
                  <button
                    type="button"
                    className="text-xs text-primary hover:underline disabled:opacity-50"
                    disabled={disabled || !item.customized}
                    onClick={() => onReset(itemId)}
                  >
                    恢复默认
                  </button>
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}
