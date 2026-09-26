package core

// 本项目新增：运行日志。
//
// 日志写在 %LocalAppData%\DramaFetch\logs\ 下，按天一个文件。目的是出问题时能直接查：
// 每个请求的动作、参数、耗时、错误，以及更新与下载的关键节点都会记进去。
// 写日志失败不影响功能，只是没有记录。

import (
	"encoding/json"
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
	"sync"
	"time"
)

var (
	dramaFetchLogMu   sync.Mutex
	dramaFetchLogFile *os.File
	dramaFetchLogDay  string
)

// dramaFetchLogDir 返回日志目录：优先放在本地应用数据目录，没有就放用户目录。
func dramaFetchLogDir() string {
	base := os.Getenv("LOCALAPPDATA")
	if base == "" {
		home, err := os.UserHomeDir()
		if err != nil {
			return ""
		}
		base = home
	}
	return filepath.Join(base, "DramaFetch", "logs")
}

func dramaFetchLogHandle() *os.File {
	day := time.Now().Format("2006-01-02")
	if dramaFetchLogFile != nil && dramaFetchLogDay == day {
		return dramaFetchLogFile
	}
	directory := dramaFetchLogDir()
	if directory == "" {
		return nil
	}
	if err := os.MkdirAll(directory, 0o755); err != nil {
		return nil
	}
	file, err := os.OpenFile(
		filepath.Join(directory, "dramafetch-"+day+".log"),
		os.O_APPEND|os.O_CREATE|os.O_WRONLY,
		0o644,
	)
	if err != nil {
		return nil
	}
	if dramaFetchLogFile != nil {
		dramaFetchLogFile.Close()
	}
	dramaFetchLogFile = file
	dramaFetchLogDay = day
	return file
}

// dfLog 记一行日志。args 会以井号分隔拼在后面，方便按字段搜索。
func dfLog(scope, message string, args ...any) {
	dramaFetchLogMu.Lock()
	defer dramaFetchLogMu.Unlock()
	file := dramaFetchLogHandle()
	if file == nil {
		return
	}
	var builder strings.Builder
	builder.WriteString(time.Now().Format("2006-01-02 15:04:05.000"))
	builder.WriteString(" [")
	builder.WriteString(scope)
	builder.WriteString("] ")
	builder.WriteString(message)
	if len(args) > 0 {
		builder.WriteString(" | ")
		for index, item := range args {
			if index > 0 {
				builder.WriteString("  ")
			}
			text := fmt.Sprintf("%v", item)
			text = strings.ReplaceAll(text, "\n", " ")
			if len(text) > 200 {
				text = text[:200] + "…"
			}
			builder.WriteString(text)
		}
	}
	builder.WriteString("\n")
	file.WriteString(builder.String())
}

// dfLogRequest 记录一次请求的动作、耗时与结果，出错时连错误一起写。
func dfLogRequest(action, command string, started time.Time, err error) {
	elapsed := time.Since(started).Milliseconds()
	if err != nil {
		dfLog("请求", action+" 失败", fmt.Sprintf("%d 毫秒", elapsed), err.Error())
		return
	}
	if elapsed < 300 {
		// 快的请求只记一行，避免日志被刷爆
		dfLog("请求", action, fmt.Sprintf("%d 毫秒", elapsed))
		return
	}
	dfLog("请求", action+" 完成", fmt.Sprintf("%d 毫秒", elapsed))
}

// dfLogJSON 把请求参数压缩后写进日志，超长的截断。
func dfLogJSON(label string, payload any) {
	raw, err := json.Marshal(payload)
	if err != nil {
		return
	}
	text := string(raw)
	if len(text) > 400 {
		text = text[:400] + "…"
	}
	dfLog("参数", label, text)
}

// openDramaFetchLogs 用资源管理器打开日志目录，方便用户把文件发出来。
func openDramaFetchLogs() (any, error) {
	directory := dramaFetchLogDir()
	if directory == "" {
		return nil, fmt.Errorf("找不到日志目录")
	}
	if err := os.MkdirAll(directory, 0o755); err != nil {
		return nil, fmt.Errorf("无法创建日志目录")
	}
	command := exec.Command("explorer", directory)
	if err := command.Start(); err != nil {
		return nil, fmt.Errorf("无法打开日志目录")
	}
	dfLog("日志", "打开日志目录", directory)
	return map[string]any{"opened": true, "path": directory}, nil
}
