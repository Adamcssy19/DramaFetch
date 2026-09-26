# DramaFetch

Windows 短剧下载器。搜索红果短剧的剧集，选集后批量下载为本地 MP4 文件。

基于 [Ghost-Downloader-3](https://github.com/XiaoYouChR/Ghost-Downloader-3) 的下载内核（多线程分块、断点续传、限速），叠加 `drama_pack` 短剧特性包实现，并裁剪了原软件中与短剧下载无关的功能（BT / eD2k / FTP / GitHub / HuggingFace / YouTube / Bilibili / 浏览器扩展 / 安卓端）。

## 功能

- **搜索**：按关键词搜索红果短剧，返回剧名、封面、集数与简介
- **分类浏览**：按分类翻页浏览全站短剧
- **选集下载**：支持区间语法（`1-50`、`1-10, 25, 30-45`、`-20` 前 20 集、`20-` 第 20 集起）
- **多线程下载**：继承 Ghost 内核的分块多线程下载与断点续传
- **落盘结构**：每部剧保存为 `剧名/第001集.mp4` 的子目录结构

## 数据来源与版权

剧集信息与视频流来自红果短剧网页端（hongguoduanju.com）的公开页面接口，视频为平台明文提供的 MP4 直链，本项目不做任何解密或破解。

本项目仅用于个人学习与技术交流，短剧内容的版权归原平台及版权方所有，请勿用于商业用途或二次分发。

## 使用

1. 从 [Releases](https://github.com/Adamcssy19/DramaFetch/releases) 下载 `DramaFetch-vX.X.X-x64-Setup.exe` 安装，或下载 zip 免安装版
2. 打开软件，左侧进入「短剧」页
3. 搜索或浏览找到想看的剧，点「下载」
4. 在选集对话框填写范围（如 `1-80` 或 `all`），选好输出目录，开始下载

支持 `drama://hongguo/<剧ID>?name=剧名&eps=1,2,3` 协议链接唤起创建任务。

## 构建

依赖 [uv](https://docs.astral.sh/uv/) 与 Python 3.13。直接运行：

```bash
uv sync
uv run python DramaFetch.py
```

Windows 安装包由 GitHub Actions 在推送 `v*` 标签时自动构建（Nuitka 编译 + Inno Setup 打包），产物为 `DramaFetch-v<版本>-x64-Setup.exe` 与 zip 便携版。

## 许可证

本项目基于 [Ghost-Downloader-3](https://github.com/XiaoYouChR/Ghost-Downloader-3)（GPL-3.0 许可证）修改而来，依据 GPL-3.0 要求同样以 [GPL-3.0](LICENSE) 开源。

Copyright (C) 2026 Adamcssy19
