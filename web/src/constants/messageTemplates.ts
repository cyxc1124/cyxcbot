export type TemplateKey =
  | 'dynamic_template_push'
  | 'dynamic_template_pinned'
  | 'dynamic_template_query_latest'
  | 'dynamic_template_query_pinned'
  | 'live_template_start'
  | 'live_template_end'

export type TemplateCategory = 'dynamic' | 'live'

export type TemplateVariable = {
  key: string
  label: string
  description: string
  segment?: boolean
}

export type TemplateField = {
  key: TemplateKey
  category: TemplateCategory
  label: string
  description: string
  defaultValue: string
  variables: TemplateVariable[]
}

export const DEFAULT_MESSAGE_TEMPLATES: Record<TemplateKey, string> = {
  dynamic_template_push: '{name} {type_desc}\n{time}\n{media}\n{url}',
  dynamic_template_pinned: '{name} 置顶了动态\n{time}\n{media}\n{url}',
  dynamic_template_query_latest: '【{name} 的最新动态】\n{media}\n{url}',
  dynamic_template_query_pinned: '【{name} 的置顶动态】\n{media}\n{url}',
  live_template_start: '{streamer_name} 开播啦！\n{card}\n{url}',
  live_template_end: '【下播提醒】\n{streamer_name}下播啦！\n{card}\n直播时长：{duration}',
}

const dynamicMediaVariable: TemplateVariable = {
  key: 'media',
  label: '动态图片',
  description: '截图模式为网页截图；关闭截图时为正文与图片',
  segment: true,
}

const dynamicVariables: TemplateVariable[] = [
  { key: 'name', label: 'UP 主名', description: 'UP 主显示名称' },
  { key: 'type_desc', label: '动态类型', description: '如「发布了新投稿视频」' },
  { key: 'time', label: '发布时间', description: '动态发布时间' },
  dynamicMediaVariable,
  { key: 'url', label: '动态链接', description: 't.bilibili.com 链接' },
  { key: 'dynamic_id', label: '动态 ID', description: 'B 站动态编号' },
  { key: 'uid', label: 'UID', description: 'UP 主 UID' },
]

const liveStartVariables: TemplateVariable[] = [
  { key: 'streamer_name', label: '主播名', description: '主播显示名称' },
  { key: 'card', label: '开播卡片', description: '生成的开播卡片图片', segment: true },
  { key: 'title', label: '直播标题', description: '当前直播标题' },
  { key: 'time', label: '开播时间', description: '开播时间文本' },
  {
    key: 'cover',
    label: '直播封面',
    description: '无卡片时可插入封面图',
    segment: true,
  },
  { key: 'url', label: '直播间链接', description: 'live.bilibili.com 链接' },
]

const liveEndVariables: TemplateVariable[] = [
  { key: 'streamer_name', label: '主播名', description: '主播显示名称' },
  { key: 'card', label: '下播卡片', description: '生成的下播卡片图片', segment: true },
  { key: 'duration', label: '直播时长', description: '如「1小时23分钟45秒」' },
]

export const dynamicTemplateFields: TemplateField[] = [
  {
    key: 'dynamic_template_push',
    category: 'dynamic',
    label: '新动态推送',
    description: '检测到 UP 主发布新动态时的完整推送内容',
    defaultValue: DEFAULT_MESSAGE_TEMPLATES.dynamic_template_push,
    variables: dynamicVariables,
  },
  {
    key: 'dynamic_template_pinned',
    category: 'dynamic',
    label: '置顶动态变更',
    description: 'UP 主置顶动态变更时的完整推送内容',
    defaultValue: DEFAULT_MESSAGE_TEMPLATES.dynamic_template_pinned,
    variables: dynamicVariables.filter((v) => v.key !== 'type_desc'),
  },
  {
    key: 'dynamic_template_query_latest',
    category: 'dynamic',
    label: '最新动态查询',
    description: '群命令查询最新动态时的完整回复内容',
    defaultValue: DEFAULT_MESSAGE_TEMPLATES.dynamic_template_query_latest,
    variables: dynamicVariables.filter((v) => !['type_desc', 'time'].includes(v.key)),
  },
  {
    key: 'dynamic_template_query_pinned',
    category: 'dynamic',
    label: '置顶动态查询',
    description: '群命令查询置顶动态时的完整回复内容',
    defaultValue: DEFAULT_MESSAGE_TEMPLATES.dynamic_template_query_pinned,
    variables: dynamicVariables.filter((v) => !['type_desc', 'time'].includes(v.key)),
  },
]

export const liveTemplateFields: TemplateField[] = [
  {
    key: 'live_template_start',
    category: 'live',
    label: '开播通知',
    description: '检测到主播开播时的完整推送内容',
    defaultValue: DEFAULT_MESSAGE_TEMPLATES.live_template_start,
    variables: liveStartVariables,
  },
  {
    key: 'live_template_end',
    category: 'live',
    label: '下播通知',
    description: '检测到主播下播时的完整推送内容',
    defaultValue: DEFAULT_MESSAGE_TEMPLATES.live_template_end,
    variables: liveEndVariables,
  },
]

export const allTemplateFields = [...dynamicTemplateFields, ...liveTemplateFields]

export const templateCategoryLabels: Record<TemplateCategory, string> = {
  dynamic: '动态模板',
  live: '直播模板',
}

export const PREVIEW_SEGMENT_LABELS: Record<string, string> = {
  media: '[动态截图或正文图片]',
  card: '[卡片图片]',
  cover: '[直播封面]',
}

export const PREVIEW_SAMPLE_VALUES: Record<string, string> = {
  name: '张三',
  type_desc: '发布了新投稿视频',
  time: '2026-06-08 14:30:00',
  url: 'https://t.bilibili.com/1234567890',
  dynamic_id: '1234567890',
  uid: '12345',
  streamer_name: '李四',
  title: '今天聊聊天~',
  duration: '1小时23分钟45秒',
}

export function createDefaultTemplateForm(): Record<TemplateKey, string> {
  return { ...DEFAULT_MESSAGE_TEMPLATES }
}

export function templatesFromSettings(
  settings: Partial<Record<TemplateKey, string>> | null | undefined,
): Record<TemplateKey, string> {
  const form = createDefaultTemplateForm()
  if (!settings) return form
  for (const field of allTemplateFields) {
    const value = settings[field.key]?.trim()
    if (value) {
      form[field.key] = value
    }
  }
  return form
}

export function getTemplateField(key: TemplateKey): TemplateField {
  const field = allTemplateFields.find((item) => item.key === key)
  if (!field) {
    throw new Error(`Unknown template key: ${key}`)
  }
  return field
}
