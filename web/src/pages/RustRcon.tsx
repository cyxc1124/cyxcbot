import type { ReactNode } from 'react'
import { Navigate, useLocation, useParams } from 'react-router-dom'
import { RustPlayerCommandsTab } from '../components/RustPlayerCommandsTab'
import { RustPlayersTab } from '../components/RustPlayersTab'
import { RustRconCustomCommandsTab } from '../components/RustRconCustomCommandsTab'
import { RustShopItemsTab } from '../components/RustShopItemsTab'
import { RustRconGroupPolicyTab, RustRconUserPolicyTab } from '../components/RustRconPolicyTabs'
import { findNavigation } from '../constants/navigation'
import { SettingsRustRconPage } from './settings/SettingsRustRcon'

const remotePages: Record<string, ReactNode> = {
  servers: <SettingsRustRconPage embedded />,
  groups: <div className="card"><RustRconGroupPolicyTab /></div>,
  friends: <div className="card"><RustRconUserPolicyTab /></div>,
  commands: <RustPlayerCommandsTab />,
  custom: <RustRconCustomCommandsTab />,
}
const playerPages: Record<string, ReactNode> = {
  accounts: <RustPlayersTab />,
  shop: <RustShopItemsTab />,
}

export function RustRconPage({ area }: { area: 'remote' | 'players' }) {
  const { tab = '' } = useParams<{ tab: string }>()
  const current = findNavigation(useLocation().pathname)
  const pages = area === 'remote' ? remotePages : playerPages

  if (!Object.hasOwn(pages, tab)) return <Navigate to={area === 'remote' ? '/rust/remote/servers' : '/rust/players/accounts'} replace />

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold text-foreground">{current?.item.label}</h2>
        <p className="mt-1 text-sm text-muted-foreground">
          {area === 'remote' ? <>
            配置 Rust 服务器连接、远控指令与会话权限。RCON 开关关闭时，远控与群管相关指令均会被静默忽略；在已开启权限的群/好友中发送{' '}
            <code className="font-mono text-xs">@机器人 触发词 命令</code>（私聊无需 @）。
          </> : '管理 SteamID 绑定、签到积分与积分商城。群管指令仍需对应会话开启 Rust RCON。'}
          群管命令触发词在「远控与权限 → 群管命令」中配置。
        </p>
        {area === 'remote' && <p className="mt-2 text-xs text-muted-foreground">
          协议为 Rust WebRCON（WebSocket，默认端口 28016）。
        </p>}
      </div>

      {pages[tab]}
    </div>
  )
}
