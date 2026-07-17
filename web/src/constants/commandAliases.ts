export type CommandId =
  | 'status'
  | 'live_status'
  | 'live_monitor_list'
  | 'dynamic_query_latest'
  | 'dynamic_query_pinned'
  | 'video_query_latest'
  | 'dynamic_extract'
  | 'group_special_title'

export type CommandField = {
  id: CommandId
  label: string
  description: string
  defaultTriggers: string[]
  hint?: string
}

export const COMMAND_FIELDS: CommandField[] = [
  {
    id: 'status',
    label: '运行状态查询',
    description: '查询机器人运行状态（群聊或私聊均可，需相应权限）。',
    defaultTriggers: ['status', '状态', '运行状态'],
  },
  {
    id: 'live_status',
    label: '直播状态查询',
    description: '查询指定房间号的直播状态（仅群聊）。',
    defaultTriggers: ['直播状态', '查直播', 'live'],
    hint: '发送时需在触发词后加房间号，例如“直播状态 12345”',
  },
  {
    id: 'live_monitor_list',
    label: '直播监控列表',
    description: '列出当前群配置的直播间监控（仅群聊）。',
    defaultTriggers: ['监控列表', '直播监控列表'],
  },
  {
    id: 'dynamic_query_latest',
    label: '最新动态查询',
    description: '查询当前群已配置 UP 主的最新动态（仅群聊）。',
    defaultTriggers: ['最新动态'],
  },
  {
    id: 'dynamic_query_pinned',
    label: '置顶动态查询',
    description: '查询当前群已配置 UP 主的置顶动态（仅群聊）。',
    defaultTriggers: ['置顶动态'],
  },
  {
    id: 'video_query_latest',
    label: '最新投稿查询',
    description: '查询当前群已配置 UP 主的最新投稿视频（仅群聊）。',
    defaultTriggers: ['最新视频', '最新投稿'],
  },
  {
    id: 'dynamic_extract',
    label: '动态图片提取',
    description: '提取动态内全部图片（群聊或私聊，需已订阅动态）。',
    defaultTriggers: ['提取', '获取'],
    hint: '仅支持 # 前缀，格式为“#触发词+动态ID或链接”，例如“#提取123456789”',
  },
  {
    id: 'group_special_title',
    label: '群头衔设置',
    description: '群成员自助设置专属头衔（仅群聊，机器人需为群主）。',
    defaultTriggers: ['头衔'],
    hint: '支持 # / ! / 。 / . 前缀，格式为“触发词 头衔内容”，例如“/头衔 我的头衔”',
  },
]
