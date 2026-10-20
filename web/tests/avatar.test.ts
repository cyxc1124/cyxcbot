import { readFileSync } from 'node:fs'
import { expect, it } from 'vitest'

it('keeps the shared avatar small enough to load quickly at three-times display density', () => {
  const avatar = readFileSync(new URL('../public/brand-avatar.png', import.meta.url))
  expect(avatar.byteLength).toBeLessThan(100 * 1024)
  expect(avatar.readUInt32BE(16)).toBeGreaterThanOrEqual(72 * 3)
  expect(avatar.readUInt32BE(20)).toBeGreaterThanOrEqual(72 * 3)
})
