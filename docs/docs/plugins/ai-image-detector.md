---
sidebar_position: 11
---

# AI 图片检测

自 **v3.2.0** 起提供。容器部署可升级到 `v3.2.0` 或后续版本；配置 OpenAI 密钥后才会执行外部检测。

在 OneBot V11 群聊或私聊中，**引用一条只包含一张图片的消息**，回复：

```text
ai吗？
```

支持大小写 `AI`、中文或英文问号，也可省略问号。不需要 `/` 前缀；触发词固定，不受命令别名配置影响。群或好友必须已允许处理入站消息。当前不支持官方 QQ Bot 的引用图片。

机器人回复会引用**原始图片消息**，让检测结果与对应图片关联。检测失败或繁忙提示同样引用原消息；若用户未引用任何消息，操作提示会引用用户的 `ai吗？` 命令消息。

## 配置与数据流

1. 打开 Web Admin → **系统 → 高级配置 → AI 图片检测**。
2. 填入 OpenAI API Key 并保存；留空保存保留原密钥，点击“清除检测密钥”才删除。
3. 用户触发后，机器人下载 QQ CDN 提供的图片原始字节，先做本地 C2PA 检查。
4. 配置密钥后，同一图片还会上传 `https://api.openai.com/v1/content_provenance_checks`，一次返回 OpenAI C2PA 和 SynthID 的结果。

OpenAI 请求与 X API 共用 **X → 账号与代理** 的出站代理配置，支持 HTTP、HTTPS 和 SOCKS5；配置保存后，后续检测立即使用最新设置。关闭该配置时仍遵循进程环境中的代理变量。若服务器无法直连 OpenAI，请在此配置可用的出口代理；QQ 图片下载和本地 C2PA 不受这项配置影响。

密钥通过现有 `WEB_SECRET_KEY` 加密存入数据库。设置接口只返回是否配置，不返回原值或预览。没有密钥时仅执行本地 C2PA，回复会明确标注 OpenAI C2PA / SynthID 未完成检测。接口无权限、限流或失败时保留本地结果，不把失败写成“未检出”。

图片不在本地持久化，下载后不重新编码，以保留仍存在的凭证。配置密钥意味着此命令会向 OpenAI 上传图片；本地 C2PA 检查不会自动请求图片中声明的远程凭证地址、OCSP 或信任列表。

## 如何读结果

- **本地 C2PA 已检出**只说明存在凭证，不说明使用 AI。插件检查当前凭证及其引用的素材链中的标准 AI 生成 / 合成声明。
- **有效但来源未受信任**：签名和内容绑定校验通过，但尚不能确认签发者可信，不据此下确定结论。
- **校验失败**：元数据或内容可能被修改，不能采信其中声明。
- **OpenAI C2PA**：报告是否识别到 OpenAI AI 生成凭证及签名状态；可同时显示签发者。
- **SynthID（OpenAI）**：报告 OpenAI 接口识别到的受支持水印。它不检测所有厂商的水印。
- 来源受信任的 AI 声明或检出的 SynthID 可以作为 AI 生成 / 编辑证据；其余情况保留不确定性。**未检出不代表非 AI**。

QQ 压缩、截图、转存、裁剪和格式转换可能删除 C2PA 或削弱水印。检测的是协议端实际提供的文件，尽量使用未压缩原图。不要从结果推断作者身份、账号或提示词。

## 文件与请求限制

- 支持 PNG、JPEG、WebP、GIF；每次一张，最多 **20 MiB、2500 万像素**。
- 多图引用会要求重新引用单张，不会静默挑选其中一张。
- 仅访问 `*.qpic.cn`、`multimedia.nt.qq.com` 和 QQNT 使用的 `multimedia.nt.qq.com.cn` 的 HTTPS 地址，不接受任意 URL、本地路径或重定向。QQNT 主机名按完整名称匹配，不放行其他相似域名。
- 每个机器人进程同时处理一条检测请求；忙时提示稍后重试。下载超时 30 秒，OpenAI 请求超时 45 秒。
- 一次命令至多发送一次 OpenAI 请求，不自动重试、轮询或批量上传。
- 无法读取、地址过期、接口未配置、无权限或限流均作为失败 / 未完成状态报告。

## 接口费用与其他来源

以下为 **2026-11-03** 官方页面调研结果，价格以供应商实际报价为准：

| 服务 | 能力与范围 | 公开费用 |
| --- | --- | --- |
| 本地 c2pa-python | 读取不同厂商的嵌入式 C2PA；无法从像素中检测 SynthID | 无 API 调用费用，使用本机资源 |
| [OpenAI Content Provenance](https://developers.openai.com/api/docs/guides/content-provenance) | 本插件已接入；一次检查 OpenAI 支持的 C2PA 和 SynthID 信号 | 指南与[价格页](https://developers.openai.com/api/docs/pricing)尚未列出该接口价格，不能据此承诺免费 |
| [Sightengine](https://sightengine.com/pricing) | 对多个来源做 AI 图片概率分类；不代替 SynthID 验证 | Starter 29 美元/月含 10,000 operations，超额 0.002 美元/operation。仅使用 genai 检测静态单帧图时每张 5 operations，即套餐约 2,000 张，超额约 0.01 美元/张 |
| [Hive / Deploy](https://deploy.com/pricing) | AI 图片与 Deepfake 分类 | 当前实际价格页要求联系销售，无可确认的公开单价 |
| [Google AI Content Detection](https://docs.cloud.google.com/gemini-enterprise-agent-platform/models/ai-content-detection) | Google 与第三方图片的概率分类，不包含 C2PA；官方文档标为 Private Preview，需申请 | 该文档未公布价格；不是可直接开通的通用 SynthID 验证 API |

Sightengine 的计算依据为其[模型计费说明](https://sightengine.com/faq/what-is-an-operation)。GIF、视频或组合多个模型可能消耗更多 operations。它也提供免费测试方案；具体配额与适用范围以账号方案为准。

Google 的 [SynthID Detector 网站](https://deepmind.google/models/synthid/)支持多个合作方，但网页能力不能视为本插件已有可用、公开计费的 API。其他服务本次仅调研，暂不接入。
