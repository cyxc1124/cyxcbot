interface ErrorAlertProps {
  message: string
  onRetry?: () => void
}

export function ErrorAlert({ message, onRetry }: ErrorAlertProps) {
  return (
    <div className="rounded-lg border border-red-200 bg-red-50 p-4 dark:border-red-900/50 dark:bg-red-950/30">
      <div className="flex items-start justify-between gap-4">
        <p className="text-sm text-red-700 dark:text-red-300">{message}</p>
        {onRetry && (
          <button type="button" onClick={onRetry} className="btn-ghost shrink-0 text-red-600">
            重试
          </button>
        )}
      </div>
    </div>
  )
}
