<div align="center">

<img src="overlay/assets/logo.png" width="128" alt="DramaFetch">

# DramaFetch

**Windows 短剧下载器 · 多线程下载 · 自动更新**

[![Release](https://img.shields.io/github/v/release/Adamcssy19/DramaFetch?style=flat-square&label=最新版本)](https://github.com/Adamcssy19/DramaFetch/releases/latest)
[![Downloads](https://img.shields.io/github/downloads/Adamcssy19/DramaFetch/total?style=flat-square&label=累计下载)](https://github.com/Adamcssy19/DramaFetch/releases)
[![Platform](https://img.shields.io/badge/平台-Windows%2010%20%2F%2011%20x64-0078D4?style=flat-square)](#安装)
[![Build](https://img.shields.io/github/actions/workflow/status/Adamcssy19/DramaFetch/build-windows.yml?style=flat-square&label=构建)](https://github.com/Adamcssy19/DramaFetch/actions/workflows/build-windows.yml)

</div>

---

DramaFetch 是一个面向 Windows 的短剧下载工具：输入剧名、剧集编号或播放页链接就能找到剧集，按集批量下载，直接得到可播放的原画视频文件，不需要二次转码，也不带水印。

界面按 Windows 11 的设计语言重做：系统圆角、层色与控件规格对齐系统，搜索框采用深色描边风格，聚焦时带青色光晕。

## 功能

| 分类 | 能力 |
| --- | --- |
| **搜索** | 支持剧名搜索；直接粘贴剧集编号或播放页链接也能打开对应剧集 |
| **最近打开** | 只记录真正点开过的剧，点一下直接回到那部剧 |
| **选集** | 单集点选、全选 / 反选、前 N 集 / 后 N 集、区间语法（`1-50`、`1-10, 25, 30-45`） |
| **下载** | 多线程并发、失败重试、断点续传；先写临时文件，校验通过才落成正式文件 |
| **下载渠道** | 自动检测各渠道的可用性与延迟并选最快的，也可以手动指定，见 [下载渠道](#下载渠道) |
| **画质** | 自动优先高清，也可指定 1080P / 720P / 480P，源站没有对应清晰度时自动回退 |
| **播放** | 边下边看、连播、断点续播；本地已下载剧集可直接播放 |
| **更新** | 打开软件自动检查新版本，弹窗列出更新内容；安装包多线程分片下载 |
| **日志** | 运行日志写在本地，出问题可在 设置 → 查看运行日志 打开目录 |

## 安装

1. 打开 [Releases](https://github.com/Adamcssy19/DramaFetch/releases/latest)
2. 下载 `DramaFetch-x64-<版本号>-setup.exe`
3. 双击安装，安装向导会创建开始菜单与桌面快捷方式

> 系统要求：Windows 10 / 11 64 位。卸载通过系统「应用和功能」即可。
> 同一目录下的 `SHA256SUMS.txt` 可用于校验安装包完整性。

## 下载渠道

下载前会先探测各渠道的网络延迟，从最快的那个开始取流；失败自动换下一个。

| 渠道 | 说明 |
| --- | --- |
| 自动择优（默认） | 先测延迟挑最快的渠道，失败则回退到内置的多层兜底 |
| 应用接口 | 走应用接口取原画直链，画质最好；接口调整时可能失效 |
| 网页解析 | 解析播放页取流，部分剧集可能只允许试看 |
| 备用接口 | 前面都不可用时的兜底通道 |

## 自动更新

打开软件约两秒后会自动检查更新：先并发探测各加速源的延迟，选最快的一个再请求版本信息。发现新版本时弹窗列出更新内容，点「稍后」则改为主界面顶部的常驻提示。安装包按 4 段并发分片下载，内存占用保持在几百 KB。

仓库里**不保存上游源码**，由两套流程协作：

| 流程 | 触发 | 作用 |
| --- | --- | --- |
| `每日检查上游更新` | 每天 04:00 | 比对上游最新提交，有变化就自动提升修订号并触发构建 |
| `构建 Windows 安装包` | 推送 / 手动 | 现拉上游源码 → 应用本项目定制 → 编译 → 生成安装程序 → 发布 |

发布说明取自 [CHANGELOG.md](CHANGELOG.md) 里对应版本的一节，应用内的更新弹窗展示同样的内容（默认折叠，点开可看）。

## 项目结构

```
.
├── overlay/          # 覆盖到上游的定制文件（品牌、主题、界面、新增功能）
├── scripts/          # 拉取上游、应用定制、构建、打包、版本号
├── installer/        # Inno Setup 安装程序配置
├── .github/workflows # 上游跟进与构建发布流程
├── CHANGELOG.md      # 每个版本的更新内容，发布时自动引用
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
<summary>日志在哪里？</summary>

在 `%LocalAppData%\DramaFetch\logs\` 下，按天一个文件，里面有每个请求的动作与耗时、渠道探测结果、更新与下载的关键节点。设置里的「查看运行日志」可以直接打开该目录。
</details>

<details>
<summary>下载的画质和预期不一致？</summary>

下载设置里的画质是偏好，源站不提供对应清晰度时会自动回退，实际画质会显示在任务详情里。
</details>

<details>
<summary>检查更新连不上？</summary>

程序会自动挑延迟最低的加速源；如果全部不可达，可以在 设置 → 检查更新 里手动指定。
</details>

<details>
<summary>上游更新后我需要做什么？</summary>

不需要。定时流程会自动拉取上游、应用本项目定制并重新出包；也可以在 Actions 页面手动触发。
</details>

## 作者

[@Adamcssy19](https://github.com/Adamcssy19)

## 技术来源

站源解析与解密能力参考了以下开源项目，在此致谢（非本仓库贡献者）：

| 项目 | 说明 |
| --- | --- |
| [x315600/guoapp](https://github.com/x315600/guoapp) | 主上游，站源核心与下载实现 |
| [327044572/hongguo-downloader](https://github.com/327044572/hongguo-downloader) | 直连接口与 CENC-AES-CTR 解密实现（GPL-3.0） |
| [zhenyong97/hongguo-downloader](https://github.com/zhenyong97/hongguo-downloader) | 下载管理、并发、合并等交互设计（GPL-3.0） |

## 免责声明

本项目仅供学习交流与个人备份使用。所有短剧内容的版权归原平台及创作者所有，通过本工具获取的内容请勿用于传播、售卖或其他侵犯第三方权益的行为。工具按现状提供，不保证可用性；平台接口调整可能导致功能失效，请关注上游项目更新。

如权利人认为本项目侵犯其权益，请提 Issue 联系删除。
