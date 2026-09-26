package core

// 本项目新增：让用户选择红果的取流方式。
//
// 上游对红果本身已经做了三层回退（App 接口 → 网页解析 → 备用接口），但用户无法指定用哪一种。
// 这里把选择权交出来：可以强制只用某一种方式，也可以保持自动择优。
// 选定结果保存在包级变量里，随下载请求由前端设置。

import (
	"context"
	"errors"
	"fmt"
	"strings"
)

const (
	downloadMethodAuto   = "auto"
	downloadMethodApp    = "app"
	downloadMethodWeb    = "web"
	downloadMethodBackup = "backup"
)

var (
	activeDownloadMethod   = downloadMethodAuto
	lastUsedDownloadMethod string
)

// downloadMethodOptions 返回可选的下载方式，前端用它渲染设置项。
// 与 lib/download_methods.dart 里的清单保持一致，改动时两边同步。
func downloadMethodOptions() []map[string]any {
	return []map[string]any{
		{
			"id":     downloadMethodAuto,
			"name":   "自动择优",
			"detail": "依次尝试 App 直连、网页解析、备用接口，成功即用（默认）",
		},
		{
			"id":     downloadMethodApp,
			"name":   "App 直连",
			"detail": "走红果 App 接口取原画直链，画质最好；接口调整时可能失效",
		},
		{
			"id":     downloadMethodWeb,
			"name":   "网页解析",
			"detail": "解析红果播放页取流，部分剧集可能只允许试看",
		},
		{
			"id":     downloadMethodBackup,
			"name":   "备用接口",
			"detail": "App 与网页都不可用时的兜底通道",
		},
	}
}

func validDownloadMethod(value string) bool {
	for _, option := range downloadMethodOptions() {
		if option["id"] == value {
			return true
		}
	}
	return false
}

// normalizeDownloadMethod 把设置里的值收敛到合法范围，空值或未知值都按自动处理。
func normalizeDownloadMethod(value string) string {
	value = strings.TrimSpace(value)
	if validDownloadMethod(value) {
		return value
	}
	return downloadMethodAuto
}

// resolveDramaFetchMedia 在用户指定了下载方式时接管红果取流。
// 返回 handled 为 false 表示保持上游原有的自动择优逻辑。
func (d *Downloader) resolveDramaFetchMedia(ctx context.Context, task Task) (providerMedia, bool, error) {
	method := activeDownloadMethod
	if method == "" || method == downloadMethodAuto {
		return providerMedia{}, false, nil
	}
	source, seriesID, ok := splitProviderDramaID(task.DramaID)
	if !ok || source != sourceHongguo {
		return providerMedia{}, false, nil
	}
	videoID := strings.TrimPrefix(task.Chapter.VideoURL, "hongguo-cenc://")
	if !hongguoNumericID.MatchString(videoID) || !hongguoNumericID.MatchString(seriesID) {
		return providerMedia{}, true, errors.New("红果章节 ID 无效，请重新获取章节")
	}

	var media providerMedia
	var err error
	switch method {
	case downloadMethodApp:
		media, err = d.resolveHongguoAppMedia(ctx, videoID)
	case downloadMethodWeb:
		media, err = d.resolveHongguoWebMedia(ctx, seriesID, videoID)
	case downloadMethodBackup:
		media, err = d.resolveHongguoPlaybackAPI(ctx, seriesID, videoID)
	default:
		return providerMedia{}, false, nil
	}
	if err != nil {
		name := "所选方式"
		for _, option := range downloadMethodOptions() {
			if option["id"] == method {
				name = fmt.Sprintf("%v", option["name"])
			}
		}
		return providerMedia{}, true, fmt.Errorf("%s取流失败：%w", name, err)
	}
	lastUsedDownloadMethod = method
	return media, true, nil
}
