import { Link, useSearchParams } from 'react-router-dom'
import { LinkParserGroupPolicyTab, LinkParserUserPolicyTab } from '../components/LinkParserPolicyTabs'
import { DouyinLinkParserGroupPolicyTab, DouyinLinkParserUserPolicyTab } from '../components/DouyinLinkParserPolicyTabs'
import { XLinkParserGroupPolicyTab, XLinkParserUserPolicyTab } from '../components/XLinkParserPolicyTabs'
import { SubPageTabs } from '../components/SubPageTabs'
import { templateCategoryLabels, type TemplateCategory } from '../constants/messageTemplates'

const policies = {
  bilibili: { groups: LinkParserGroupPolicyTab, friends: LinkParserUserPolicyTab },
  x: { groups: XLinkParserGroupPolicyTab, friends: XLinkParserUserPolicyTab },
  douyin: { groups: DouyinLinkParserGroupPolicyTab, friends: DouyinLinkParserUserPolicyTab },
}

export function LinkParserPage({ platform }: { platform: TemplateCategory }) {
  const [searchParams, setSearchParams] = useSearchParams()
  const scope = searchParams.get('scope') === 'friends' ? 'friends' : 'groups'
  const Policy = policies[platform][scope]

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold text-foreground">{templateCategoryLabels[platform]}链接解析</h2>
        <p className="mt-1 text-sm text-muted-foreground">按群组或好友管理解析策略，与会话页使用同一份配置。消息响应权限不影响主动订阅推送。</p>
        <div className="mt-3 flex flex-wrap gap-x-5 gap-y-2 text-sm text-primary">
          <Link to={`/${platform}/account`} className="hover:underline">{platform === 'x' ? '账号与代理' : '账号'}</Link>
          <Link to={`/${platform}/templates`} className="hover:underline">消息模板</Link>
          <Link to={scope === 'groups' ? '/groups' : '/friends'} className="hover:underline">{scope === 'groups' ? '群消息权限' : '好友消息权限'}</Link>
          <Link to="/system/advanced" className="hover:underline">共享媒体目录</Link>
        </div>
      </div>
      <SubPageTabs tabs={{ groups: '群组', friends: '好友' }} value={scope} onChange={(value) => {
        setSearchParams((current) => { current.set('scope', value); return current })
      }} />
      <div className="card"><Policy /></div>
    </div>
  )
}
