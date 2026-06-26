import type {ReactNode} from 'react';
import clsx from 'clsx';
import Link from '@docusaurus/Link';
import useDocusaurusContext from '@docusaurus/useDocusaurusContext';
import Layout from '@theme/Layout';
import HomepageFeatures from '@site/src/components/HomepageFeatures';
import Heading from '@theme/Heading';

import styles from './index.module.css';

function HomepageHeader() {
  const {siteConfig} = useDocusaurusContext();
  return (
    <header className={clsx(styles.heroBanner)}>
      <div className={clsx('container', styles.heroInner)}>
        <div className={styles.logoWrap}>
          <img
            src={`${siteConfig.baseUrl}img/favicon.svg`}
            alt=""
            className={styles.logo}
            width={72}
            height={69}
          />
        </div>
        <Heading as="h1" className={styles.heroTitle}>
          {siteConfig.title}
        </Heading>
        <p className={styles.heroSubtitle}>{siteConfig.tagline}</p>
        <div className={styles.buttons}>
          <Link className={styles.btnPrimary} to="/docs/intro">
            阅读文档
          </Link>
          <Link
            className={styles.btnGhost}
            href="https://github.com/cyxc1124/cyxcbot">
            GitHub
          </Link>
        </div>
      </div>
    </header>
  );
}

export default function Home(): ReactNode {
  const {siteConfig} = useDocusaurusContext();
  return (
    <Layout
      title={siteConfig.title}
      description="机器草 cyxcbot 官方文档：B 站动态、直播监控与群消息推送的 QQ 机器人">
      <HomepageHeader />
      <main>
        <HomepageFeatures />
      </main>
    </Layout>
  );
}
