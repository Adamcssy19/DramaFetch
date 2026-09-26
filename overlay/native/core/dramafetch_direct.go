package core

// 本项目新增：下载渠道的选择与自动测速。
//
// 上游对果子本身已经做了三层回退（App 接口 → 网页解析 → 备用接口），但用户无法指定用哪一种，
// 也不会按网络情况挑最快的。这里把两件事补上：
//   1. 允许固定使用某个渠道；
//   2. 「自动」模式下先并发探测各渠道的可用性与延迟，从最快的开始试，失败再交回上游原有回退。

import (
	"context"
	"errors"
	"fmt"
	"io"
	"net/http"
	"sort"
	"strings"
	"sync"
	"time"
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

// dramaFetchChannelTargets 各渠道的探测地址，用来判断可用性与响应快慢。
var dramaFetchChannelTargets = []struct {
	ID    string
	URL   string
	Label string
}{
	{downloadMethodApp, "https://api5-normal-sinfonlineb.fqnovel.com/", "应用接口"},
	{downloadMethodWeb, "https://hongguoduanju.com/", "网页解析"},
	{downloadMethodBackup, "https://djapi.999888456.xyz/", "备用接口"},
}

var (
	channelProbeMu     sync.Mutex
	channelProbeOrder  []string
	channelProbeDetail []map[string]any
	channelProbeAt     time.Time
)

// downloadMethodOptions 返回可选的下载渠道，前端用它渲染设置项。
// 与 lib/download_methods.dart 里的清单保持一致，改动时两边同步。
func downloadMethodOptions() []map[string]any {
	return []map[string]any{
		{
			"id":     downloadMethodAuto,
			"name":   "自动择优",
			"detail": "先测各渠道的可用性与延迟，从最快的开始试（默认）",
		},
		{
			"id":     downloadMethodApp,
			"name":   "应用接口",
			"detail": "走应用接口取原画直链，画质最好；接口调整时可能失效",
		},
		{
			"id":     downloadMethodWeb,
			"name":   "网页解析",
			"detail": "解析播放页取流，部分剧集可能只允许试看",
		},
		{
			"id":     downloadMethodBackup,
			"name":   "备用接口",
			"detail": "前两个都不可用时的兜底通道",
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

func dramaFetchChannelLabel(id string) string {
	for _, target := range dramaFetchChannelTargets {
		if target.ID == id {
			return target.Label
		}
	}
	return id
}

// probeDramaFetchChannels 并发探测各渠道，返回按延迟从快到慢的结果。
// 结果缓存 10 分钟，避免每次下载都测一遍。
func probeDramaFetchChannels(ctx context.Context, force bool) []map[string]any {
	channelProbeMu.Lock()
	defer channelProbeMu.Unlock()
	if !force && len(channelProbeDetail) > 0 && time.Since(channelProbeAt) < 10*time.Minute {
		return channelProbeDetail
	}

	type outcome struct {
		id    string
		delay int64
		ok    bool
	}
	results := make([]outcome, len(dramaFetchChannelTargets))
	client := &http.Client{Timeout: 6 * time.Second}

	var wait sync.WaitGroup
	for index, target := range dramaFetchChannelTargets {
		wait.Add(1)
		go func(index int, id, url string) {
			defer wait.Done()
			requestCtx, cancel := context.WithTimeout(ctx, 6*time.Second)
			defer cancel()
			request, err := http.NewRequestWithContext(requestCtx, http.MethodGet, url, nil)
			if err != nil {
				results[index] = outcome{id: id, delay: -1}
				return
			}
			request.Header.Set("User-Agent", dramaFetchUserAgent)
			started := time.Now()
			response, err := client.Do(request)
			if err != nil {
				results[index] = outcome{id: id, delay: -1}
				return
			}
			io.CopyN(io.Discard, response.Body, 64)
			response.Body.Close()
			results[index] = outcome{
				id:    id,
				delay: time.Since(started).Milliseconds(),
				ok:    true,
			}
		}(index, target.ID, target.URL)
	}
	wait.Wait()

	sort.SliceStable(results, func(left, right int) bool {
		if results[left].ok != results[right].ok {
			return results[left].ok
		}
		return results[left].delay < results[right].delay
	})

	detail := make([]map[string]any, 0, len(results))
	order := make([]string, 0, len(results))
	for _, item := range results {
		detail = append(detail, map[string]any{
			"id":    item.id,
			"label": dramaFetchChannelLabel(item.id),
			"delay": item.delay,
			"ok":    item.ok,
		})
		if item.ok {
			order = append(order, item.id)
		}
	}

	channelProbeOrder = order
	channelProbeDetail = detail
	channelProbeAt = time.Now()

	if len(order) == 0 {
		dfLog("渠道", "探测完成，所有渠道都不可达")
	} else {
		dfLog(
			"渠道",
			"探测完成，最快的是",
			dramaFetchChannelLabel(order[0]),
			fmt.Sprintf("%v 毫秒", detail[0]["delay"]),
		)
	}
	lastDigest := make([]string, 0, len(detail))
	for _, item := range detail {
		lastDigest = append(lastDigest, fmt.Sprintf(
			"%s=%v",
			dramaFetchChannelLabel(fmt.Sprintf("%v", item["id"])),
			item["delay"],
		))
	}
	dfLog("渠道", "全部结果", strings.Join(lastDigest, " "))
	return detail
}

// fastestDramaFetchChannel 返回当前可用的最快渠道，没有可用渠道时返回空串。
func fastestDramaFetchChannel(ctx context.Context) string {
	channelProbeMu.Lock()
	cached := channelProbeOrder
	fresh := len(channelProbeDetail) > 0 && time.Since(channelProbeAt) < 10*time.Minute
	channelProbeMu.Unlock()
	if fresh && len(cached) > 0 {
		return cached[0]
	}
	probeDramaFetchChannels(ctx, false)
	channelProbeMu.Lock()
	defer channelProbeMu.Unlock()
	if len(channelProbeOrder) == 0 {
		return ""
	}
	return channelProbeOrder[0]
}

// resolveChannelMedia 用指定渠道取流。
func (d *Downloader) resolveChannelMedia(
	ctx context.Context,
	method, seriesID, videoID string,
) (providerMedia, error) {
	switch method {
	case downloadMethodApp:
		return d.resolveHongguoAppMedia(ctx, videoID)
	case downloadMethodWeb:
		return d.resolveHongguoWebMedia(ctx, seriesID, videoID)
	case downloadMethodBackup:
		return d.resolveHongguoPlaybackAPI(ctx, seriesID, videoID)
	}
	return providerMedia{}, errors.New("未知的下载渠道")
}

// resolveDramaFetchMedia 接管果子取流。
// 返回 handled 为 false 表示保持上游原有的自动择优逻辑。
func (d *Downloader) resolveDramaFetchMedia(
	ctx context.Context,
	task Task,
) (providerMedia, bool, error) {
	method := activeDownloadMethod
	if method == "" {
		method = downloadMethodAuto
	}
	source, seriesID, ok := splitProviderDramaID(task.DramaID)
	if !ok || source != sourceHongguo {
		return providerMedia{}, false, nil
	}
	videoID := strings.TrimPrefix(task.Chapter.VideoURL, "hongguo-cenc://")
	if !hongguoNumericID.MatchString(videoID) || !hongguoNumericID.MatchString(seriesID) {
		return providerMedia{}, true, errors.New("剧集编号无效，请重新获取章节")
	}

	if method == downloadMethodAuto {
		// 先把探测到最快的渠道试一次；成功就用，失败交回上游原有的回退链
		fastest := fastestDramaFetchChannel(ctx)
		if fastest == "" {
			dfLog("渠道", "没有探测到可用渠道，交回默认回退")
			return providerMedia{}, false, nil
		}
		if media, err := d.resolveChannelMedia(ctx, fastest, seriesID, videoID); err == nil {
			lastUsedDownloadMethod = fastest
			dfLog("渠道", "使用自动选中的渠道", dramaFetchChannelLabel(fastest))
			return media, true, nil
		}
		dfLog("渠道", "自动选中的渠道取流失败，交回默认回退", dramaFetchChannelLabel(fastest))
		return providerMedia{}, false, nil
	}

	media, err := d.resolveChannelMedia(ctx, method, seriesID, videoID)
	if err != nil {
		return providerMedia{}, true, fmt.Errorf(
			"%s取流失败：%w",
			dramaFetchChannelLabel(method),
			err,
		)
	}
	lastUsedDownloadMethod = method
	dfLog("渠道", "使用指定渠道", dramaFetchChannelLabel(method))
	return media, true, nil
}

// channelProbePayload 把探测结果整理成前端能直接用的结构。
func channelProbePayload(ctx context.Context, force bool) map[string]any {
	detail := probeDramaFetchChannels(ctx, force)
	best := ""
	for _, item := range detail {
		if ok, _ := item["ok"].(bool); ok {
			best = fmt.Sprintf("%v", item["id"])
			break
		}
	}
	return map[string]any{
		"items": detail,
		"best":  best,
		"active": normalizeDownloadMethod(activeDownloadMethod),
	}
}
