import { useEffect, useId, useRef, useState, type FormEvent } from 'react'
import { ApiClientError, putPassword, setToken } from '../api/client'
import { useToast } from '../contexts/ToastContext'
import { acceptPasswordInput, getPasswordValidationError, MIN_PASSWORD_LENGTH } from '../utils/password'
import { PasswordInput } from './PasswordInput'

export function ChangePasswordDialog({ username, onClose }: { username: string; onClose: () => void }) {
  const dialogRef = useRef<HTMLDialogElement>(null)
  const titleId = useId()
  const { showToast } = useToast()
  const [currentPassword, setCurrentPassword] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [confirm, setConfirm] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    dialogRef.current?.showModal()
    const previousOverflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    return () => { document.body.style.overflow = previousOverflow }
  }, [])

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault()
    if (loading) return
    setError('')
    const passwordError = getPasswordValidationError(newPassword)
    if (passwordError) {
      setError(passwordError)
      return
    }
    if (newPassword !== confirm) {
      setError('两次输入的密码不一致')
      return
    }
    setLoading(true)
    try {
      const { access_token } = await putPassword({ current_password: currentPassword, new_password: newPassword })
      setToken(access_token)
      showToast('success', '密码修改成功，其他登录已失效')
      dialogRef.current?.close()
    } catch (err) {
      setError(err instanceof ApiClientError ? err.message : '修改密码失败，请重试')
    } finally {
      setLoading(false)
    }
  }

  return (
    <dialog
      ref={dialogRef}
      aria-labelledby={titleId}
      className="card fixed inset-0 m-auto max-h-[calc(100dvh-2rem)] w-[calc(100%-2rem)] max-w-md overflow-y-auto text-foreground shadow-xl backdrop:bg-black/40"
      onCancel={(event) => { if (loading) event.preventDefault() }}
      onClose={onClose}
    >
      <form onSubmit={handleSubmit} className="space-y-4" aria-busy={loading}>
        <div>
          <h2 id={titleId} className="text-lg font-semibold">修改密码</h2>
          <p className="mt-1 text-sm text-muted-foreground">修改后，其他设备需要使用新密码重新登录。</p>
        </div>
        <input type="hidden" name="username" autoComplete="username" value={username} />
        <div>
          <label className="label" htmlFor="current-password">当前密码</label>
          <PasswordInput
            id="current-password"
            name="current-password"
            value={currentPassword}
            onChange={(event) => setCurrentPassword(event.target.value)}
            autoComplete="current-password"
            minLength={MIN_PASSWORD_LENGTH}
            maxLength={128}
            required
            autoFocus
            disabled={loading}
          />
        </div>
        <div>
          <label className="label" htmlFor="new-password">新密码</label>
          <PasswordInput
            id="new-password"
            name="new-password"
            value={newPassword}
            onChange={(event) => setNewPassword(acceptPasswordInput(newPassword, event.target.value))}
            autoComplete="new-password"
            minLength={MIN_PASSWORD_LENGTH}
            required
            disabled={loading}
          />
          <p className="mt-1 text-xs text-muted-foreground">至少 8 个字符，最多 72 个 UTF-8 字节。</p>
        </div>
        <div>
          <label className="label" htmlFor="confirm-password">确认新密码</label>
          <PasswordInput
            id="confirm-password"
            name="confirm-password"
            value={confirm}
            onChange={(event) => setConfirm(acceptPasswordInput(confirm, event.target.value))}
            autoComplete="new-password"
            minLength={MIN_PASSWORD_LENGTH}
            required
            disabled={loading}
          />
        </div>
        {error && <p role="alert" className="rounded-xl border border-destructive/20 bg-destructive/10 px-3 py-2 text-sm text-destructive">{error}</p>}
        <div className="flex justify-end gap-3 pt-2">
          <button type="button" className="btn-secondary" disabled={loading} onClick={() => dialogRef.current?.close()}>取消</button>
          <button type="submit" className="btn-primary" disabled={loading}>{loading ? '保存中…' : '保存密码'}</button>
        </div>
      </form>
    </dialog>
  )
}
