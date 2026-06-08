import { useState, type FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import { ApiClientError } from '../api/client'
import { useAuth } from '../contexts/AuthContext'

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

    if (password.length < 8) {
      setError('密码至少需要 8 个字符')
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
    <div className="flex min-h-screen items-center justify-center bg-gradient-to-br from-slate-50 to-brand-50 p-4 dark:from-slate-950 dark:to-slate-900">
      <div className="card w-full max-w-md">
        <div className="mb-8 text-center">
          <h1 className="text-2xl font-bold text-slate-900 dark:text-white">
            欢迎使用 机器草
          </h1>
          <p className="mt-2 text-sm text-slate-500">
            首次使用，请创建管理员账户
          </p>
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
              minLength={3}
              autoComplete="username"
              placeholder="admin"
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
              minLength={8}
              autoComplete="new-password"
            />
          </div>
          <div>
            <label className="label" htmlFor="confirm">
              确认密码
            </label>
            <input
              id="confirm"
              type="password"
              className="input"
              value={confirm}
              onChange={(e) => setConfirm(e.target.value)}
              required
              autoComplete="new-password"
            />
          </div>

          {error && (
            <p className="text-sm text-red-600 dark:text-red-400">{error}</p>
          )}

          <button type="submit" className="btn-primary w-full" disabled={loading}>
            {loading ? '创建中…' : '创建管理员账户'}
          </button>
        </form>
      </div>
    </div>
  )
}
