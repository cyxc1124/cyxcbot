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
}

const SidebarContext = createContext<SidebarContextValue | null>(null)

export function SidebarProvider({ children }: { children: ReactNode }) {
  const [navCollapsed, setNavCollapsedState] = useState(false)

  const setNavCollapsed = useCallback((collapsed: boolean) => {
    setNavCollapsedState(collapsed)
  }, [])

  const value = useMemo(
    () => ({ navCollapsed, setNavCollapsed }),
    [navCollapsed, setNavCollapsed],
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
