package core

// 本项目新增：运行日志。
//
// 日志写在 %LocalAppData%\DramaFetch\logs\ 下，按天一个文件。目的是出问题时能直接查：
// 每个请求的动作、参数、耗时、错误，以及更新与下载的关键节点都会记进去。
//
// ## 为什么要缓冲
// 上游每次请求都会调到这里，如果每条日志都直接 write+flush，一次同步下载能产生上千次磁盘写，
// 在机械盘和老旧机器上会实打实拖慢下载速度。这里改成内存缓冲：
// 攒够 64 KB 立刻落盘，否则最多延迟 2 秒写一次。写日志失败不影响任何功能。
//
// 另外做了两件保守的自我保护：单日文件超过 16 MB 就不再写，只保留最近 7 天的日志。

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

const (
	// dramaFetchLogFlushBytes 缓冲达到这个大小就立刻落盘。
	dramaFetchLogFlushBytes = 64 * 1024

	// dramaFetchLogFlushEvery 没有攒够缓冲时的最长滞留时间。
	dramaFetchLogFlushEvery = 2 * time.Second

	// dramaFetchLogMaxBytes 单日日志上限，超过就停止写入。
	dramaFetchLogMaxBytes = 16 << 20

	// dramaFetchLogKeepDays 日志保留天数。
	dramaFetchLogKeepDays = 7
)

var (
	dramaFetchLogMu   sync.Mutex
	dramaFetchLogFile *os.File
	dramaFetchLogDay  string
	dramaFetchLogBuf  strings.Builder
	dramaFetchLogLast time.Time
	dramaFetchLogSize int64
	dramaFetchLogFull bool
	dramaFetchLogTimer *time.Timer
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

// dramaFetchLogHandleLocked 取当天日志文件的句柄，跨天时自动切换。
// 调用方必须已持有 dramaFetchLogMu。
func dramaFetchLogHandleLocked() *os.File {
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
	path := filepath.Join(directory, "dramafetch-"+day+".log")
	file, err := os.OpenFile(path, os.O_APPEND|os.O_CREATE|os.O_WRONLY, 0o644)
	if err != nil {
		return nil
	}
	if dramaFetchLogFile != nil {
		dramaFetchLogFile.Close()
	}
	dramaFetchLogFile = file
	dramaFetchLogDay = day
	dramaFetchLogFull = false
	if info, err := file.Stat(); err == nil {
		dramaFetchLogSize = info.Size()
	} else {
		dramaFetchLogSize = 0
	}
	dramaFetchLogCleanupLocked(directory)
	return file
}

// dramaFetchLogCleanupLocked 删掉超过保留期的旧日志，顺带把目录体积控制住。
func dramaFetchLogCleanupLocked(directory string) {
	entries, err := os.ReadDir(directory)
	if err != nil {
		return
	}
	deadline := time.Now().AddDate(0, 0, -dramaFetchLogKeepDays)
	for _, entry := range entries {
		name := entry.Name()
		if entry.IsDir() ||
			!strings.HasPrefix(name, "dramafetch-") ||
			!strings.HasSuffix(name, ".log") {
			continue
		}
		info, err := entry.Info()
		if err != nil || !info.ModTime().Before(deadline) {
			continue
		}
		os.Remove(filepath.Join(directory, name))
	}
}

// dramaFetchLogFormat 拼一行日志。参数以两个空格分隔，超长的截断。
func dramaFetchLogFormat(scope, message string, args ...any) string {
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
	return builder.String()
}

// dramaFetchLogFlushLocked 把缓冲落盘。调用方必须已持有 dramaFetchLogMu。
func dramaFetchLogFlushLocked() {
	if dramaFetchLogBuf.Len() == 0 || dramaFetchLogFull {
		return
	}
	file := dramaFetchLogHandleLocked()
	if file == nil {
		dramaFetchLogBuf.Reset()
		return
	}
	if dramaFetchLogSize >= dramaFetchLogMaxBytes {
		dramaFetchLogBuf.Reset()
		dramaFetchLogFull = true
		return
	}
	text := dramaFetchLogBuf.String()
	dramaFetchLogBuf.Reset()
	written, err := file.WriteString(text)
	if err != nil {
		return
	}
	dramaFetchLogSize += int64(written)
	dramaFetchLogLast = time.Now()
}

// dramaFetchLogScheduleLocked 给滞留的缓冲挂一个兜底定时器，保证最后几行也能落盘。
func dramaFetchLogScheduleLocked() {
	if dramaFetchLogTimer != nil {
		return
	}
	dramaFetchLogTimer = time.AfterFunc(dramaFetchLogFlushEvery, func() {
		dramaFetchLogMu.Lock()
		defer dramaFetchLogMu.Unlock()
		dramaFetchLogTimer = nil
		dramaFetchLogFlushLocked()
	})
}

// dfLog 记一行日志。args 会以两个空格分隔拼在后面，方便按字段搜索。
func dfLog(scope, message string, args ...any) {
	dramaFetchLogMu.Lock()
	defer dramaFetchLogMu.Unlock()
	if dramaFetchLogFull {
		return
	}
	dramaFetchLogBuf.WriteString(dramaFetchLogFormat(scope, message, args...))
	if dramaFetchLogBuf.Len() >= dramaFetchLogFlushBytes {
		if dramaFetchLogTimer != nil {
			dramaFetchLogTimer.Stop()
			dramaFetchLogTimer = nil
		}
		dramaFetchLogFlushLocked()
		return
	}
	dramaFetchLogScheduleLocked()
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
	// 打开目录前先把缓冲落盘，否则用户看到的日志会缺最后几行
	dramaFetchLogMu.Lock()
	if dramaFetchLogTimer != nil {
		dramaFetchLogTimer.Stop()
		dramaFetchLogTimer = nil
	}
	dramaFetchLogFlushLocked()
	dramaFetchLogMu.Unlock()

	command := exec.Command("explorer", directory)
	if err := command.Start(); err != nil {
		return nil, fmt.Errorf("无法打开日志目录")
	}
	dfLog("日志", "打开日志目录", directory)
	return map[string]any{"opened": true, "path": directory}, nil
}
