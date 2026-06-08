import { useState, type FormEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { ApiClientError } from '../api/client'
import { useAuth } from '../contexts/AuthContext'

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
    <div className="flex min-h-screen items-center justify-center bg-gradient-to-br from-slate-50 to-brand-50 p-4 dark:from-slate-950 dark:to-slate-900">
      <div className="card w-full max-w-md">
        <div className="mb-8 text-center">
          <span className="text-4xl">🤖</span>
          <h1 className="mt-4 text-2xl font-bold text-slate-900 dark:text-white">
            登录 cyxcbot
          </h1>
          <p className="mt-2 text-sm text-slate-500">Web 管理面板</p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="label" htmlFor="username">
              用户名
            </label>
            <input
              id="username"
              className="input"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              required
              autoComplete="username"
            />
          </div>
          <div>
            <label className="label" htmlFor="password">
              密码
            </label>
            <input
              id="password"
              type="password"
              className="input"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              autoComplete="current-password"
            />
          </div>

          {error && (
            <p className="text-sm text-red-600 dark:text-red-400">{error}</p>
          )}

          <button type="submit" className="btn-primary w-full" disabled={loading}>
            {loading ? '登录中…' : '登录'}
          </button>
        </form>

        {initialized === false && (
          <p className="mt-6 text-center text-xs text-slate-500">
            首次使用？{' '}
            <Link to="/setup" className="text-brand-600 hover:underline">
              前往初始化
            </Link>
          </p>
        )}
      </div>
    </div>
  )
}
