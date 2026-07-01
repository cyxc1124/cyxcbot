import type { Friend } from '../api/types'
import { DualListSelector } from './DualListSelector'

interface FriendSelectorProps {
  friends: Friend[]
  selected: string[]
  onChange: (ids: string[]) => void
  disabled?: boolean
  helperText?: string
}

const FRIEND_LABELS = {
  emptyListMessage: '暂无好友数据，请确保机器人已连接 OneBot 且协议端支持 get_friend_list。',
  defaultHelperText: '点击左侧好友添加到推送列表',
  availableSearchPlaceholder: '搜索昵称或 QQ 号',
  selectedSearchPlaceholder: '搜索已选昵称或 QQ 号',
  availablePanelTitle: '可选好友',
  selectedPanelTitle: '已选好友',
  noMatchMessage: '没有匹配的好友',
  clickToAddHint: '点击左侧好友添加',
  allAddedMessage: '已全部添加',
} as const

export function FriendSelector({
  friends,
  selected,
  onChange,
  disabled,
  helperText,
}: FriendSelectorProps) {
  return (
    <DualListSelector
      items={friends}
      selected={selected}
      onChange={onChange}
      getId={(friend) => friend.user_id}
      getName={(friend) => friend.nickname}
      labels={FRIEND_LABELS}
      disabled={disabled}
      helperText={helperText}
    />
  )
}
