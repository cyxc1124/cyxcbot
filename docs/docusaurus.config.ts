import {themes as prismThemes} from 'prism-react-renderer';
import type {Config} from '@docusaurus/types';
import type * as Preset from '@docusaurus/preset-classic';

const config: Config = {
  title: '机器草',
  tagline: 'B 站动态、直播监控与群消息推送的 QQ 机器人',
  favicon: 'img/favicon.svg',

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
          editUrl: 'https://github.com/cyxc1124/cyxcbot/tree/main/docs/',
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
        src: 'img/favicon.svg',
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
      style: 'dark',
      links: [
        {
          title: '文档',
          items: [
            {label: '快速开始', to: '/docs/getting-started/quick-start'},
            {label: '环境变量', to: '/docs/configuration/env-vars'},
            {label: 'Web Admin', to: '/docs/web-admin/overview'},
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
      copyright: `Copyright © ${new Date().getFullYear()} cyxc1124. Built with Docusaurus.`,
    },
    prism: {
      theme: prismThemes.github,
      darkTheme: prismThemes.dracula,
      additionalLanguages: ['bash', 'powershell', 'json'],
    },
  } satisfies Preset.ThemeConfig,
};

export default config;
