import { useMemo, useState } from 'react'

export interface DualListSelectorLabels {
  emptyListMessage: string
  defaultHelperText: string
  availableSearchPlaceholder: string
  selectedSearchPlaceholder: string
  availablePanelTitle: string
  selectedPanelTitle: string
  noMatchMessage: string
  clickToAddHint: string
  allAddedMessage: string
}

interface DualListSelectorProps<T> {
  items: T[]
  selected: string[]
  onChange: (ids: string[]) => void
  getId: (item: T) => string
  getName: (item: T) => string | null
  labels: DualListSelectorLabels
  disabled?: boolean
  helperText?: string
}

type ItemLike = { id: string; name: string | null }

const PANEL_HEIGHT =
  'h-[clamp(10rem,35dvh,16rem)] sm:h-[clamp(12rem,42dvh,24rem)] lg:h-[clamp(14rem,48dvh,32rem)]'

export function DualListSelector<T>({
  items,
  selected,
  onChange,
  getId,
  getName,
  labels,
  disabled,
  helperText,
}: DualListSelectorProps<T>) {
  const [availableQuery, setAvailableQuery] = useState('')
  const [selectedQuery, setSelectedQuery] = useState('')
  const list = useMemo(() => (Array.isArray(items) ? items : []), [items])

  const itemMap = useMemo(() => {
    const map = new Map<string, T>()
    for (const item of list) {
      map.set(getId(item), item)
    }
    return map
  }, [list, getId])

  const available = useMemo(() => {
    const q = availableQuery.trim().toLowerCase()
    return list.filter((item) => {
      const id = getId(item)
      if (selected.includes(id)) return false
      if (!q) return true
      const name = (getName(item) ?? '').toLowerCase()
      return name.includes(q) || id.toLowerCase().includes(q)
    })
  }, [list, selected, availableQuery, getId, getName])

  const selectedItems = useMemo((): ItemLike[] => {
    return selected.map((id) => {
      const item = itemMap.get(id)
      return item
        ? { id, name: getName(item) }
        : { id, name: null }
    })
  }, [selected, itemMap, getName])

  const filteredSelectedItems = useMemo(() => {
    const q = selectedQuery.trim().toLowerCase()
    if (!q) return selectedItems
    return selectedItems.filter((item) => {
      const name = (item.name ?? '').toLowerCase()
      return name.includes(q) || item.id.toLowerCase().includes(q)
    })
  }, [selectedItems, selectedQuery])

  const addItem = (id: string) => {
    if (disabled || selected.includes(id)) return
    onChange([...selected, id])
  }

  const removeItem = (id: string) => {
    if (disabled) return
    onChange(selected.filter((itemId) => itemId !== id))
  }

  if (list.length === 0 && selected.length === 0) {
    return <p className="text-sm text-muted-foreground">{labels.emptyListMessage}</p>
  }

  return (
    <div className="space-y-2">
      <p className="text-xs text-muted-foreground">
        {helperText ?? labels.defaultHelperText}
        {selected.length > 0 && (
          <span className="ml-1 font-medium text-primary">
            （已选 {selected.length} 个）
          </span>
        )}
      </p>

      <div className="grid gap-4 sm:grid-cols-2">
        <div
          className={`flex flex-col overflow-hidden rounded-lg border border-border bg-card ${PANEL_HEIGHT}`}
        >
          <div className="border-b border-border p-2 border-border">
            <input
              type="search"
              className="input py-1.5 text-sm"
              placeholder={labels.availableSearchPlaceholder}
              value={availableQuery}
              disabled={disabled}
              onChange={(e) => setAvailableQuery(e.target.value)}
            />
          </div>
          <div className="flex items-center justify-between border-b border-border px-3 py-2 border-border">
            <span className="text-xs font-medium text-muted-foreground">
              {labels.availablePanelTitle}
            </span>
            <span className="text-xs text-muted-foreground">{available.length} 个</span>
          </div>
          <ul className="flex-1 overflow-y-auto p-1">
            {available.length === 0 ? (
              <li className="px-3 py-6 text-center text-sm text-muted-foreground">
                {availableQuery.trim() ? labels.noMatchMessage : labels.allAddedMessage}
              </li>
            ) : (
              available.map((item) => {
                const id = getId(item)
                const name = getName(item)
                return (
                  <li key={id}>
                    <button
                      type="button"
                      disabled={disabled}
                      onClick={() => addItem(id)}
                      className="flex w-full items-center gap-2 rounded-md px-3 py-2 text-left text-sm transition-colors hover:bg-accent disabled:cursor-not-allowed disabled:opacity-50 hover:bg-accent"
                    >
                      <span className="min-w-0 flex-1 truncate text-foreground">
                        {name ?? id}
                      </span>
                      {name && (
                        <span className="shrink-0 font-mono text-xs text-muted-foreground">
                          {id}
                        </span>
                      )}
                    </button>
                  </li>
                )
              })
            )}
          </ul>
        </div>

        <div
          className={`flex flex-col overflow-hidden rounded-lg border border-border bg-card ${PANEL_HEIGHT}`}
        >
          <div className="border-b border-border p-2 border-border">
            <input
              type="search"
              className="input py-1.5 text-sm"
              placeholder={labels.selectedSearchPlaceholder}
              value={selectedQuery}
              disabled={disabled}
              onChange={(e) => setSelectedQuery(e.target.value)}
            />
          </div>
          <div className="flex items-center justify-between border-b border-border px-3 py-2 border-border">
            <span className="text-xs font-medium text-muted-foreground">
              {labels.selectedPanelTitle}
            </span>
            <span className="text-xs text-muted-foreground">
              {selectedQuery.trim()
                ? `${filteredSelectedItems.length} / ${selectedItems.length} 个`
                : `${selectedItems.length} 个`}
            </span>
          </div>
          <ul className="flex-1 overflow-y-auto p-1">
            {selectedItems.length === 0 ? (
              <li className="px-3 py-6 text-center text-sm text-muted-foreground">
                {labels.clickToAddHint}
              </li>
            ) : filteredSelectedItems.length === 0 ? (
              <li className="px-3 py-6 text-center text-sm text-muted-foreground">
                {labels.noMatchMessage}
              </li>
            ) : (
              filteredSelectedItems.map((item) => (
                <li
                  key={item.id}
                  className="flex items-center gap-2 rounded-md px-2 py-1.5 hover:bg-muted hover:bg-accent/50"
                >
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm text-foreground">
                      {item.name ?? item.id}
                    </p>
                    {item.name && (
                      <p className="font-mono text-xs text-muted-foreground">{item.id}</p>
                    )}
                  </div>
                  <button
                    type="button"
                    disabled={disabled}
                    aria-label={`移除 ${item.name ?? item.id}`}
                    onClick={() => removeItem(item.id)}
                    className="flex h-7 w-7 shrink-0 items-center justify-center rounded-md text-muted-foreground transition-colors hover:bg-accent hover:text-foreground disabled:cursor-not-allowed disabled:opacity-50 hover:bg-accent hover:text-foreground"
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
