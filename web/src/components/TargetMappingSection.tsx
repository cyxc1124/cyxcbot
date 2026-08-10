import { useTargetMappings } from '../hooks/useTargetMappings'
import { LoadErrorBanner } from './LoadErrorBanner'
import { TargetDetail } from './TargetDetail'
import { TargetForm } from './TargetForm'
import {
  getTargetDisplayName,
  getTargetId,
  type TargetType,
} from './targetMapping/types'

interface TargetMappingSectionProps {
  type: TargetType
  onTargetsChanged?: () => void | Promise<void>
}

export function TargetMappingSection({ type, onTargetsChanged }: TargetMappingSectionProps) {
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
  const listHiddenOnMobile = showSplit && !showForm && selectedTarget

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="text-sm text-muted-foreground">
          选择{targetLabel}查看推送目标，可同时订阅多个 QQ 群与好友
        </p>
        <button type="button" className="btn-primary" onClick={openCreate}>
          添加订阅
        </button>
      </div>

      {error && <LoadErrorBanner message={error} onRetry={retryLoad} />}

      {loading && targets.length === 0 && !error ? (
        <p className="py-12 text-center text-sm text-muted-foreground">加载中…</p>
      ) : !loading && error && targets.length === 0 ? (
        <p className="py-12 text-center text-sm text-muted-foreground">数据暂时无法加载</p>
      ) : !loading && targets.length === 0 && !showForm ? (
        <p className="py-12 text-center text-sm text-muted-foreground">暂无订阅，点击上方按钮添加</p>
      ) : (
        <div
          className={`flex min-h-112 overflow-hidden rounded-lg border border-border ${
            showSplit ? 'divide-x divide-border' : ''
          }`}
        >
          <aside
            className={`shrink-0 bg-muted/40 ${
              listHiddenOnMobile ? 'hidden lg:block' : ''
            } ${showSplit ? 'w-full lg:w-72' : 'w-full'}`}
          >
            <div className="flex h-full max-h-128 flex-col lg:max-h-144">
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
              className={`min-w-0 flex-1 bg-card p-4 ${
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
    </div>
  )
}
