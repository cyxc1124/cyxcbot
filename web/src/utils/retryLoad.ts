export function createRetryHandler(
  load: () => Promise<void>,
  setLoading: (value: boolean) => void,
): () => void {
  return () => {
    setLoading(true)
    void load()
  }
}
