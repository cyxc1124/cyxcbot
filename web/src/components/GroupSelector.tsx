import type { Group } from '../api/types'
import { DualListSelector } from './DualListSelector'

interface GroupSelectorProps {
  groups: Group[]
  selected: string[]
  onChange: (ids: string[]) => void
  disabled?: boolean
  helperText?: string
}

const GROUP_LABELS = {
  emptyListMessage: '暂无可用群组，请确保机器人已连接 OneBot 并在线。',
  defaultHelperText: '点击左侧群组添加到推送列表',
  availableSearchPlaceholder: '搜索群名或群号',
  selectedSearchPlaceholder: '搜索已选群名或群号',
  availablePanelTitle: '可选群组',
  selectedPanelTitle: '已选群组',
  noMatchMessage: '没有匹配的群组',
  clickToAddHint: '点击左侧群组添加',
  allAddedMessage: '已全部添加',
} as const

export function GroupSelector({ groups, selected, onChange, disabled, helperText }: GroupSelectorProps) {
  return (
    <DualListSelector
      items={groups}
      selected={selected}
      onChange={onChange}
      getId={(group) => group.group_id}
      getName={(group) => group.group_name}
      labels={GROUP_LABELS}
      disabled={disabled}
      helperText={helperText}
    />
  )
}
