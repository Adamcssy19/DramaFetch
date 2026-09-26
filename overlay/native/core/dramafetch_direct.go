package core

// 本项目新增：下载渠道（取流通道）的统一注册表与自动测速。
//
// ## 分层
// 上游对果子已经做了三层回退（应用接口 → 网页解析 → 备用接口），但用户无法指定用哪一种，
// 也不会按网络情况挑最快的。这一层负责三件事：
//
//	1. 渠道注册表：每个渠道的编号、名称、说明、探测地址只写一次，
//	   设置项、探测目标、日志里的中文名都从同一份数据生成，不会出现改了名字漏改探测地址的情况；
//	2. 自动测速：并发探测各渠道的可用性与延迟，结果缓存 10 分钟；
//	3. 取流接管：把用户选定的渠道交给上游的下载器执行，失败按需交回上游原有回退链。
//
// 真正的下载、分片、解密仍然全部复用上游实现，本项目只做「选哪条路」。

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

// dramaFetchChannel 一个取流通道的全部元信息。
type dramaFetchChannel struct {
	ID string

	// Name 与 Detail 是给设置页显示的文案。
	Name   string
	Detail string

	// Probe 是探测地址，留空表示这是策略项（如「自动择优」）而不是具体通道。
	Probe string
}

// dramaFetchChannels 是渠道的唯一数据源，顺序即设置项顺序。
var dramaFetchChannels = []dramaFetchChannel{
	{
		ID:     downloadMethodAuto,
		Name:   "自动择优",
		Detail: "先测各渠道的可用性与延迟，从最快的开始试（默认）",
	},
	{
		ID:     downloadMethodApp,
		Name:   "应用接口",
		Detail: "走应用接口取原画直链，画质最好；接口调整时可能失效",
		Probe:  "https://api5-normal-sinfonlineb.fqnovel.com/",
	},
	{
		ID:     downloadMethodWeb,
		Name:   "网页解析",
		Detail: "解析播放页取流，部分剧集可能只允许试看",
		Probe:  "https://hongguoduanju.com/",
	},
	{
		ID:     downloadMethodBackup,
		Name:   "备用接口",
		Detail: "前两个都不可用时的兜底通道",
		Probe:  "https://djapi.999888456.xyz/",
	},
}

func dramaFetchChannelByID(id string) (dramaFetchChannel, bool) {
	for _, channel := range dramaFetchChannels {
		if channel.ID == id {
			return channel, true
		}
	}
	return dramaFetchChannel{}, false
}

// dramaFetchChannelLabel 返回渠道的中文名，未知编号原样返回，便于日志里看出传了什么。
func dramaFetchChannelLabel(id string) string {
	if channel, ok := dramaFetchChannelByID(id); ok {
		return channel.Name
	}
	return id
}

// probeChannels 只挑有探测地址的具体通道，策略项不参与测速。
func probeChannels() []dramaFetchChannel {
	items := make([]dramaFetchChannel, 0, len(dramaFetchChannels))
	for _, channel := range dramaFetchChannels {
		if channel.Probe != "" {
			items = append(items, channel)
		}
	}
	return items
}

// downloadMethodOptions 返回可选的下载渠道，前端用它渲染设置项。
// 与 lib/download_methods.dart 里的清单保持一致，改动时两边同步。
func downloadMethodOptions() []map[string]any {
	options := make([]map[string]any, 0, len(dramaFetchChannels))
	for _, channel := range dramaFetchChannels {
		options = append(options, map[string]any{
			"id":     channel.ID,
			"name":   channel.Name,
			"detail": channel.Detail,
		})
	}
	return options
}

func validDownloadMethod(value string) bool {
	_, ok := dramaFetchChannelByID(value)
	return ok
}

// normalizeDownloadMethod 把设置里的值收敛到合法范围，空值或未知值都按自动处理。
func normalizeDownloadMethod(value string) string {
	value = strings.TrimSpace(value)
	if validDownloadMethod(value) {
		return value
	}
	return downloadMethodAuto
}

var (
	channelProbeMu     sync.Mutex
	channelProbeOrder  []string
	channelProbeDetail []map[string]any
	channelProbeAt     time.Time
)

// probeCacheTTL 探测结果的保鲜时间。太短会频繁测速拖慢首次下载，太长则网络切换后不及时。
const probeCacheTTL = 10 * time.Minute

func channelProbeFresh() bool {
	return len(channelProbeDetail) > 0 && time.Since(channelProbeAt) < probeCacheTTL
}

// probeDramaFetchChannels 并发探测各渠道，返回按延迟从快到慢的结果。
// 结果缓存 10 分钟，避免每次下载都测一遍。
func probeDramaFetchChannels(ctx context.Context, force bool) []map[string]any {
	channelProbeMu.Lock()
	defer channelProbeMu.Unlock()
	if !force && channelProbeFresh() {
		return channelProbeDetail
	}

	targets := probeChannels()
	type outcome struct {
		id    string
		delay int64
		ok    bool
	}
	results := make([]outcome, len(targets))
	// 每个探测请求都要走一次 TLS 握手，用独立客户端避免和下载共用连接池后互相拖累
	client := &http.Client{Timeout: 6 * time.Second}

	var wait sync.WaitGroup
	for index, target := range targets {
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
		}(index, target.ID, target.Probe)
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
	digest := make([]string, 0, len(detail))
	for _, item := range detail {
		digest = append(digest, fmt.Sprintf(
			"%s=%v",
			dramaFetchChannelLabel(fmt.Sprintf("%v", item["id"])),
			item["delay"],
		))
	}
	dfLog("渠道", "全部结果", strings.Join(digest, " "))
	return detail
}

// fastestDramaFetchChannel 返回当前可用的最快渠道，没有可用渠道时返回空串。
func fastestDramaFetchChannel(ctx context.Context) string {
	channelProbeMu.Lock()
	cached := channelProbeOrder
	fresh := channelProbeFresh()
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

// resolveChannelMedia 用指定渠道取流。取流本身全部复用上游的三个实现。
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
	method := normalizeDownloadMethod(activeDownloadMethod)
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
		"items":  detail,
		"best":   best,
		"active": normalizeDownloadMethod(activeDownloadMethod),
	}
}
