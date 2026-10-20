import { useState, type FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import { ApiClientError } from '../api/client'
import { useAuth } from '../contexts/AuthContext'
import { AuthShell } from '../components/AuthShell'
import { PasswordInput } from '../components/PasswordInput'
import { Icon } from '../components/Icon'
import {
  acceptPasswordInput,
  getPasswordValidationError,
  MIN_PASSWORD_LENGTH,
} from '../utils/password'

export function SetupPage() {
  const { setup } = useAuth()
  const navigate = useNavigate()
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [confirm, setConfirm] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault()
    setError('')

    const passwordError = getPasswordValidationError(password)
    if (passwordError) {
      setError(passwordError)
      return
    }
    if (password !== confirm) {
      setError('两次输入的密码不一致')
      return
    }

    setLoading(true)
    try {
      await setup({ username, password })
      navigate('/', { replace: true })
    } catch (err) {
      setError(err instanceof ApiClientError ? err.message : '初始化失败，请重试')
    } finally {
      setLoading(false)
    }
  }

  return (
    <AuthShell subtitle="首次使用，创建管理员账户">
      <form onSubmit={handleSubmit} className="space-y-6" aria-busy={loading}>
        <div>
          <label className="label" htmlFor="username">
            用户名
          </label>
          <div className="relative">
            <span className="pointer-events-none absolute inset-y-0 left-3.5 flex items-center text-muted-foreground"><Icon name="user" /></span>
            <input
              id="username"
              name="username"
              className="input h-14 pl-10 text-base"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              required
              minLength={3}
              maxLength={64}
              autoComplete="username"
              placeholder="请输入管理员用户名"
            />
          </div>
        </div>
        <div>
          <label className="label" htmlFor="password">
            密码
          </label>
          <PasswordInput
            id="password"
            name="password"
            value={password}
            onChange={(e) =>
              setPassword(acceptPasswordInput(password, e.target.value))
            }
            required
            minLength={MIN_PASSWORD_LENGTH}
            autoComplete="new-password"
            placeholder="请输入密码"
          />
        </div>
        <div>
          <label className="label" htmlFor="confirm">
            确认密码
          </label>
          <PasswordInput
            id="confirm"
            name="confirm-password"
            value={confirm}
            onChange={(e) =>
              setConfirm(acceptPasswordInput(confirm, e.target.value))
            }
            required
            minLength={MIN_PASSWORD_LENGTH}
            autoComplete="new-password"
            placeholder="请再次输入密码"
          />
        </div>

        {error && (
          <p role="alert" className="rounded-xl border border-destructive/20 bg-destructive/10 px-3 py-2 text-sm text-destructive">{error}</p>
        )}

        <button type="submit" className="btn-primary h-14 w-full text-base" disabled={loading}>
          {loading ? '创建中…' : '创建管理员账户'}
          {!loading && <Icon name="arrow-right" />}
        </button>
      </form>
    </AuthShell>
  )
}
