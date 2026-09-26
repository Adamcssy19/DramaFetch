import 'package:flutter/material.dart';

import 'design/df_design.dart';

/// 顶栏底部的液态玻璃条。
///
/// 作为 [AppBar] 的 `flexibleSpace` 使用：标题与操作按钮浮在它上面。
/// 顶栏是固定不滚动的，模糊只在窗口尺寸变化时重算，成本可控。
class DramaFetchTopBar extends StatelessWidget {
  const DramaFetchTopBar({super.key, this.blur = 16});

  final double blur;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.fromLTRB(12, 10, 12, 0),
      child: DfGlass(
        radius: DfTokens.radiusCard,
        blur: blur,
        padding: const EdgeInsets.symmetric(horizontal: 16),
        child: const SizedBox.expand(),
      ),
    );
  }
}
