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
  it('keeps cached official rows editable beside incomplete numeric rows', () => {
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
        savingIds={new Set()}
        togglingAll={false}
        editable={false}
        onPatch={() => {}}
        onReset={() => {}}
      />,
    )
    expect(html).toContain('官方 QQ')
    expect(html).toContain('OneBot · 只读')
    expect(html).toContain('official 视频链接')
    expect(html.match(/disabled=""/g)).toHaveLength(5)
  })

  it('keeps unavailable rows readonly when older APIs omit row metadata', () => {
    const html = renderToStaticMarkup(
      <LinkParserPolicyTable
        items={[{ ...flags, id: '1001' }]}
        getItemId={(item) => item.id}
        getDisplayName={() => null}
        idColumnLabel="ID"
        nameColumnLabel="名称"
        savingIds={new Set()}
        togglingAll={false}
        editable={false}
        onPatch={() => {}}
        onReset={() => {}}
      />,
    )
    expect(html.match(/disabled=""/g)).toHaveLength(5)
  })
})
