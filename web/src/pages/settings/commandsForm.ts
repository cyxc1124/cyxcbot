import type { Settings } from '../../api/types'
import {
  COMMAND_FIELDS,
  DEFAULT_EXTRA_PREFIXES,
  type CommandField,
  type CommandId,
} from '../../constants/commandAliases'

export type CommandFormValue = { enabled: boolean; text: string }
export type CommandForm = Partial<Record<CommandId, CommandFormValue>>

export function parseLines(text: string): string[] {
  return text
    .split('\n')
    .map((line) => line.trim())
    .filter((line) => line.length > 0)
}

export function buildForm(
  settings: Settings | null,
  fields: readonly CommandField[] = COMMAND_FIELDS,
): CommandForm {
  const result: CommandForm = {}
  for (const field of fields) {
    const entry = settings?.command_aliases?.[field.id]
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
