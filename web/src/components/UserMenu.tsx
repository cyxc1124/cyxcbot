import { useEffect, useId, useRef, useState } from 'react'
import { useAuth } from '../contexts/AuthContext'
import { ChangePasswordDialog } from './ChangePasswordDialog'
import { Icon } from './Icon'

export function UserMenu() {
  const { user, logout } = useAuth()
  const detailsRef = useRef<HTMLDetailsElement>(null)
  const [changingPassword, setChangingPassword] = useState(false)
  const panelId = useId()

  useEffect(() => {
    const onPointerDown = (event: PointerEvent) => {
      const details = detailsRef.current
      if (details?.open && !details.contains(event.target as Node)) details.open = false
    }
    const onKeyDown = (event: KeyboardEvent) => {
      const details = detailsRef.current
      if (event.key === 'Escape' && details?.open) {
        details.open = false
        details.querySelector('summary')?.focus()
      }
    }
    document.addEventListener('pointerdown', onPointerDown)
    document.addEventListener('keydown', onKeyDown)
    return () => {
      document.removeEventListener('pointerdown', onPointerDown)
      document.removeEventListener('keydown', onKeyDown)
    }
  }, [])

  return (
    <>
      <details ref={detailsRef} className="group relative z-10 shrink-0">
        <summary
          aria-label={`账户：${user?.username ?? ''}`}
          aria-controls={panelId}
          className="inline-flex min-h-11 cursor-pointer list-none items-center gap-2 rounded-full border border-border bg-background px-3 text-sm text-foreground hover:bg-accent focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring [&::-webkit-details-marker]:hidden"
        >
          <Icon name="user" className="size-4 shrink-0" />
          <span className="max-w-32 truncate">{user?.username}</span>
          <Icon name="chevron-down" className="size-3 text-muted-foreground group-open:rotate-180" />
        </summary>
        <div id={panelId} className="absolute right-0 top-full mt-2 w-56 max-w-[calc(100vw-1.5rem)] rounded-2xl border border-border bg-popover p-2 text-popover-foreground shadow-lg">
          <div className="mb-1 border-b border-border px-3 py-2">
            <p className="break-all text-sm font-medium">{user?.username}</p>
            <p className="text-xs text-muted-foreground">{user?.is_admin ? '管理员' : '用户'}</p>
          </div>
          <button type="button" className="btn-ghost min-h-11 w-full justify-start text-sm" onClick={() => {
            if (detailsRef.current) detailsRef.current.open = false
            setChangingPassword(true)
          }}>修改密码</button>
          <button type="button" onClick={logout} className="btn-ghost min-h-11 w-full justify-start text-sm text-destructive">退出登录</button>
        </div>
      </details>
      {changingPassword && <ChangePasswordDialog username={user?.username ?? ''} onClose={() => {
        setChangingPassword(false)
        detailsRef.current?.querySelector('summary')?.focus()
      }} />}
    </>
  )
}
