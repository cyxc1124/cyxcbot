import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it, vi } from 'vitest'
import { ChoiceCardGroup } from './ChoiceCardGroup'

const options = [
  { value: 'image', label: '动态配图', description: '优先首张配图' },
  { value: 'avatar', label: '作者头像', description: '使用作者头像' },
] as const

describe('ChoiceCardGroup', () => {
  it('renders one native radio selection with an accessible group and descriptions', () => {
    const html = renderToStaticMarkup(<ChoiceCardGroup label="取色来源" value="avatar" options={options} onChange={vi.fn()} />)
    expect(html).toContain('<legend')
    expect(html).toContain('取色来源')
    expect(html.match(/type="radio"/g)).toHaveLength(2)
    expect(html.match(/checked=""/g)).toHaveLength(1)
    expect(html).toMatch(/checked="" value="avatar"/)
    expect(html).toContain('aria-describedby=')
    expect(html).toContain('peer-focus-visible:')
  })

  it('disables the entire group while saving', () => {
    const html = renderToStaticMarkup(<ChoiceCardGroup label="取色来源" value="image" options={options} disabled onChange={vi.fn()} />)
    expect(html).toContain('<fieldset disabled=""')
  })
})
