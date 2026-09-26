# 更新日志

本项目基于 [Ghost-Downloader-3](https://github.com/XiaoYouChR/Ghost-Downloader-3) 修改，格式参考 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)。

## 0.0.1 - 2026-09-26

### 重构

- 以 Ghost-Downloader-3 v4.3.8 为底座重建项目，更名为 DramaFetch
- 新增 `drama_pack` 短剧特性包：
  - 红果短剧搜索 / 分类浏览 / 剧集详情 / 播放页直链解析（网页公开接口）
  - 区间选集语法：`all`、`1-50`、`1-10, 25, 30-45`、`-20`、`20-`
  - 按剧分集落盘：`剧名/第001集.mp4`
  - `drama://` 协议链接唤起创建任务

### 移除

- 特性包：Bilibili、BT（bittorrent）、eD2k、FTP、GitHub、HuggingFace、yt-dlp
- 浏览器扩展服务、安卓端、多语言翻译脚本
- 相关下载渠道的文件关联与协议注册（保留 m3u8/mpd）

### 变更

- 品牌、更新源、安装包命名、构建流水线全部切换至 DramaFetch（仅保留 Windows x64 构建）
- URL 协议由 `ghostdownloader://` 更换为 `dramafetch://`
- 数据目录由 `GhostDownloader` 更名为 `DramaFetch`
