import { describe, expect, it } from 'vitest'
import type { Settings } from '../../api/types'
import { COMMAND_FIELDS } from '../../constants/commandAliases'
import { buildForm } from './commandsForm'

function baseSettings(commandAliases: Settings['command_aliases']): Settings {
  return {
    dynamic_monitor_interval: 60,
    dynamic_monitor_use_stagger: false,
    dynamic_enable_screenshot: false,
    dynamic_template_push: '',
    dynamic_template_pinned: '',
    dynamic_template_query_latest: '',
    dynamic_template_query_pinned: '',
    dynamic_template_extract: '',
    dynamic_template_extract_empty: '',
    dynamic_template_extract_failed: '',
    dynamic_template_extract_image_label: '',
    live_monitor_interval: 60,
    live_monitor_include_info: false,
    live_monitor_use_websocket: false,
    live_template_start: '',
    live_template_end: '',
    link_template_video: '',
    link_template_live: '',
    link_template_douyin: '',
    bilibili_cookie: { configured: false, preview: null },
    douyin_cookie: { configured: false, preview: null },
    status_check_allowed_qq: [],
    nonebot_superusers: [],
    command_aliases: commandAliases,
    command_extra_prefixes: [],
    command_prefixes: [],
    link_parser_shared_media_dir: '',
    link_parser_shared_media_dir_default: '/root/.config/QQ/tmp',
    link_parser_shared_media_dir_resolved: '/root/.config/QQ/tmp',
  }
}

describe('buildForm', () => {
  it('falls back to factory defaults only when the entry is entirely missing', () => {
    const form = buildForm(baseSettings({}))
    for (const field of COMMAND_FIELDS) {
      expect(form[field.id]?.text).toBe(field.defaultTriggers.join('\n'))
      expect(form[field.id]?.enabled).toBe(true)
    }
  })

  it('preserves an intentionally empty trigger list instead of resetting to defaults', () => {
    // 回归测试：管理员禁用某条命令并清空其触发词（避免与别的命令冲突）后，
    // 表单不应把它渲染回出厂默认值——那样下次保存会把清空的触发词又写回去
    // （见 issue：Preserve intentionally empty trigger lists）。
    const status = COMMAND_FIELDS[0]!
    const form = buildForm(
      baseSettings({ [status.id]: { enabled: false, triggers: [] } }),
    )
    expect(form[status.id]).toEqual({ enabled: false, text: '' })
  })

  it('keeps a customized non-empty trigger list as-is', () => {
    const status = COMMAND_FIELDS[0]!
    const form = buildForm(
      baseSettings({ [status.id]: { enabled: true, triggers: ['自定义'] } }),
    )
    expect(form[status.id]).toEqual({ enabled: true, text: '自定义' })
  })
})
