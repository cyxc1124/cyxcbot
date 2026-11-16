import type { IconName } from '../components/Icon'

export interface NavigationItem {
  to: string
  label: string
  icon: IconName
  description?: string
  title?: string
}

export interface NavigationSection {
  section: string
  icon: IconName
  branch?: string
  groups: { label?: string; items: NavigationItem[] }[]
}

export const navigationSections: NavigationSection[] = [
  { section: '概览', icon: 'home', groups: [{ items: [{ to: '/', label: '仪表盘', icon: 'home' }] }] },
  {
    section: 'B 站',
    icon: 'document',
    groups: [{ items: [
      { to: '/bilibili/dynamic', label: '动态订阅', icon: 'play' },
      { to: '/bilibili/live', label: '直播订阅', icon: 'video' },
      { to: '/bilibili/parser', label: '链接解析', icon: 'globe' },
      { to: '/bilibili/templates', label: '消息模板', icon: 'messages' },
      { to: '/bilibili/settings', label: '订阅参数', icon: 'settings', description: '动态与直播检查间隔、监控方式和图片模式' },
      { to: '/bilibili/account', label: '账号', icon: 'user', description: '多账号扫码登录、验证与请求轮换' },
    ] }],
  },
  {
    section: 'X',
    icon: 'x',
    groups: [{ items: [
      { to: '/x/subscriptions', label: '推文订阅', icon: 'play' },
      { to: '/x/parser', label: '链接解析', icon: 'globe' },
      { to: '/x/templates', label: '消息模板', icon: 'messages' },
      { to: '/x/settings', label: '订阅参数', icon: 'settings', description: '推文检查间隔与分散检查' },
      { to: '/x/account', label: '账号与代理', icon: 'user', description: 'Bearer Token 与 X 选用的出站代理' },
    ] }],
  },
  {
    section: '抖音',
    icon: 'video',
    groups: [{ items: [
      { to: '/douyin/parser', label: '链接解析', icon: 'globe' },
      { to: '/douyin/templates', label: '消息模板', icon: 'messages' },
      { to: '/douyin/account', label: '账号', icon: 'user', description: '扫码登录与抖音 Cookie 管理' },
    ] }],
  },
  {
    section: '会话',
    icon: 'messages',
    groups: [{ items: [
      { to: '/groups', label: '群组', icon: 'users' },
      { to: '/friends', label: '好友', icon: 'users' },
    ] }],
  },
  {
    section: '游戏',
    icon: 'cube',
    branch: 'Rust 管理',
    groups: [
      { label: '远控与权限', items: [
        { to: '/rust/remote/servers', label: '服务器绑定', icon: 'command' },
        { to: '/rust/remote/groups', label: '群权限', icon: 'users' },
        { to: '/rust/remote/friends', label: '好友权限', icon: 'users' },
        { to: '/rust/remote/commands', label: '群管命令', icon: 'command' },
        { to: '/rust/remote/custom', label: '自定义指令', icon: 'command' },
      ] },
      { label: '玩家与积分', items: [
        { to: '/rust/players/accounts', label: '积分与绑定', icon: 'user' },
        { to: '/rust/players/shop', label: '积分商城', icon: 'grid' },
      ] },
    ],
  },
  {
    section: 'AI 图片检测',
    icon: 'photo',
    groups: [{ items: [
      { to: '/ai-image/sources', label: '检测来源', title: '图片检测来源', icon: 'settings', description: '本地 C2PA、OpenAI C2PA 与 SynthID（OpenAI）开关及 OpenAI 密钥' },
      { to: '/ai-image/vision', label: '视觉模型', title: '视觉模型共同识别', icon: 'eye', description: '接入多个 OpenAI / Anthropic 兼容的视觉模型，与来源检测一起给出参考判断' },
      { to: '/ai-image/command', label: '触发命令', title: '图片检测触发命令', icon: 'command', description: '自定义触发词与命令开关' },
    ] }],
  },
  { section: '运行日志', icon: 'document', groups: [{ items: [{ to: '/logs', label: '运行日志', icon: 'document' }] }] },
  {
    section: '系统',
    icon: 'settings',
    groups: [{ items: [
      { to: '/system/connections', label: '机器人接入', icon: 'settings', description: '官方 QQ Bot 凭证、接入方式与 OneBot 连接说明' },
      { to: '/system/permissions', label: '权限', title: '权限管理', icon: 'settings', description: '配置超级用户与状态查询的额外授权' },
      { to: '/system/commands', label: '命令', icon: 'command', description: '通用命令触发词、开关与习惯性前缀' },
      { to: '/system/proxies', label: '网络代理', icon: 'globe', description: '添加多个出站代理，供 X、AI 图片检测等功能分别选用' },
      { to: '/system/advanced', label: '高级配置', icon: 'settings', description: '链接解析共享媒体目录' },
      { to: '/about', label: '关于', icon: 'info' },
    ] }],
  },
]

export function findNavigation(pathname: string) {
  const path = pathname.replace(/\/+$/, '') || '/'
  for (const section of navigationSections) {
    for (const group of section.groups) {
      const item = group.items.find((entry) => entry.to === path)
      if (item) return { section: section.section, branch: section.branch, group: group.label, item }
    }
  }
}
