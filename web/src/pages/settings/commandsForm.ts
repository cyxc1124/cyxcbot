import type { Settings } from '../../api/types'
import {
  COMMAND_FIELDS,
  DEFAULT_EXTRA_PREFIXES,
  type CommandId,
} from '../../constants/commandAliases'

export type CommandFormValue = { enabled: boolean; text: string }
export type CommandForm = Record<CommandId, CommandFormValue>

export function parseLines(text: string): string[] {
  return text
    .split('\n')
    .map((line) => line.trim())
    .filter((line) => line.length > 0)
}

export function buildForm(settings: Settings | null): CommandForm {
  const result = {} as CommandForm
  for (const field of COMMAND_FIELDS) {
    const entry = settings?.command_aliases?.[field.id]
    // entry 存在时用其 triggers（可能是管理员故意清空的 []，需保留，不能回退成
    // 默认值），只有 entry 整条缺失时才用出厂默认值填充
    const triggers = entry ? entry.triggers : field.defaultTriggers
    result[field.id] = {
      enabled: entry?.enabled ?? true,
      text: triggers.join('\n'),
    }
  }
  return result
}

export function buildExtraPrefixesText(settings: Settings | null): string {
  return (settings?.command_extra_prefixes ?? DEFAULT_EXTRA_PREFIXES).join('\n')
}
