import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'
import { LinkParserPolicyTable } from './LinkParserPolicyTable'

const flags = {
  customized: true,
  video_enabled: true,
  live_enabled: false,
  dynamic_enabled: false,
  send_video_enabled: false,
}

describe('Bilibili policy row access', () => {
  it.each([false, true])('keeps official row saving=%s visually distinct from readonly numeric rows', (saving) => {
    const html = renderToStaticMarkup(
      <LinkParserPolicyTable
        items={[
          { ...flags, id: 'official', source: 'official' as const, editable: true },
          { ...flags, id: '1001', source: 'onebot' as const, editable: false },
        ]}
        getItemId={(item) => item.id}
        getDisplayName={() => null}
        idColumnLabel="ID"
        nameColumnLabel="名称"
        savingIds={new Set(saving ? ['official'] : [])}
        togglingAll={false}
        editable={false}
        onPatch={() => {}}
        onReset={() => {}}
      />,
    )
    expect(html).toContain('官方 QQ')
    expect(html).toContain('OneBot · 只读')
    expect(html).toContain('official 视频链接')
    expect(html.match(/disabled=""/g)).toHaveLength(saving ? 10 : 5)
    expect(html.match(/opacity-50/g)).toHaveLength(4)
    expect(html).not.toContain('保存中')
  })

  it.each([false, true])('keeps unavailable rows readonly with bulk saving=%s when older APIs omit row metadata', (togglingAll) => {
    const html = renderToStaticMarkup(
      <LinkParserPolicyTable
        items={[{ ...flags, id: '1001' }]}
        getItemId={(item) => item.id}
        getDisplayName={() => null}
        idColumnLabel="ID"
        nameColumnLabel="名称"
        savingIds={new Set()}
        togglingAll={togglingAll}
        editable={false}
        onPatch={() => {}}
        onReset={() => {}}
      />,
    )
    expect(html).toContain('OneBot · 只读')
    expect(html.match(/disabled=""/g)).toHaveLength(5)
  })
})
