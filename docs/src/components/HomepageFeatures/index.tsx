import type {ReactNode, SVGProps} from 'react';
import clsx from 'clsx';
import Link from '@docusaurus/Link';
import Heading from '@theme/Heading';
import styles from './styles.module.css';

type FeatureItem = {
  title: string;
  description: ReactNode;
  Icon: (props: SVGProps<SVGSVGElement>) => ReactNode;
};

type QuickLink = {
  title: string;
  description: string;
  to: string;
};

const FeatureList: FeatureItem[] = [
  {
    title: 'B 站监控',
    Icon: IconMonitor,
    description: (
      <>
        直播、动态、投稿三重监控，WebSocket + API 轮询双重机制，开播下播秒级推送。
      </>
    ),
  },
  {
    title: 'Web Admin',
    Icon: IconPanel,
    description: (
      <>
        浏览器管理面板，监控映射、B 站账号、消息模板、权限策略一站式配置，无需改环境变量。
      </>
    ),
  },
  {
    title: '多平台部署',
    Icon: IconDeploy,
    description: (
      <>
        支持 Docker、Windows 可执行包、Docker Compose 与 Kubernetes Helm，适配服务器与桌面环境。
      </>
    ),
  },
];

const QuickLinks: QuickLink[] = [
  {
    title: '快速开始',
    description: '本地开发、Docker 与 Windows 部署',
    to: '/docs/getting-started/quick-start',
  },
  {
    title: '环境变量',
    description: '启动级配置说明',
    to: '/docs/configuration/env-vars',
  },
  {
    title: 'Web Admin',
    description: '管理面板功能概览',
    to: '/docs/web-admin/overview',
  },
  {
    title: '插件文档',
    description: '直播、动态、链接解析等',
    to: '/docs/plugins/dynamic-monitor',
  },
];

function IconMonitor(props: SVGProps<SVGSVGElement>) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" {...props}>
      <rect x="2" y="4" width="20" height="14" rx="2" />
      <path d="M8 20h8M12 18v2" strokeLinecap="round" />
      <path d="M7 9l3 3 7-7" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

function IconPanel(props: SVGProps<SVGSVGElement>) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" {...props}>
      <rect x="3" y="3" width="18" height="18" rx="2" />
      <path d="M3 9h18M9 9v12" strokeLinecap="round" />
      <circle cx="15" cy="14" r="2" />
    </svg>
  );
}

function IconDeploy(props: SVGProps<SVGSVGElement>) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" {...props}>
      <path d="M12 3l8 4.5v9L12 21l-8-4.5v-9L12 3z" strokeLinejoin="round" />
      <path d="M12 12l8-4.5M12 12v9M12 12L4 7.5" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

function IconArrow(props: SVGProps<SVGSVGElement>) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" {...props}>
      <path d="M5 12h14M13 6l6 6-6 6" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

function Feature({title, Icon, description}: FeatureItem) {
  return (
    <div className={clsx('col col--4', styles.featureCol)}>
      <div className={styles.featureCard}>
        <div className={styles.featureIconWrap}>
          <Icon className={styles.featureIcon} aria-hidden />
        </div>
        <Heading as="h3" className={styles.featureTitle}>
          {title}
        </Heading>
        <p className={styles.featureDesc}>{description}</p>
      </div>
    </div>
  );
}

function QuickLinkCard({title, description, to}: QuickLink) {
  return (
    <Link to={to} className={styles.quickLink}>
      <div>
        <div className={styles.quickLinkTitle}>{title}</div>
        <div className={styles.quickLinkDesc}>{description}</div>
      </div>
      <IconArrow className={styles.quickLinkArrow} aria-hidden />
    </Link>
  );
}

export default function HomepageFeatures(): ReactNode {
  return (
    <>
      <section className={styles.features}>
        <div className="container">
          <div className="row">
            {FeatureList.map((props, idx) => (
              <Feature key={idx} {...props} />
            ))}
          </div>
        </div>
      </section>

      <section className={styles.quickLinks}>
        <div className="container">
          <Heading as="h2" className={styles.sectionTitle}>
            快速导航
          </Heading>
          <div className={styles.quickLinkGrid}>
            {QuickLinks.map((link) => (
              <QuickLinkCard key={link.to} {...link} />
            ))}
          </div>
        </div>
      </section>
    </>
  );
}
