/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_BUILD_VERSION: string
  readonly VITE_GIT_BRANCH: string | null
  readonly VITE_BUILD_TIME: string | null
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
