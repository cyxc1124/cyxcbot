import {themes as prismThemes} from 'prism-react-renderer';
import type {Config} from '@docusaurus/types';
import type * as Preset from '@docusaurus/preset-classic';

const config: Config = {
  title: '机器草',
  tagline: 'B 站动态与直播推送、X 推文监控、多平台链接解析，支持 OneBot 与官方 QQ\u00a0Bot，自带 Web 管理面板',
  favicon: 'img/brand-avatar.png',

  future: {
    v4: true,
  },

  url: 'https://cyxc1124.github.io',
  baseUrl: '/cyxcbot/',

  organizationName: 'cyxc1124',
  projectName: 'cyxcbot',

  onBrokenLinks: 'throw',

  i18n: {
    defaultLocale: 'zh-Hans',
    locales: ['zh-Hans'],
  },

  presets: [
    [
      'classic',
      {
        docs: {
          sidebarPath: './sidebars.ts',
          editUrl: 'https://github.com/cyxc1124/cyxcbot/tree/develop/docs/',
        },
        blog: false,
        theme: {
          customCss: './src/css/custom.css',
        },
      } satisfies Preset.Options,
    ],
  ],

  themeConfig: {
    colorMode: {
      respectPrefersColorScheme: true,
    },
    navbar: {
      title: '机器草',
      logo: {
        alt: '机器草',
        src: 'img/brand-avatar.png',
      },
      items: [
        {
          type: 'docSidebar',
          sidebarId: 'docsSidebar',
          position: 'left',
          label: '文档',
        },
        {
          href: 'https://github.com/cyxc1124/cyxcbot',
          label: 'GitHub',
          position: 'right',
        },
      ],
    },
    footer: {
      links: [
        {
          title: '文档',
          items: [
            {label: '快速开始', to: '/docs/getting-started/quick-start'},
            {label: '环境变量', to: '/docs/configuration/env-vars'},
            {label: 'Web Admin', to: '/docs/web-admin/overview'},
            {label: '插件', to: '/docs/category/插件'},
          ],
        },
        {
          title: '部署',
          items: [
            {label: 'Docker', to: '/docs/getting-started/docker'},
            {label: 'Docker Compose', to: '/docs/getting-started/docker-compose'},
            {label: 'Helm', to: '/docs/getting-started/helm'},
            {label: 'Windows', to: '/docs/getting-started/windows'},
          ],
        },
        {
          title: '相关链接',
          items: [
            {
              label: 'GitHub',
              href: 'https://github.com/cyxc1124/cyxcbot',
            },
            {
              label: 'NoneBot2',
              href: 'https://nonebot.dev/',
            },
          ],
        },
      ],
      copyright: `© ${new Date().getFullYear()} cyxc1124 · 机器草 cyxcbot`,
    },
    prism: {
      theme: prismThemes.oneLight,
      darkTheme: prismThemes.oneDark,
      additionalLanguages: ['bash', 'powershell', 'json', 'python', 'toml', 'yaml'],
    },
  } satisfies Preset.ThemeConfig,
};

export default config;
