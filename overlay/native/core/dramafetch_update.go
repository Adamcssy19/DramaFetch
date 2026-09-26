package core

// 本项目新增：应用内检查更新、下载安装包并启动安装。
//
// 更新源固定为本项目自己的 GitHub Release。请求与下载都支持填加速前缀
// （例如 https://ghfast.top/ ），拼在原始地址前面即可通过镜像访问。

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
	"strings"
	"sync"
	"time"
)

const (
	dramaFetchRepo      = "Adamcssy19/DramaFetch"
	dramaFetchAPIBase   = "https://api.github.com"
	dramaFetchUserAgent = "DramaFetch-Updater"
)

var (
	dramaFetchUpdateMu        sync.Mutex
	dramaFetchUpdateState     = "idle"
	dramaFetchUpdateReceived  int64
	dramaFetchUpdateTotal     int64
	dramaFetchUpdatePath      string
	dramaFetchUpdateError     string
	dramaFetchUpdateAssetURL  string
	dramaFetchUpdateAssetName string
)

// nativeUpdate 处理更新请求：
// check 检查更新，download 开始下载，status 查询进度，launch 运行已下载的安装包。
func (engine *nativeEngine) nativeUpdate(ctx context.Context, input nativeInput) (any, error) {
	switch input.Command {
	case "check":
		return engine.checkDramaFetchUpdate(ctx, strings.TrimSpace(input.Query))
	case "download":
		return startDramaFetchUpdate(strings.TrimSpace(input.Query))
	case "status":
		return dramaFetchUpdateStatus(), nil
	case "launch":
		return launchDramaFetchInstaller()
	default:
		return nil, errors.New("更新请求无效")
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

	client := &http.Client{Timeout: 30 * time.Minute}
	request, err := http.NewRequest(http.MethodGet, url, nil)
	if err != nil {
		fail("下载地址无效")
		return
	}
	request.Header.Set("User-Agent", dramaFetchUserAgent)
	response, err := client.Do(request)
	if err != nil {
		fail("下载失败，请换个加速源重试")
		return
	}
	defer response.Body.Close()
	if response.StatusCode != http.StatusOK {
		fail(fmt.Sprintf("下载失败（%d），请换个加速源重试", response.StatusCode))
		return
	}

	file, err := os.Create(temporary)
	if err != nil {
		fail("无法写入下载文件")
		return
	}
	defer file.Close()

	dramaFetchUpdateMu.Lock()
	dramaFetchUpdateTotal = response.ContentLength
	dramaFetchUpdateMu.Unlock()

	buffer := make([]byte, 256*1024)
	for {
		read, readErr := response.Body.Read(buffer)
		if read > 0 {
			if _, writeErr := file.Write(buffer[:read]); writeErr != nil {
				fail("写入下载文件失败")
				os.Remove(temporary)
				return
			}
			dramaFetchUpdateMu.Lock()
			dramaFetchUpdateReceived += int64(read)
			dramaFetchUpdateMu.Unlock()
		}
		if readErr == io.EOF {
			break
		}
		if readErr != nil {
			fail("下载中断，请重试")
			os.Remove(temporary)
			return
		}
	}
	file.Close()

	// 下载完成后再改名为最终文件，中途失败不会留下残缺文件
	if err := os.Rename(temporary, destination); err != nil {
		os.Remove(temporary)
		fail("安装包保存失败")
		return
	}

	dramaFetchUpdateMu.Lock()
	dramaFetchUpdateState = "done"
	dramaFetchUpdatePath = destination
	dramaFetchUpdateMu.Unlock()
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
