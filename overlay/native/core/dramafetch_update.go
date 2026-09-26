package core

// 本项目新增：应用内检查更新、下载安装包并启动安装。
//
// 更新源固定为本项目自己的 GitHub Release。请求与下载都支持填加速前缀
// （例如 https://ghfast.top/ ），拼在原始地址前面即可通过镜像访问。
//
// 为了尽量快：先用 probe 并发探测各加速源的延迟，选最快的一个；下载安装包时
// 走多线程分片（4 段），每段独立写文件，最后合并，内存占用只有几百 KB。

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"net/http"
	"os"
	"os/exec"
	"path/filepath"
	"sort"
	"strconv"
	"strings"
	"sync"
	"time"
)

const (
	dramaFetchRepo      = "Adamcssy19/DramaFetch"
	dramaFetchAPIBase   = "https://api.github.com"
	dramaFetchUserAgent = "DramaFetch-Updater"

	// 分片下载的线程数与单块大小，保持轻量，不占内存
	dramaFetchThreads   = 4
	dramaFetchChunkSize = 128 * 1024

	// 单个加速源的探测超时。
	// 探测是并发跑的、要等最慢的一个，而列表里有几个源在国内会直接卡死，
	// 等满超时才继续 —— 界面上就是「点了检查更新半天没动静」，所以压到 2.5 秒。
	dramaFetchProbeTimeout = 2500 * time.Millisecond

	// 版本检查本身的超时，直连实测不到 1 秒。
	dramaFetchCheckTimeout = 8 * time.Second
)

// dramaFetchMirror 是一个加速源；前缀为空表示直连。
type dramaFetchMirror struct {
	Prefix string
	Label  string
}

var dramaFetchMirrors = []dramaFetchMirror{
	{"", "直连 GitHub"},
	{"https://ghfast.top/", "ghfast.top"},
	{"https://gh-proxy.com/", "gh-proxy.com"},
	{"https://ghproxy.net/", "ghproxy.net"},
	{"https://gh.llkk.cc/", "gh.llkk.cc"},
}

var (
	dramaFetchUpdateMu        sync.Mutex
	dramaFetchUpdateState     = "idle"
	dramaFetchUpdateReceived  int64
	dramaFetchUpdateTotal     int64
	dramaFetchUpdatePath      string
	dramaFetchUpdateError     string
	dramaFetchUpdateAssetURL  string
	dramaFetchUpdateAssetName string
	dramaFetchUpdateThreads   int
)

// nativeUpdate 处理更新请求：
// probe 探测各源延迟，check 检查更新，download 开始下载，status 查询进度，launch 运行安装包。
func (engine *nativeEngine) nativeUpdate(ctx context.Context, input nativeInput) (any, error) {
	switch input.Command {
	case "probe":
		return engine.probeDramaFetchMirrors(ctx), nil
	case "check":
		return engine.checkDramaFetchUpdate(ctx, strings.TrimSpace(input.Query))
	case "download":
		return startDramaFetchUpdate(strings.TrimSpace(input.Query))
	case "status":
		return dramaFetchUpdateStatus(), nil
	case "launch":
		return launchDramaFetchInstaller()
	case "openLogs":
		return openDramaFetchLogs()
	case "channels":
		return channelProbePayload(ctx, true), nil
	default:
		return nil, errors.New("更新请求无效")
	}
}

// probeDramaFetchMirrors 并发访问各加速源，按响应快慢排序返回。
//
// 探测目标是「检查更新」实际要用的接口地址，取首包时间作为延迟；
// 这样选出来的源最贴近真实体验，且不会真的下载任何数据。
func (engine *nativeEngine) probeDramaFetchMirrors(ctx context.Context) map[string]any {
	type result struct {
		Index int
		Delay int64
		OK    bool
	}

	endpoint := fmt.Sprintf("%s/repos/%s/releases/latest", dramaFetchAPIBase, dramaFetchRepo)
	client := &http.Client{Timeout: dramaFetchProbeTimeout}

	results := make([]result, len(dramaFetchMirrors))
	var wait sync.WaitGroup
	for index, mirror := range dramaFetchMirrors {
		wait.Add(1)
		go func(index int, mirror dramaFetchMirror) {
			defer wait.Done()
			target := mirror.Prefix + endpoint
			requestCtx, cancel := context.WithTimeout(ctx, dramaFetchProbeTimeout)
			defer cancel()
			request, err := http.NewRequestWithContext(requestCtx, http.MethodGet, target, nil)
			if err != nil {
				results[index] = result{Index: index, Delay: -1}
				return
			}
			request.Header.Set("User-Agent", dramaFetchUserAgent)
			request.Header.Set("Accept", "application/vnd.github+json")

			start := time.Now()
			response, err := client.Do(request)
			if err != nil {
				results[index] = result{Index: index, Delay: -1}
				return
			}
			// 只读一点点，拿到响应头就够了
			io.CopyN(io.Discard, response.Body, 64)
			response.Body.Close()
			duration := time.Since(start).Milliseconds()

			ok := response.StatusCode == http.StatusOK
			if !ok {
				results[index] = result{Index: index, Delay: -1}
				return
			}
			results[index] = result{Index: index, Delay: duration, OK: true}
		}(index, mirror)
	}
	wait.Wait()

	sort.SliceStable(results, func(left, right int) bool {
		// 可用的排在前面，其次按延迟从小到大
		if results[left].OK != results[right].OK {
			return results[left].OK
		}
		if results[left].Delay != results[right].Delay {
			return results[left].Delay < results[right].Delay
		}
		return results[left].Index < results[right].Index
	})

	items := make([]map[string]any, 0, len(results))
	best := ""
	bestLabel := ""
	bestDelay := int64(-1)
	for _, item := range results {
		mirror := dramaFetchMirrors[item.Index]
		items = append(items, map[string]any{
			"prefix": mirror.Prefix,
			"label":  mirror.Label,
			"delay":  item.Delay,
			"ok":     item.OK,
		})
		if item.OK && best == "" {
			best = mirror.Prefix
			bestLabel = mirror.Label
			bestDelay = item.Delay
		}
	}
	return map[string]any{
		"items":     items,
		"best":      best,
		"bestLabel": bestLabel,
		"bestDelay": bestDelay,
	}
}

// checkDramaFetchUpdate 读取最新发布信息。mirror 为空时直连官方接口。
func (engine *nativeEngine) checkDramaFetchUpdate(ctx context.Context, mirror string) (any, error) {
	base := strings.TrimRight(mirror, "/")
	if base == "" {
		base = dramaFetchAPIBase
	}
	endpoint := fmt.Sprintf("%s/repos/%s/releases/latest", base, dramaFetchRepo)
	request, err := http.NewRequestWithContext(ctx, http.MethodGet, endpoint, nil)
	if err != nil {
		return nil, errors.New("更新请求无效")
	}
	request.Header.Set("User-Agent", dramaFetchUserAgent)
	request.Header.Set("Accept", "application/vnd.github+json")

	response, err := engine.downloader.client.Do(request)
	if err != nil {
		return nil, errors.New("无法连接更新服务，请检查网络或换个加速源重试")
	}
	defer response.Body.Close()
	if response.StatusCode == http.StatusNotFound {
		return nil, errors.New("尚未发布任何版本")
	}
	if response.StatusCode != http.StatusOK {
		return nil, fmt.Errorf("更新服务返回异常（%d）", response.StatusCode)
	}

	var payload struct {
		TagName     string `json:"tag_name"`
		Body        string `json:"body"`
		PublishedAt string `json:"published_at"`
		HTMLURL     string `json:"html_url"`
		Assets      []struct {
			Name               string `json:"name"`
			Size               int64  `json:"size"`
			BrowserDownloadURL string `json:"browser_download_url"`
		} `json:"assets"`
	}
	if err := json.NewDecoder(io.LimitReader(response.Body, 1<<20)).Decode(&payload); err != nil {
		return nil, errors.New("更新信息格式异常")
	}

	assets := []map[string]any{}
	installerURL := ""
	installerName := ""
	for _, item := range payload.Assets {
		if !strings.HasSuffix(strings.ToLower(item.Name), ".exe") {
			continue
		}
		assets = append(assets, map[string]any{
			"name": item.Name,
			"size": item.Size,
			"url":  item.BrowserDownloadURL,
		})
		if installerURL == "" {
			installerURL = item.BrowserDownloadURL
			installerName = item.Name
		}
	}

	dramaFetchUpdateMu.Lock()
	dramaFetchUpdateAssetURL = installerURL
	dramaFetchUpdateAssetName = installerName
	dramaFetchUpdateMu.Unlock()

	return map[string]any{
		"tag":         payload.TagName,
		"latest":      strings.TrimPrefix(payload.TagName, "v"),
		"notes":       payload.Body,
		"publishedAt": payload.PublishedAt,
		"pageUrl":     payload.HTMLURL,
		"assets":      assets,
	}, nil
}

func startDramaFetchUpdate(mirror string) (any, error) {
	dramaFetchUpdateMu.Lock()
	defer dramaFetchUpdateMu.Unlock()
	if dramaFetchUpdateState == "downloading" {
		return map[string]any{"state": dramaFetchUpdateState}, nil
	}
	if dramaFetchUpdateAssetURL == "" {
		return nil, errors.New("请先检查更新")
	}
	dramaFetchUpdateState = "downloading"
	dramaFetchUpdateReceived = 0
	dramaFetchUpdateTotal = 0
	dramaFetchUpdatePath = ""
	dramaFetchUpdateError = ""
	dramaFetchUpdateThreads = 0
	// 加速前缀直接拼在原始下载地址前面
	target := strings.TrimRight(mirror, "/") + dramaFetchUpdateAssetURL
	name := dramaFetchUpdateAssetName
	go downloadDramaFetchUpdate(target, name)
	return map[string]any{"state": dramaFetchUpdateState}, nil
}

func downloadDramaFetchUpdate(url, name string) {
	fail := func(message string) {
		dramaFetchUpdateMu.Lock()
		dramaFetchUpdateState = "failed"
		dramaFetchUpdateError = message
		dramaFetchUpdateMu.Unlock()
	}

	directory := filepath.Join(os.Getenv("USERPROFILE"), "Downloads")
	if directory == "" || os.Getenv("USERPROFILE") == "" {
		home, err := os.UserHomeDir()
		if err != nil {
			fail("找不到下载目录")
			return
		}
		directory = filepath.Join(home, "Downloads")
	}
	if err := os.MkdirAll(directory, 0o755); err != nil {
		fail("无法创建下载目录")
		return
	}
	destination := filepath.Join(directory, name)
	temporary := destination + ".part"

	total, supportsRange := probeDownloadSource(url)
	if total > 0 && supportsRange && total > int64(dramaFetchThreads)*256*1024 {
		if err := downloadInChunks(url, temporary, total); err == nil {
			finishDramaFetchDownload(temporary, destination)
			return
		}
		// 分片失败就清理干净，改用单线程再来一次
		os.Remove(temporary)
		dramaFetchUpdateMu.Lock()
		dramaFetchUpdateReceived = 0
		dramaFetchUpdateTotal = 0
		dramaFetchUpdateThreads = 0
		dramaFetchUpdateMu.Unlock()
	}

	if err := downloadInOnePass(url, temporary); err != nil {
		os.Remove(temporary)
		fail(err.Error())
		return
	}
	finishDramaFetchDownload(temporary, destination)
}

func finishDramaFetchDownload(temporary, destination string) {
	// 下载完成后再改名为最终文件，中途失败不会留下残缺文件
	if err := os.Rename(temporary, destination); err != nil {
		os.Remove(temporary)
		dramaFetchUpdateMu.Lock()
		dramaFetchUpdateState = "failed"
		dramaFetchUpdateError = "安装包保存失败"
		dramaFetchUpdateMu.Unlock()
		return
	}
	dramaFetchUpdateMu.Lock()
	dramaFetchUpdateState = "done"
	dramaFetchUpdatePath = destination
	dramaFetchUpdateMu.Unlock()
}

// probeDownloadSource 询问服务端是否支持分片，并取回文件总长度。
func probeDownloadSource(url string) (int64, bool) {
	request, err := http.NewRequest(http.MethodGet, url, nil)
	if err != nil {
		return 0, false
	}
	request.Header.Set("User-Agent", dramaFetchUserAgent)
	request.Header.Set("Range", "bytes=0-0")

	client := &http.Client{Timeout: 20 * time.Second}
	response, err := client.Do(request)
	if err != nil {
		return 0, false
	}
	defer response.Body.Close()
	io.CopyN(io.Discard, response.Body, 16)

	if response.StatusCode == http.StatusPartialContent {
		// Content-Range: bytes 0-0/123456
		contentRange := response.Header.Get("Content-Range")
		if index := strings.LastIndex(contentRange, "/"); index >= 0 {
			if size, parseErr := strconv.ParseInt(contentRange[index+1:], 10, 64); parseErr == nil {
				return size, true
			}
		}
	}
	return response.ContentLength, false
}

// downloadInChunks 把文件切成若干段并发下载，最后按顺序合并。
func downloadInChunks(url, temporary string, total int64) error {
	partSize := total / int64(dramaFetchThreads)
	if total%int64(dramaFetchThreads) != 0 {
		partSize++
	}

	paths := make([]string, dramaFetchThreads)
	for index := range paths {
		paths[index] = fmt.Sprintf("%s.%d", temporary, index)
	}

	dramaFetchUpdateMu.Lock()
	dramaFetchUpdateTotal = total
	dramaFetchUpdateThreads = dramaFetchThreads
	dramaFetchUpdateMu.Unlock()

	var wait sync.WaitGroup
	failures := make([]error, dramaFetchThreads)
	for index := 0; index < dramaFetchThreads; index++ {
		start := int64(index) * partSize
		end := start + partSize - 1
		if end >= total {
			end = total - 1
		}
		if start > end {
			continue
		}
		wait.Add(1)
		go func(index int, start, end int64) {
			defer wait.Done()
			failures[index] = downloadChunk(url, paths[index], start, end)
		}(index, start, end)
	}
	wait.Wait()

	for _, failure := range failures {
		if failure != nil {
			for _, path := range paths {
				os.Remove(path)
			}
			return failure
		}
	}

	// 按分片顺序合并
	merged, err := os.Create(temporary)
	if err != nil {
		for _, path := range paths {
			os.Remove(path)
		}
		return errors.New("无法写入下载文件")
	}
	buffer := make([]byte, dramaFetchChunkSize)
	for _, path := range paths {
		part, openErr := os.Open(path)
		if openErr != nil {
			merged.Close()
			for _, item := range paths {
				os.Remove(item)
			}
			return errors.New("分片文件缺失")
		}
		if _, copyErr := io.CopyBuffer(merged, part, buffer); copyErr != nil {
			part.Close()
			merged.Close()
			for _, item := range paths {
				os.Remove(item)
			}
			return errors.New("分片合并失败")
		}
		part.Close()
		os.Remove(path)
	}
	if err := merged.Close(); err != nil {
		return errors.New("分片合并失败")
	}
	return nil
}

func downloadChunk(url, path string, start, end int64) error {
	request, err := http.NewRequest(http.MethodGet, url, nil)
	if err != nil {
		return err
	}
	request.Header.Set("User-Agent", dramaFetchUserAgent)
	request.Header.Set("Range", fmt.Sprintf("bytes=%d-%d", start, end))

	client := &http.Client{Timeout: 30 * time.Minute}
	response, err := client.Do(request)
	if err != nil {
		return err
	}
	defer response.Body.Close()
	if response.StatusCode != http.StatusPartialContent && response.StatusCode != http.StatusOK {
		return fmt.Errorf("分片下载失败（%d）", response.StatusCode)
	}

	file, err := os.Create(path)
	if err != nil {
		return err
	}
	defer file.Close()

	buffer := make([]byte, dramaFetchChunkSize)
	for {
		read, readErr := response.Body.Read(buffer)
		if read > 0 {
			if _, writeErr := file.Write(buffer[:read]); writeErr != nil {
				return writeErr
			}
			dramaFetchUpdateMu.Lock()
			dramaFetchUpdateReceived += int64(read)
			dramaFetchUpdateMu.Unlock()
		}
		if readErr == io.EOF {
			break
		}
		if readErr != nil {
			return readErr
		}
	}
	return nil
}

// downloadInOnePass 是单线程兜底：服务端不支持分片时使用。
func downloadInOnePass(url, temporary string) error {
	client := &http.Client{Timeout: 30 * time.Minute}
	request, err := http.NewRequest(http.MethodGet, url, nil)
	if err != nil {
		return errors.New("下载地址无效")
	}
	request.Header.Set("User-Agent", dramaFetchUserAgent)
	response, err := client.Do(request)
	if err != nil {
		return errors.New("下载失败，请换个加速源重试")
	}
	defer response.Body.Close()
	if response.StatusCode != http.StatusOK && response.StatusCode != http.StatusPartialContent {
		return fmt.Errorf("下载失败（%d），请换个加速源重试", response.StatusCode)
	}

	file, err := os.Create(temporary)
	if err != nil {
		return errors.New("无法写入下载文件")
	}
	defer file.Close()

	dramaFetchUpdateMu.Lock()
	dramaFetchUpdateTotal = response.ContentLength
	dramaFetchUpdateThreads = 1
	dramaFetchUpdateMu.Unlock()

	buffer := make([]byte, dramaFetchChunkSize*2)
	for {
		read, readErr := response.Body.Read(buffer)
		if read > 0 {
			if _, writeErr := file.Write(buffer[:read]); writeErr != nil {
				return errors.New("写入下载文件失败")
			}
			dramaFetchUpdateMu.Lock()
			dramaFetchUpdateReceived += int64(read)
			dramaFetchUpdateMu.Unlock()
		}
		if readErr == io.EOF {
			break
		}
		if readErr != nil {
			return errors.New("下载中断，请重试")
		}
	}
	file.Close()
	return nil
}

func dramaFetchUpdateStatus() map[string]any {
	dramaFetchUpdateMu.Lock()
	defer dramaFetchUpdateMu.Unlock()
	return map[string]any{
		"state":    dramaFetchUpdateState,
		"received": dramaFetchUpdateReceived,
		"total":    dramaFetchUpdateTotal,
		"path":     dramaFetchUpdatePath,
		"error":    dramaFetchUpdateError,
		"threads":  dramaFetchUpdateThreads,
	}
}

func launchDramaFetchInstaller() (any, error) {
	dramaFetchUpdateMu.Lock()
	path := dramaFetchUpdatePath
	dramaFetchUpdateMu.Unlock()
	if path == "" {
		return nil, errors.New("安装包尚未下载完成")
	}
	if _, err := os.Stat(path); err != nil {
		return nil, errors.New("安装包已不存在，请重新下载")
	}
	command := exec.Command("cmd", "/c", "start", "", path)
	if err := command.Start(); err != nil {
		return nil, errors.New("无法启动安装程序")
	}
	return map[string]any{"started": true, "path": path}, nil
}
