interface LoadErrorBannerProps {
  message?: string
  onRetry?: () => void
}

export function LoadErrorBanner({
  message = '后端服务暂不可用，数据暂时无法加载',
  onRetry,
}: LoadErrorBannerProps) {
  return (
    <div className="rounded-lg border border-amber-200 bg-amber-50 p-3 dark:border-amber-900/50 dark:bg-amber-950/30">
      <div className="flex items-center justify-between gap-4">
        <p className="text-sm text-amber-800 dark:text-amber-200">{message}</p>
        {onRetry && (
          <button
            type="button"
            onClick={onRetry}
            className="btn-ghost shrink-0 text-sm text-amber-700 dark:text-amber-300"
          >
            重试
          </button>
        )}
      </div>
    </div>
  )
}
