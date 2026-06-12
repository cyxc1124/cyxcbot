import type {ReactNode} from 'react';
import clsx from 'clsx';
import Heading from '@theme/Heading';
import styles from './styles.module.css';

type FeatureItem = {
  title: string;
  emoji: string;
  description: ReactNode;
};

const FeatureList: FeatureItem[] = [
  {
    title: 'B 站监控',
    emoji: '📺',
    description: (
      <>
        直播、动态、投稿三重监控，WebSocket + API 轮询双重机制，开播下播秒级推送。
      </>
    ),
  },
  {
    title: 'Web Admin',
    emoji: '🌐',
    description: (
      <>
        浏览器管理面板，监控映射、B 站账号、消息模板、权限策略一站式配置，无需改环境变量。
      </>
    ),
  },
  {
    title: '多平台部署',
    emoji: '📦',
    description: (
      <>
        支持 Docker、Windows 可执行包、Docker Compose 与 Kubernetes Helm，适配服务器与桌面环境。
      </>
    ),
  },
];

function Feature({title, emoji, description}: FeatureItem) {
  return (
    <div className={clsx('col col--4')}>
      <div className="text--center">
        <span className={styles.featureEmoji} role="img" aria-label={title}>
          {emoji}
        </span>
      </div>
      <div className="text--center padding-horiz--md">
        <Heading as="h3">{title}</Heading>
        <p>{description}</p>
      </div>
    </div>
  );
}

export default function HomepageFeatures(): ReactNode {
  return (
    <section className={styles.features}>
      <div className="container">
        <div className="row">
          {FeatureList.map((props, idx) => (
            <Feature key={idx} {...props} />
          ))}
        </div>
      </div>
    </section>
  );
}
