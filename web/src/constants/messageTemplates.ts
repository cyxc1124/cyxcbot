export type TemplateKey =
  | 'dynamic_template_push'
  | 'dynamic_template_pinned'
  | 'dynamic_template_query_latest'
  | 'dynamic_template_query_pinned'
  | 'dynamic_template_extract'
  | 'dynamic_template_extract_empty'
  | 'dynamic_template_extract_failed'
  | 'dynamic_template_extract_image_label'
  | 'live_template_start'
  | 'live_template_end'
  | 'link_template_video'
  | 'link_template_live'

export type TemplateCategory = 'dynamic' | 'live' | 'link'

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
  dynamic_template_extract: '动态{dynamic_id}的图片\n{images}\n{url}',
  dynamic_template_extract_empty: '动态{dynamic_id}的图片\n该动态未找到可提取的图片\n{url}',
  dynamic_template_extract_failed: '动态{dynamic_id}的图片\n提取失败，请稍后重试\n{url}',
  dynamic_template_extract_image_label: '图片{index}',
  live_template_start: '{streamer_name} 开播啦！\n{card}\n{url}',
  live_template_end: '【下播提醒】\n{streamer_name}下播啦！\n{card}\n直播时长：{duration}',
  link_template_video: '{cover}标题：{title}\nUP主：{author}\n发布时间：{pub_date}\n链接：{url}',
  link_template_live:
    '{cover}标题：{title}\n主播：{streamer_name}\n状态：{status}\n开播时间：{live_start_time}\n分区：{area}\n链接：{url}',
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

const extractVariables: TemplateVariable[] = [
  { key: 'dynamic_id', label: '动态 ID', description: 'B 站动态编号' },
  { key: 'url', label: '动态链接', description: 't.bilibili.com 链接' },
  {
    key: 'images',
    label: '动态图片列表',
    description: '按顺序插入全部图片，每张前带单图标签',
    segment: true,
  },
]

const extractImageLabelVariables: TemplateVariable[] = [
  { key: 'index', label: '图片序号', description: '从 1 开始的序号' },
  { key: 'dynamic_id', label: '动态 ID', description: 'B 站动态编号' },
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
  {
    key: 'dynamic_template_extract',
    category: 'dynamic',
    label: '动态图片提取',
    description: '发送 #提取/#获取{动态ID} 成功提取到图片时的完整回复内容',
    defaultValue: DEFAULT_MESSAGE_TEMPLATES.dynamic_template_extract,
    variables: extractVariables,
  },
  {
    key: 'dynamic_template_extract_empty',
    category: 'dynamic',
    label: '动态图片提取（无图）',
    description: '动态中未找到可提取图片时的回复内容',
    defaultValue: DEFAULT_MESSAGE_TEMPLATES.dynamic_template_extract_empty,
    variables: extractVariables.filter((v) => v.key !== 'images'),
  },
  {
    key: 'dynamic_template_extract_failed',
    category: 'dynamic',
    label: '动态图片提取（失败）',
    description: '拉取动态详情失败时的回复内容',
    defaultValue: DEFAULT_MESSAGE_TEMPLATES.dynamic_template_extract_failed,
    variables: extractVariables.filter((v) => v.key !== 'images'),
  },
  {
    key: 'dynamic_template_extract_image_label',
    category: 'dynamic',
    label: '动态图片提取（单图标签）',
    description: '每张图片前的标签文字，会按序号重复插入',
    defaultValue: DEFAULT_MESSAGE_TEMPLATES.dynamic_template_extract_image_label,
    variables: extractImageLabelVariables,
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

const linkVideoVariables: TemplateVariable[] = [
  { key: 'cover', label: '视频封面', description: '视频封面图片', segment: true },
  { key: 'title', label: '标题', description: '视频标题' },
  { key: 'author', label: 'UP 主', description: 'UP 主显示名称' },
  { key: 'pub_date', label: '发布时间', description: '视频发布时间' },
  { key: 'url', label: '视频链接', description: 'bilibili.com/video 链接' },
  { key: 'bvid', label: 'BV 号', description: '视频 BV 号' },
  { key: 'aid', label: 'AV 号', description: '视频 AV 号（数字）' },
]

const linkLiveVariables: TemplateVariable[] = [
  { key: 'cover', label: '直播封面', description: '直播间封面图片', segment: true },
  { key: 'title', label: '标题', description: '直播间标题' },
  { key: 'streamer_name', label: '主播名', description: '主播显示名称' },
  { key: 'status', label: '直播状态', description: '直播中 / 未开播 / 轮播中' },
  { key: 'live_start_time', label: '开播时间', description: '未开播时为 —' },
  { key: 'area', label: '分区', description: '直播分区名称' },
  { key: 'url', label: '直播间链接', description: 'live.bilibili.com 链接' },
  { key: 'room_id', label: '房间号', description: '直播间 room_id' },
]

export const linkTemplateFields: TemplateField[] = [
  {
    key: 'link_template_video',
    category: 'link',
    label: '视频链接解析',
    description: '群聊/好友中识别到 B 站视频链接时的自动回复内容',
    defaultValue: DEFAULT_MESSAGE_TEMPLATES.link_template_video,
    variables: linkVideoVariables,
  },
  {
    key: 'link_template_live',
    category: 'link',
    label: '直播链接解析',
    description: '群聊/好友中识别到 B 站直播间链接时的自动回复内容',
    defaultValue: DEFAULT_MESSAGE_TEMPLATES.link_template_live,
    variables: linkLiveVariables,
  },
]

export const allTemplateFields = [...dynamicTemplateFields, ...liveTemplateFields, ...linkTemplateFields]

export const templateCategoryLabels: Record<TemplateCategory, string> = {
  dynamic: '动态模板',
  live: '直播模板',
  link: '链接解析',
}

export const PREVIEW_SEGMENT_LABELS: Record<string, string> = {
  media: '[动态截图或正文图片]',
  card: '[卡片图片]',
  cover: '[封面图片]',
  images: '[图片1]\n[图片2]',
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
  author: '张三',
  pub_date: '2026-06-08 14:30:00',
  status: '直播中',
  live_start_time: '2026-06-08 20:00:00',
  area: '娱乐',
  room_id: '12345',
  bvid: 'BV1xx411c7mD',
  aid: '170001',
  index: '1',
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
