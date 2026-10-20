import { Link } from 'react-router-dom'
import type { MonitorPollSchedule } from '../api/types'
import { useTargetMappings } from '../hooks/useTargetMappings'
import { LoadErrorBanner } from './LoadErrorBanner'
import { TargetDetail } from './TargetDetail'
import { TargetForm } from './TargetForm'
import { MonitorPollScheduleCard } from './MonitorPollScheduleCard'
import {
  getTargetDisplayName,
  getTargetId,
  type TargetType,
} from './targetMapping/types'

interface TargetMappingSectionProps {
  type: TargetType
  title: string
  description: string
  pollSchedule: MonitorPollSchedule | null
  checking: boolean
  onCheck: () => void
  onTargetsChanged?: () => void | Promise<void>
}

export function TargetMappingSection({ type, title, description, pollSchedule, checking, onCheck, onTargetsChanged }: TargetMappingSectionProps) {
  const {
    groups,
    friends,
    targets,
    loading,
    error,
    retryLoad,
    selectedId,
    selectedTarget,
    showForm,
    editingId,
    form,
    setForm,
    editOriginalId,
    saving,
    togglingId,
    refreshingId,
    idLabel,
    targetLabel,
    nameSource,
    openCreate,
    openEdit,
    selectTarget,
    clearSelection,
    resetForm,
    handleSubmit,
    handleDelete,
    toggleEnabled,
    toggleAtAll,
    refreshProfile,
  } = useTargetMappings({ type, onTargetsChanged })

  const showSplit = selectedId !== null || showForm
  const listHiddenOnMobile = showSplit
  const subscriptionStatus = (
    <div className="flex flex-wrap items-start gap-x-3 gap-y-2 text-xs">
      <details className="min-w-0 text-muted-foreground">
        <summary className="cursor-pointer">
          {pollSchedule
            ? `${pollSchedule.target_count} 个目标 · ${pollSchedule.strategy === 'websocket_primary' ? 'WebSocket 实时检测' : `每 ${Math.round(pollSchedule.per_target_cycle_seconds)} 秒检查`}`
            : '监控状态与检查'}
        </summary>
        <div className="mt-3 space-y-3">
          {pollSchedule && <MonitorPollScheduleCard title="当前 API 请求频率" schedule={pollSchedule} />}
          <button type="button" className="btn-secondary text-xs" disabled={checking} onClick={onCheck}>
            {checking ? '检查中…' : '立即检查'}
          </button>
        </div>
      </details>
      <Link to={type === 'x' ? '/x/settings' : '/bilibili/settings'} className="shrink-0 rounded-md bg-sidebar-accent px-2 py-0.5 font-medium text-primary hover:underline">
        查看订阅参数
      </Link>
    </div>
  )

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h2 className="text-2xl font-bold text-foreground">{title}</h2>
          <p className="mt-1 text-sm text-muted-foreground">{description}</p>
        </div>
        <button type="button" className="btn-primary" onClick={openCreate}>
          添加订阅
        </button>
      </div>

      {error && <LoadErrorBanner message={error} onRetry={retryLoad} />}

      {loading && targets.length === 0 && !error ? (
        <p className="card py-12 text-center text-sm text-muted-foreground">加载中…</p>
      ) : !loading && error && targets.length === 0 ? (
        <p className="card py-12 text-center text-sm text-muted-foreground">数据暂时无法加载</p>
      ) : !loading && targets.length === 0 && !showForm ? (
        <p className="card py-12 text-center text-sm text-muted-foreground">暂无订阅，点击上方按钮添加</p>
      ) : (
        <div
          className={`flex min-h-112 overflow-hidden rounded-2xl border border-border bg-card lg:min-h-[calc(100dvh-14rem)] ${
            showSplit ? 'lg:divide-x lg:divide-border' : ''
          }`}
        >
          <aside
            className={`shrink-0 bg-card ${
              listHiddenOnMobile ? 'hidden lg:block' : ''
            } ${showSplit ? 'w-full lg:w-64 xl:w-72' : 'w-full'}`}
          >
            <div className="flex h-full max-h-128 flex-col lg:max-h-[calc(100dvh-14rem)]">
              <div className="border-b border-border px-3 py-2.5 border-border">
                <p className="text-xs font-medium text-muted-foreground">
                  {targetLabel}列表
                  <span className="ml-1">({targets.length})</span>
                </p>
              </div>
              <ul className="flex-1 overflow-y-auto p-2">
                {targets.map((target) => {
                  const targetId = getTargetId(target, type)
                  const displayName = getTargetDisplayName(target, type, targetLabel)
                  const isSelected = selectedId === target.id
                  return (
                    <li key={target.id}>
                      <button
                        type="button"
                        onClick={() => selectTarget(target)}
                        className={`mb-1 w-full rounded-lg px-3 py-2.5 text-left transition-colors ${
                          isSelected
                            ? 'bg-sidebar-accent text-sidebar-primary'
                            : 'hover:bg-accent'
                        }`}
                      >
                        <div className="flex items-start justify-between gap-2">
                          <div className="min-w-0 flex-1">
                            <p className="truncate text-sm font-medium">{displayName}</p>
                            <p className="mt-0.5 font-mono text-xs text-muted-foreground">{targetId}</p>
                          </div>
                          <span
                            className={`mt-1 h-2 w-2 shrink-0 rounded-full ${
                              target.enabled ? 'bg-emerald-500' : 'bg-input'
                            }`}
                            title={target.enabled ? '已启用' : '已禁用'}
                          />
                        </div>
                        <p className="mt-1 text-xs text-muted-foreground">
                          {target.group_ids.length} 个群 · {target.user_ids.length} 个好友
                        </p>
                      </button>
                    </li>
                  )
                })}
              </ul>
            </div>
          </aside>

          {(showSplit || showForm) && (
            <main
              className={`min-w-0 flex-1 bg-card p-4 sm:p-5 ${
                showForm || selectedTarget ? 'block' : 'hidden lg:block'
              }`}
            >
              {showForm ? (
                <TargetForm
                  editingId={editingId}
                  form={form}
                  setForm={setForm}
                  editOriginalId={editOriginalId}
                  idLabel={idLabel}
                  type={type}
                  nameSource={nameSource}
                  groups={groups}
                  friends={friends}
                  saving={saving}
                  onSubmit={(e) => void handleSubmit(e)}
                  onCancel={resetForm}
                />
              ) : selectedTarget ? (
                <TargetDetail
                  target={selectedTarget}
                  type={type}
                  targetLabel={targetLabel}
                  groups={groups}
                  friends={friends}
                  rowBusy={togglingId === selectedTarget.id}
                  refreshing={refreshingId === selectedTarget.id}
                  subscriptionStatus={subscriptionStatus}
                  onClearSelection={clearSelection}
                  onToggleEnabled={toggleEnabled}
                  onToggleAtAll={toggleAtAll}
                  onEdit={openEdit}
                  onDelete={handleDelete}
                  onRefreshProfile={type === 'x' ? refreshProfile : undefined}
                />
              ) : (
                <div className="flex h-full min-h-80 items-center justify-center text-sm text-muted-foreground">
                  请从左侧选择一个{targetLabel}
                </div>
              )}
            </main>
          )}
        </div>
      )}
      {(!selectedTarget || showForm) && subscriptionStatus}
    </div>
  )
}
