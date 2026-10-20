import { useState, type FormEvent } from 'react'
import { Link } from 'react-router-dom'
import { useSettingsForm } from './SettingsContext'

export function SettingsAdvancedPage() {
  const { settings, formDisabled, saving, savePartial } = useSettingsForm()
  const [directory, setDirectory] = useState(settings?.link_parser_shared_media_dir ?? '')
  const [syncedSettings, setSyncedSettings] = useState(settings)

  if (settings !== syncedSettings) {
    setSyncedSettings(settings)
    if (settings) setDirectory(settings.link_parser_shared_media_dir ?? '')
  }

  const handleSubmit = (event: FormEvent) => {
    event.preventDefault()
    void savePartial({ link_parser_shared_media_dir: directory.trim() })
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-6">
      <div className="card space-y-4">
        <div>
          <h3 className="font-semibold text-foreground">链接解析共享媒体目录</h3>
          <p className="mt-1 text-sm text-muted-foreground">
            B 站、抖音和 X 链接解析下载的媒体写入此目录。通过 OneBot 发送时，以{' '}
            <code className="font-mono text-xs">file://</code>{' '}
            交给协议端读取。分离部署时请把机器草与协议端 / QQ 数据目录挂到同一路径。留空则使用平台默认。
          </p>
        </div>
        <div>
          <label className="label" htmlFor="link_parser_shared_media_dir">目录路径</label>
          <input id="link_parser_shared_media_dir" className="input font-mono text-sm"
            placeholder={settings?.link_parser_shared_media_dir_default || 'data/tmp'} value={directory}
            disabled={formDisabled || saving} onChange={(event) => setDirectory(event.target.value)} />
          <p className="mt-2 break-words text-xs text-muted-foreground">
            当前生效：<code className="font-mono">{settings?.link_parser_shared_media_dir_resolved || settings?.link_parser_shared_media_dir_default || '—'}</code>。
            默认 <code className="font-mono">data/tmp</code>。与协议端（如 LLBot）共用 QQ 数据持久化目录时，请设为{' '}
            <code className="font-mono">/root/.config/QQ/tmp</code>（卷挂 QQ 数据根即可）。
          </p>
        </div>
        <div className="flex flex-wrap gap-4 text-sm text-primary">
          <Link to="/bilibili/parser" className="hover:underline">B 站链接解析</Link>
          <Link to="/x/parser" className="hover:underline">X 链接解析</Link>
          <Link to="/douyin/parser" className="hover:underline">抖音链接解析</Link>
        </div>
      </div>
      <button type="submit" className="btn-primary" disabled={saving || formDisabled}>{saving ? '保存中…' : '保存设置'}</button>
    </form>
  )
}
