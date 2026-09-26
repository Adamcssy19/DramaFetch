<div align="center">

<img src="overlay/assets/logo.png" width="128" alt="DramaFetch">

# DramaFetch

**Windows 短剧下载器 · 原画直存 · 多方式下载 · 内置更新**

[![Release](https://img.shields.io/github/v/release/Adamcssy19/DramaFetch?style=flat-square&label=最新版本)](https://github.com/Adamcssy19/DramaFetch/releases/latest)
[![Downloads](https://img.shields.io/github/downloads/Adamcssy19/DramaFetch/total?style=flat-square&label=累计下载)](https://github.com/Adamcssy19/DramaFetch/releases)
[![Platform](https://img.shields.io/badge/平台-Windows%2010%20%2F%2011%20x64-0078D4?style=flat-square)](#安装)
[![Build](https://img.shields.io/github/actions/workflow/status/Adamcssy19/DramaFetch/build-windows.yml?style=flat-square&label=构建)](https://github.com/Adamcssy19/DramaFetch/actions/workflows/build-windows.yml)

</div>

---

DramaFetch 是一个面向 Windows 的短剧下载工具：浏览或粘贴链接找到剧集，按集批量下载，直接得到可播放的原画视频文件，不需要二次转码，也不带水印。

界面按照 Windows 11 的 Fluent 设计语言重做，采用 Mica 底色与系统强调色；下载完成后可以直接在应用内播放、合并或导出。

## 功能

| 分类 | 能力 |
| --- | --- |
| **发现** | 分类浏览、关键词搜索、榜单与推荐；支持粘贴分享链接、口令文本或剧集 ID 直接解析 |
| **选集** | 单集点选、全选 / 反选、前 N 集 / 后 N 集快捷选择、区间语法（`1-50`、`1-10, 25, 30-45`） |
| **下载** | 1～6 线程并发、失败重试、队列持久化、断点续传；先写临时文件，校验通过才落成正式文件 |
| **画质** | 自动优先高清，也可指定 1080P / 720P / 480P；指定不可用时自动回退到源站可用版本 |
| **下载方式** | 四种取流方式可选，见下方 [下载方式](#下载方式) |
| **播放** | 边下边看、连播、断点续播；本地已下载剧集可直接播放 |
| **导出** | 一键合并整部剧集、导出 Emby 元数据、按站源分类归档 |
| **更新** | 应用内检查新版本并直接下载安装，支持切换 GitHub 加速源 |

## 安装

1. 打开 [Releases](https://github.com/Adamcssy19/DramaFetch/releases/latest)
2. 下载 `DramaFetch-x64-<版本号>-setup.exe`
3. 双击安装，安装向导会创建开始菜单与桌面快捷方式

> 系统要求：Windows 10 / 11 64 位。卸载通过系统「应用和功能」即可。
> 同一目录下的 `SHA256SUMS.txt` 可用于校验安装包完整性。

## 下载方式

红果站源支持四种取流方式，在 **设置 → 网络与资源 → 红果下载方式** 中切换：

| 方式 | 说明 |
| --- | --- |
| 自动择优（默认） | 依次尝试下面三种，先成功就先使用 |
| App 直连 | 走红果 App 接口取原画直链，画质最好；接口调整时可能失效 |
| 网页解析 | 解析红果播放页取流，部分剧集可能只允许试看 |
| 备用接口 | App 与网页都不可用时的兜底通道 |

## 自动更新

项目由两套流程协作，仓库里**不保存上游源码**：

| 流程 | 触发 | 作用 |
| --- | --- | --- |
| `每日检查上游更新` | 每天 04:00 | 比对上游最新提交，有变化就自动提升修订号并触发构建 |
| `构建 Windows 安装包` | 推送 / 手动 | 现拉上游源码 → 应用本项目定制 → 编译 → 生成安装程序 → 发布 |

应用内更新：**设置 → 检查更新**。默认直连 GitHub，连接不畅时可切换 `ghfast.top`、`gh-proxy.com`、`ghproxy.net`、`gh.llkk.cc` 等加速源，检查与下载会同时走所选源。

## 项目结构

仓库只保留自己的东西，上游源码在构建时现拉：

```
.
├── overlay/          # 覆盖到上游的定制文件（品牌、主题、图标、新增功能）
├── scripts/          # 拉取上游、应用定制、构建、打包
├── installer/        # Inno Setup 安装程序配置
├── tools/            # 图标处理脚本
├── .github/workflows # 上游跟进与构建发布流程
├── version.txt       # 本项目版本号，不跟随上游
└── upstream.lock     # 上一次构建对应的上游提交
```

定制分两层应用，因此上游更新不会冲掉自己的改动：

- **覆盖**：`overlay/` 下的文件按相同路径覆盖到上游源码
- **定点替换**：`scripts/apply_custom.py` 里对上游文件的少量修改，用标记保证重复执行不会重复插入

## 开发与构建

```bash
# 拉取上游源码到 upstream/guoapp（不入库）
python scripts/fetch_upstream.py

# 应用本项目定制
python scripts/apply_custom.py

# 编译（需要 Flutter、Go、MinGW-w64）
python scripts/build_app.py

# 生成安装程序（需要 Inno Setup 6）
python scripts/build_installer.py
```

构建产物在 `dist/`。版本号改 `version.txt` 即可，格式为 `主版本.次版本.修订号+构建号`。

## 常见问题

<details>
<summary>安装后提示需要管理员权限？</summary>

应用采用多用户设计，默认账户即管理员。若切换到了受限用户，部分设置项（网络与资源、下载偏好等）不可修改，切回管理员即可。
</details>

<details>
<summary>下载的画质和预期不一致？</summary>

下载设置里的画质是偏好，源站不提供对应清晰度时会自动回退，实际画质会显示在任务详情里。
</details>

<details>
<summary>检查更新连不上？</summary>

切换一个加速源重试。加速源同时影响版本检查和安装包下载。
</details>

<details>
<summary>上游更新后我需要做什么？</summary>

不需要。定时流程会自动拉取上游、应用本项目定制并重新出包；你也可以在 Actions 页面手动触发。
</details>

## 参考的上游项目

本项目站源解析与解密能力来自以下开源项目，在此致谢：

| 项目 | 说明 |
| --- | --- |
| [x315600/guoapp](https://github.com/x315600/guoapp) | 主上游，多端短剧应用的站源核心与下载实现 |
| [327044572/hongguo-downloader](https://github.com/327044572/hongguo-downloader) | 红果直连接口与 CENC-AES-CTR 解密实现（GPL-3.0） |
| [zhenyong97/hongguo-downloader](https://github.com/zhenyong97/hongguo-downloader) | 下载管理、并发、合并与清理等交互设计（GPL-3.0） |

## 免责声明

本项目仅供学习交流与个人备份使用。所有短剧内容的版权归原平台及创作者所有，通过本工具获取的内容请勿用于传播、售卖或其他侵犯第三方权益的行为。工具按现状提供，不保证可用性；平台接口调整可能导致功能失效，请关注上游项目更新。

如权利人认为本项目侵犯其权益，请提 Issue 联系删除。
