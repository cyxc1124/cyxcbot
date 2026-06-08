import { useMemo, useState } from 'react'
import type { Friend } from '../api/types'

interface FriendSelectorProps {
  friends: Friend[]
  selected: string[]
  onChange: (ids: string[]) => void
  disabled?: boolean
  helperText?: string
}

type FriendLike = Pick<Friend, 'user_id' | 'nickname'>

const PANEL_HEIGHT =
  'h-[clamp(10rem,35dvh,16rem)] sm:h-[clamp(12rem,42dvh,24rem)] lg:h-[clamp(14rem,48dvh,32rem)]'

export function FriendSelector({
  friends,
  selected,
  onChange,
  disabled,
  helperText,
}: FriendSelectorProps) {
  const [availableQuery, setAvailableQuery] = useState('')
  const [selectedQuery, setSelectedQuery] = useState('')
  const list = Array.isArray(friends) ? friends : []

  const friendMap = useMemo(() => {
    const map = new Map<string, Friend>()
    for (const friend of list) {
      map.set(friend.user_id, friend)
    }
    return map
  }, [list])

  const available = useMemo(() => {
    const q = availableQuery.trim().toLowerCase()
    return list.filter((friend) => {
      if (selected.includes(friend.user_id)) return false
      if (!q) return true
      const name = (friend.nickname ?? '').toLowerCase()
      const id = friend.user_id.toLowerCase()
      return name.includes(q) || id.includes(q)
    })
  }, [list, selected, availableQuery])

  const selectedFriends = useMemo((): FriendLike[] => {
    return selected.map(
      (id) => friendMap.get(id) ?? { user_id: id, nickname: null },
    )
  }, [selected, friendMap])

  const filteredSelectedFriends = useMemo(() => {
    const q = selectedQuery.trim().toLowerCase()
    if (!q) return selectedFriends
    return selectedFriends.filter((friend) => {
      const name = (friend.nickname ?? '').toLowerCase()
      const id = friend.user_id.toLowerCase()
      return name.includes(q) || id.includes(q)
    })
  }, [selectedFriends, selectedQuery])

  const addFriend = (userId: string) => {
    if (disabled || selected.includes(userId)) return
    onChange([...selected, userId])
  }

  const removeFriend = (userId: string) => {
    if (disabled) return
    onChange(selected.filter((id) => id !== userId))
  }

  if (list.length === 0 && selected.length === 0) {
    return (
      <p className="text-sm text-slate-500">
        暂无好友数据，请确保机器人已连接 OneBot 且协议端支持 get_friend_list。
      </p>
    )
  }

  return (
    <div className="space-y-2">
      <p className="text-xs text-slate-500">
        {helperText ?? '点击左侧好友添加到推送列表'}
        {selected.length > 0 && (
          <span className="ml-1 font-medium text-brand-600 dark:text-brand-400">
            （已选 {selected.length} 个）
          </span>
        )}
      </p>

      <div className="grid gap-4 sm:grid-cols-2">
        <div
          className={`flex flex-col overflow-hidden rounded-lg border border-slate-200 bg-white dark:border-slate-700 dark:bg-slate-900 ${PANEL_HEIGHT}`}
        >
          <div className="border-b border-slate-200 p-2 dark:border-slate-700">
            <input
              type="search"
              className="input py-1.5 text-sm"
              placeholder="搜索昵称或 QQ 号"
              value={availableQuery}
              disabled={disabled}
              onChange={(e) => setAvailableQuery(e.target.value)}
            />
          </div>
          <div className="flex items-center justify-between border-b border-slate-100 px-3 py-2 dark:border-slate-800">
            <span className="text-xs font-medium text-slate-500">可选好友</span>
            <span className="text-xs text-slate-400">{available.length} 个</span>
          </div>
          <ul className="flex-1 overflow-y-auto p-1">
            {available.length === 0 ? (
              <li className="px-3 py-6 text-center text-sm text-slate-400">
                {availableQuery.trim() ? '没有匹配的好友' : '已全部添加'}
              </li>
            ) : (
              available.map((friend) => (
                <li key={friend.user_id}>
                  <button
                    type="button"
                    disabled={disabled}
                    onClick={() => addFriend(friend.user_id)}
                    className="flex w-full items-center gap-2 rounded-md px-3 py-2 text-left text-sm transition-colors hover:bg-slate-100 disabled:cursor-not-allowed disabled:opacity-50 dark:hover:bg-slate-800"
                  >
                    <span className="min-w-0 flex-1 truncate text-slate-900 dark:text-white">
                      {friend.nickname ?? friend.user_id}
                    </span>
                    {friend.nickname && (
                      <span className="shrink-0 font-mono text-xs text-slate-400">
                        {friend.user_id}
                      </span>
                    )}
                  </button>
                </li>
              ))
            )}
          </ul>
        </div>

        <div
          className={`flex flex-col overflow-hidden rounded-lg border border-slate-200 bg-white dark:border-slate-700 dark:bg-slate-900 ${PANEL_HEIGHT}`}
        >
          <div className="border-b border-slate-200 p-2 dark:border-slate-700">
            <input
              type="search"
              className="input py-1.5 text-sm"
              placeholder="搜索已选昵称或 QQ 号"
              value={selectedQuery}
              disabled={disabled}
              onChange={(e) => setSelectedQuery(e.target.value)}
            />
          </div>
          <div className="flex items-center justify-between border-b border-slate-100 px-3 py-2 dark:border-slate-800">
            <span className="text-xs font-medium text-slate-500">已选好友</span>
            <span className="text-xs text-slate-400">
              {selectedQuery.trim()
                ? `${filteredSelectedFriends.length} / ${selectedFriends.length} 个`
                : `${selectedFriends.length} 个`}
            </span>
          </div>
          <ul className="flex-1 overflow-y-auto p-1">
            {selectedFriends.length === 0 ? (
              <li className="px-3 py-6 text-center text-sm text-slate-400">
                点击左侧好友添加
              </li>
            ) : filteredSelectedFriends.length === 0 ? (
              <li className="px-3 py-6 text-center text-sm text-slate-400">
                没有匹配的好友
              </li>
            ) : (
              filteredSelectedFriends.map((friend) => (
                <li
                  key={friend.user_id}
                  className="flex items-center gap-2 rounded-md px-2 py-1.5 hover:bg-slate-50 dark:hover:bg-slate-800/50"
                >
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm text-slate-900 dark:text-white">
                      {friend.nickname ?? friend.user_id}
                    </p>
                    {friend.nickname && (
                      <p className="font-mono text-xs text-slate-400">{friend.user_id}</p>
                    )}
                  </div>
                  <button
                    type="button"
                    disabled={disabled}
                    aria-label={`移除 ${friend.nickname ?? friend.user_id}`}
                    onClick={() => removeFriend(friend.user_id)}
                    className="flex h-7 w-7 shrink-0 items-center justify-center rounded-md text-slate-400 transition-colors hover:bg-slate-200 hover:text-slate-700 disabled:cursor-not-allowed disabled:opacity-50 dark:hover:bg-slate-700 dark:hover:text-slate-200"
                  >
                    <span className="text-base leading-none" aria-hidden>
                      ×
                    </span>
                  </button>
                </li>
              ))
            )}
          </ul>
        </div>
      </div>
    </div>
  )
}
