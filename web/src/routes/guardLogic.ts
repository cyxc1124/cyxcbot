export interface InitGuardState {
  initialized: boolean | null
  loading: boolean
  initError: string | null
}

/** 仅在后端明确返回未初始化时才跳转设置页 */
export function shouldRedirectToSetup({
  initialized,
  loading,
  initError,
}: InitGuardState): boolean {
  if (loading || initError) return false
  return initialized === false
}

/** 设置页仅在后端明确返回未初始化时允许访问 */
export function shouldAllowSetupRoute({
  initialized,
  loading,
  initError,
}: InitGuardState): boolean {
  if (loading || initError) return false
  return initialized === false
}

/** 已初始化实例应离开设置页 */
export function shouldLeaveSetupRoute({
  initialized,
  loading,
  initError,
}: InitGuardState): boolean {
  if (loading || initError) return false
  return initialized === true
}
