import type { ReactNode } from 'react'
import { AppBrand, AppFooter } from './AppBrand'
import { ThemeModeSwitch } from './ThemeModeSwitch'

export function AuthShell({ subtitle, children }: { subtitle: string; children: ReactNode }) {
  return (
    <div className="flex min-h-dvh flex-col bg-background">
      <header className="flex shrink-0 justify-end px-4 py-4 sm:px-8">
        <ThemeModeSwitch />
      </header>
      <main className="flex flex-1 items-center justify-center px-4 py-8">
        <section className="card w-full max-w-lg px-7 py-10 sm:px-10 [&_.label]:text-base" aria-labelledby="auth-heading">
          <h1 id="auth-heading" className="sr-only">机器草 · {subtitle}</h1>
          <div className="mb-8"><AppBrand subtitle={subtitle} /></div>
          {children}
        </section>
      </main>
      <AppFooter />
    </div>
  )
}
