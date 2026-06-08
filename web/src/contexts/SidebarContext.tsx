import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useState,
  type ReactNode,
} from 'react'

interface SidebarContextValue {
  navCollapsed: boolean
  setNavCollapsed: (collapsed: boolean) => void
  /** 当前页可收起导航（如订阅详情） */
  navCollapsible: boolean
  setNavCollapsible: (collapsible: boolean) => void
}

const SidebarContext = createContext<SidebarContextValue | null>(null)

export function SidebarProvider({ children }: { children: ReactNode }) {
  const [navCollapsed, setNavCollapsedState] = useState(false)
  const [navCollapsible, setNavCollapsibleState] = useState(false)

  const setNavCollapsed = useCallback((collapsed: boolean) => {
    setNavCollapsedState(collapsed)
  }, [])

  const setNavCollapsible = useCallback((collapsible: boolean) => {
    setNavCollapsibleState(collapsible)
  }, [])

  const value = useMemo(
    () => ({ navCollapsed, setNavCollapsed, navCollapsible, setNavCollapsible }),
    [navCollapsed, setNavCollapsed, navCollapsible, setNavCollapsible],
  )

  return <SidebarContext.Provider value={value}>{children}</SidebarContext.Provider>
}

export function useSidebar() {
  const ctx = useContext(SidebarContext)
  if (!ctx) {
    throw new Error('useSidebar must be used within SidebarProvider')
  }
  return ctx
}
