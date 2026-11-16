import { Link } from 'react-router-dom'
import type { ProxyEntry } from '../api/types'
import { PROXIES_PATH, proxyAddress } from '../pages/settings/proxyForm'

/** 选择某个功能使用的出站代理；没有代理时引导用户先去添加。 */
export function ProxyPicker({ id, value, proxies, disabled, onChange }: {
  id: string
  value: string
  proxies: ProxyEntry[]
  disabled: boolean
  onChange: (proxyId: string) => void
}) {
  const missing = value !== '' && !proxies.some((proxy) => proxy.id === value)
  return (
    <div className="space-y-2">
      <select id={id} className="input" value={missing ? '' : value} disabled={disabled}
        onChange={(event) => onChange(event.target.value)}>
        <option value="">不使用代理（直接连接）</option>
        {proxies.map((proxy) => (
          <option key={proxy.id} value={proxy.id}>{proxy.name}（{proxyAddress(proxy)}）</option>
        ))}
      </select>
      {missing && (
        <p className="text-xs text-amber-600 dark:text-amber-400">之前选择的代理已被删除，当前直接连接，请重新选择。</p>
      )}
      {proxies.length === 0 ? (
        <p className="text-xs text-muted-foreground">
          还没有添加代理。服务器无法直接访问该服务时，先到{' '}
          <Link to={PROXIES_PATH} className="text-primary hover:underline">系统 → 网络代理</Link>{' '}
          添加，再回到这里选择。
        </p>
      ) : (
        <p className="text-xs text-muted-foreground">
          代理在 <Link to={PROXIES_PATH} className="text-primary hover:underline">系统 → 网络代理</Link> 中统一添加和测试。
        </p>
      )}
    </div>
  )
}
