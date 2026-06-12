import { useEffect, type ReactNode } from 'react'

type ConfirmDialogProps = {
  open: boolean
  title: string
  message: ReactNode
  confirmLabel?: string
  cancelLabel?: string
  loading?: boolean
  onConfirm: () => void
  onCancel: () => void
}

export function ConfirmDialog({
  open,
  title,
  message,
  confirmLabel = '确认',
  cancelLabel = '取消',
  loading = false,
  onConfirm,
  onCancel,
}: ConfirmDialogProps) {
  useEffect(() => {
    if (!open) return

    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape' && !loading) {
        onCancel()
      }
    }

    document.addEventListener('keydown', onKeyDown)
    const previousOverflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'

    return () => {
      document.removeEventListener('keydown', onKeyDown)
      document.body.style.overflow = previousOverflow
    }
  }, [loading, onCancel, open])

  if (!open) return null

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4"
      role="presentation"
      onClick={loading ? undefined : onCancel}
    >
      <div className="absolute inset-0 bg-background/80 backdrop-blur-xs" />
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="confirm-dialog-title"
        className="card relative z-10 w-full max-w-md space-y-5 shadow-xl"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="space-y-2">
          <h3 id="confirm-dialog-title" className="text-lg font-semibold text-foreground">
            {title}
          </h3>
          <div className="text-sm text-muted-foreground">{message}</div>
        </div>
        <div className="flex justify-end gap-3">
          <button type="button" className="btn-secondary" disabled={loading} onClick={onCancel}>
            {cancelLabel}
          </button>
          <button type="button" className="btn-danger" disabled={loading} onClick={onConfirm}>
            {loading ? '处理中…' : confirmLabel}
          </button>
        </div>
      </div>
    </div>
  )
}
