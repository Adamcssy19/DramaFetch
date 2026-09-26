/// 本项目新增：红果取流方式清单。
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
    '依次尝试 App 直连、网页解析、备用接口，成功即用',
  ),
  DownloadMethodOption(
    'app',
    'App 直连',
    '走红果 App 接口取原画直链，画质最好；接口调整时可能失效',
  ),
  DownloadMethodOption(
    'web',
    '网页解析',
    '解析红果播放页取流，部分剧集可能只允许试看',
  ),
  DownloadMethodOption(
    'backup',
    '备用接口',
    'App 与网页都不可用时的兜底通道',
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
