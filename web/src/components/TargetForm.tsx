import type { FormEvent } from 'react'
import type { Friend, Group } from '../api/types'
import { FriendSelector } from './FriendSelector'
import { GroupSelector } from './GroupSelector'
import { ToggleSwitch } from './ToggleSwitch'
import type { TargetFormState } from './targetMapping/types'

interface TargetFormProps {
  editingId: number | null
  form: TargetFormState
  setForm: React.Dispatch<React.SetStateAction<TargetFormState>>
  editOriginalId: string
  idLabel: string
  isDynamic: boolean
  groups: Group[]
  friends: Friend[]
  saving: boolean
  onSubmit: (e: FormEvent) => void
  onCancel: () => void
}

export function TargetForm({
  editingId,
  form,
  setForm,
  editOriginalId,
  idLabel,
  isDynamic,
  groups,
  friends,
  saving,
  onSubmit,
  onCancel,
}: TargetFormProps) {
  return (
    <div className="space-y-4">
      <h3 className="text-lg font-semibold text-foreground">
        {editingId ? '编辑订阅' : '新建订阅'}
      </h3>
      <form onSubmit={onSubmit} className="space-y-4">
        <div className="grid gap-4 sm:grid-cols-2">
          <div>
            <label className="label">{idLabel}</label>
            <input
              className="input"
              value={form.id}
              onChange={(e) => {
                const id = e.target.value
                setForm((f) => ({
                  ...f,
                  id,
                  name: editingId && id.trim() !== editOriginalId ? '' : f.name,
                }))
              }}
              required
              placeholder="12345678"
            />
          </div>
          <div>
            <label className="label">显示名称（可选）</label>
            <input
              className="input"
              value={form.name}
              onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
              placeholder="留空将自动从 B 站获取"
            />
            {!editingId ? (
              <p className="mt-1 text-xs text-muted-foreground">
                {isDynamic
                  ? 'UID 无效且未填写名称时无法保存'
                  : '房间号无效且未填写名称时无法保存'}
              </p>
            ) : (
              <p className="mt-1 text-xs text-muted-foreground">
                修改 {idLabel} 后将清空名称并重新从 B 站获取
              </p>
            )}
          </div>
        </div>

        <div>
          <label className="label">订阅群组</label>
          <GroupSelector
            groups={groups}
            selected={form.group_ids}
            onChange={(ids) => setForm((f) => ({ ...f, group_ids: ids }))}
            disabled={saving}
          />
        </div>

        <div>
          <label className="label">推送好友</label>
          <FriendSelector
            friends={friends}
            selected={form.user_ids}
            onChange={(ids) => setForm((f) => ({ ...f, user_ids: ids }))}
            disabled={saving}
          />
        </div>

        <div className="flex flex-wrap items-center gap-6">
          <div className="inline-flex items-center gap-2">
            <span className="text-sm text-muted-foreground">启用订阅</span>
            <ToggleSwitch
              checked={form.enabled}
              disabled={saving}
              onChange={(checked) => setForm((f) => ({ ...f, enabled: checked }))}
            />
          </div>
          <div className="inline-flex items-center gap-2">
            <span className="text-sm text-muted-foreground">@全体成员</span>
            <ToggleSwitch
              checked={form.at_all}
              disabled={saving}
              onChange={(checked) => setForm((f) => ({ ...f, at_all: checked }))}
            />
          </div>
        </div>
        <p className="text-xs text-muted-foreground">
          @全体成员仅对群组生效；好友推送不支持 @全体，需机器人为群管理员时群组 @ 才生效
        </p>

        <div className="flex gap-2">
          <button type="submit" className="btn-primary" disabled={saving}>
            {saving ? '保存中…' : '保存'}
          </button>
          <button type="button" className="btn-secondary" onClick={onCancel}>
            取消
          </button>
        </div>
      </form>
    </div>
  )
}
