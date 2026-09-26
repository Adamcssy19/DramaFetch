package core

// 本项目新增：下载文件与文件夹的命名规则。
//
// 目标是把下载结果整理成能直接浏览的结构：
//     下载目录/剧名/剧名 001.mp4
// 剧名与集号都来自任务本身，不再使用内部编号，方便直接在资源管理器里查看与整理。

import (
	"fmt"
	"strings"
)

// nativeSafeName 把剧名里不适合作为文件名的字符替换成空格，并限制长度。
func nativeSafeName(raw string) string {
	name := strings.TrimSpace(raw)
	if name == "" {
		return ""
	}
	replacer := strings.NewReplacer(
		"\\", " ", "/", " ", ":", " ", "*", " ", "?", " ",
		"\"", " ", "<", " ", ">", " ", "|", " ",
		"\n", " ", "\r", " ", "\t", " ",
	)
	name = strings.Join(strings.Fields(replacer.Replace(name)), " ")
	name = strings.Trim(name, " .")
	runes := []rune(name)
	if len(runes) > 80 {
		name = strings.Trim(string(runes[:80]), " .")
	}
	return name
}

// nativeDownloadFolderName 返回该任务归档到的文件夹名，取剧名。
func nativeDownloadFolderName(job nativeDownloadJob) string {
	return nativeSafeName(job.Drama.Title)
}

// nativeDownloadFileName 返回下载文件名，形如「剧名 001.mp4」。
func nativeDownloadFileName(job nativeDownloadJob) string {
	number := job.Index
	if number <= 0 {
		number = 1
	}
	title := nativeSafeName(job.Drama.Title)
	if title == "" {
		return fmt.Sprintf("%03d.mp4", number)
	}
	return fmt.Sprintf("%s %03d.mp4", title, number)
}
