<div align="center">

# DramaFetch

**短剧下载器 · 搜索 / 分类 / 排行榜 / 批量下载 1080p**

基于 Ghost-Downloader-3 下载内核与 Fluent 液态玻璃界面的 Windows 桌面客户端。

[![Release](https://img.shields.io/github/v/release/Adamcssy19/DramaFetch?style=flat-square)](https://github.com/Adamcssy19/DramaFetch/releases)
[![Platform](https://img.shields.io/badge/platform-Windows%2010%20%2F%2011%20x64-blue?style=flat-square)](https://github.com/Adamcssy19/DramaFetch/releases)
[![Python](https://img.shields.io/badge/python-3.13-3776AB?style=flat-square)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-GPL--3.0-orange?style=flat-square)](LICENSE)

[下载最新版](https://github.com/Adamcssy19/DramaFetch/releases) · [问题反馈](https://github.com/Adamcssy19/DramaFetch/issues)

</div>

## ✨ 特性

**发现**
- 关键词搜索、分类翻页浏览
- 四大榜单：果子热播榜 / 真人剧热播榜 / 漫剧热播榜 / AI 剧热播榜
- 网格卡片排版，窄窗口单列、宽窗口多列自适应

**下载**
- 区间选集语法：`1-50`、`1-10, 25, 30-45`、`-20`（前 20 集）、`20-`（第 20 集起）
- 多线程分块下载 + 断点续传 + AI 自动提速（Ghost 内核）
- 1080p 原画：自动解密 CENC 加密流并重建 MP4 索引，落盘即可播放
- 四条取流渠道自动逐级降级，单渠道失效不影响下载

| 优先级 | 渠道 | 画质 | 说明 |
|:---:|---|:---:|---|
| 1 | App 接口（请求签名） | 最高 1080p | CENC 加密流，下载完成后自动解密 |
| 2 | 官网播放页 | 720p | 明文 MP4 直链 |
| 3 | 备用解析接口 | 最高 1080p | 第三方解析服务 |
| 4 | 镜像站 | 720p | m3u8 分片流，需在设置中安装 N_m3u8DL-RE |

**体验**
- Fluent Design 液态玻璃卡片界面，支持 Mica / Acrylic 透明材质
- 自动更新 + 版本更新日志展示
- `drama://` 协议链接一键唤起创建任务
- 下载完成提示音（可开关）

## 📥 安装

到 [Releases](https://github.com/Adamcssy19/DramaFetch/releases) 下载：

| 文件 | 说明 |
|---|---|
| `DramaFetch-vX.X.X-x64-Setup.exe` | 安装版，双击安装 |
| `DramaFetch-vX.X.X-Windows-x64.zip` | 便携版，解压即用 |

## 📁 输出结构

```
下载目录/
└── DramaFetch/
    └── 剧名/
        ├── 剧名 001.mp4
        ├── 剧名 002.mp4
        └── ...
```

子文件夹与文件命名模板可在 **设置 → 综合下载设置** 中调整。

## 🛠️ 从源码运行

依赖 [uv](https://docs.astral.sh/uv/) 与 Python 3.13：

```bash
uv sync
uv run python DramaFetch.py
```

Windows 安装包由 GitHub Actions 在推送 `v*` 标签时自动构建（Nuitka 编译 + Inno Setup 打包）。

## 📄 声明与许可

- 本项目基于 [Ghost-Downloader-3](https://github.com/XiaoYouChR/Ghost-Downloader-3)（GPL-3.0）修改，依据 GPL-3.0 以[相同许可](LICENSE)开源
- 剧集内容版权归原平台及版权方所有，仅供个人学习与技术交流，请勿用于商业用途或二次分发
