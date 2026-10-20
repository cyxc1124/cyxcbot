import { useState, type FormEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { ApiClientError } from '../api/client'
import { useAuth } from '../contexts/AuthContext'
import { AuthShell } from '../components/AuthShell'
import { PasswordInput } from '../components/PasswordInput'
import { Icon } from '../components/Icon'
import {
  getLoginPasswordValidationError,
  MIN_PASSWORD_LENGTH,
} from '../utils/password'

export function LoginPage() {
  const { login, initialized } = useAuth()
  const navigate = useNavigate()
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault()
    setError('')

    const passwordError = getLoginPasswordValidationError(password)
    if (passwordError) {
      setError(passwordError)
      return
    }

    setLoading(true)
    try {
      await login({ username, password })
      navigate('/', { replace: true })
    } catch (err) {
      setError(err instanceof ApiClientError ? err.message : '登录失败，请重试')
    } finally {
      setLoading(false)
    }
  }

  return (
    <AuthShell subtitle="登录 Web 管理面板">
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
              placeholder="请输入用户名"
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
            onChange={(e) => setPassword(e.target.value)}
            required
            minLength={MIN_PASSWORD_LENGTH}
            autoComplete="current-password"
            placeholder="请输入密码"
          />
        </div>

        {error && (
          <p role="alert" className="rounded-xl border border-destructive/20 bg-destructive/10 px-3 py-2 text-sm text-destructive">{error}</p>
        )}

        <button type="submit" className="btn-primary h-14 w-full text-base" disabled={loading}>
          {loading ? '登录中…' : '登录'}
          {!loading && <Icon name="arrow-right" />}
        </button>
      </form>

      {initialized === false && (
        <p className="mt-6 text-center text-xs text-muted-foreground">
          首次使用？{' '}
          <Link to="/setup" className="text-primary hover:underline">
            前往初始化
          </Link>
        </p>
      )}
    </AuthShell>
  )
}
