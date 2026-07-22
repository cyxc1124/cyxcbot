import { useState } from 'react'
import { RustPlayerCommandsTab } from '../components/RustPlayerCommandsTab'
import { RustPlayersTab } from '../components/RustPlayersTab'
import { RustRconGroupPolicyTab, RustRconUserPolicyTab } from '../components/RustRconPolicyTabs'
import { SubPageTabs } from '../components/SubPageTabs'
import { SettingsRustRconPage } from './settings/SettingsRustRcon'

type RustRconTab = 'bindings' | 'groups' | 'users' | 'commands' | 'players'

export function RustRconPage() {
  const [tab, setTab] = useState<RustRconTab>('bindings')

  const tabLabels: Record<RustRconTab, string> = {
    bindings: '服务器绑定',
    groups: '群权限',
    users: '好友权限',
    commands: '群管命令',
    players: '积分与绑定',
  }

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold text-foreground">Rust 远控管理</h2>
        <p className="mt-1 text-sm text-muted-foreground">
          配置 Rust 服务器连接与触发词，管理群/好友远控权限，以及群内签到积分与
          SteamID 绑定。远控在已开启权限的群/好友中发送{' '}
          <code className="font-mono text-xs">@机器人 触发词 命令</code>{' '}
          （私聊无需 @）；群管命令触发词在「群管命令」Tab 中配置。
        </p>
        <p className="mt-2 text-xs text-muted-foreground">
          协议为 Rust WebRCON（WebSocket，默认端口 28016）。
        </p>
      </div>

      <SubPageTabs tabs={tabLabels} value={tab} onChange={setTab} />

      {tab === 'bindings' && <SettingsRustRconPage embedded />}

      {tab === 'groups' && (
        <div className="card">
          <RustRconGroupPolicyTab />
        </div>
      )}

      {tab === 'users' && (
        <div className="card">
          <RustRconUserPolicyTab />
        </div>
      )}

      {tab === 'commands' && <RustPlayerCommandsTab />}

      {tab === 'players' && <RustPlayersTab />}
    </div>
  )
}
