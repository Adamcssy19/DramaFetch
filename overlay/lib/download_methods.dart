/// 本项目新增：下载渠道清单。
///
/// 与 native/core/dramafetch_direct.go 里的 downloadMethodOptions 保持一致，改动时两边同步。
library;

class DownloadMethodOption {
  const DownloadMethodOption(this.id, this.name, this.detail);
  final String id;
  final String name;
  final String detail;
}

const downloadMethodOptions = <DownloadMethodOption>[
  DownloadMethodOption(
    'auto',
    '自动择优',
    '下载前先测各渠道的可用性与延迟，从最快的开始试',
  ),
  DownloadMethodOption(
    'app',
    '应用接口',
    '走应用接口取原画直链，画质最好；接口调整时可能失效',
  ),
  DownloadMethodOption(
    'web',
    '网页解析',
    '解析播放页取流，部分剧集可能只允许试看',
  ),
  DownloadMethodOption(
    'backup',
    '备用接口',
    '前两个都不可用时的兜底通道',
  ),
];

/// 把后端返回的值收敛到合法范围，未知值一律按自动处理。
String downloadMethodFromJson(Object? value) {
  final id = value is String ? value.trim() : '';
  for (final option in downloadMethodOptions) {
    if (option.id == id) return id;
  }
  return 'auto';
}

DownloadMethodOption downloadMethodOf(String id) =>
    downloadMethodOptions.firstWhere(
      (option) => option.id == id,
      orElse: () => downloadMethodOptions.first,
    );
