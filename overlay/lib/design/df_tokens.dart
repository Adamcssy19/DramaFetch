import 'package:flutter/material.dart';

/// DramaFetch 视觉令牌：卡片式布局 + 液态玻璃。
///
/// ## 性能约定（低配机器优先）
/// 玻璃质感一律用「半透明填充 + 渐变高光描边 + 柔和外阴影」表达，
/// **默认不做背景模糊**。真正开模糊的地方只有三处浮层（侧边栏、顶栏、对话框），
/// 且都包在 [RepaintBoundary] 里，避免滚动时反复重绘。
///
/// 所有颜色、尺寸都是编译期常量，重建时不会重新分配对象。
abstract final class DfTokens {
  /// 大面板（对话框、抽屉）圆角。
  static const radiusPanel = 8.0;

  /// 卡片圆角。
  static const radiusCard = 8.0;

  /// 输入框、按钮等控件圆角。
  static const radiusControl = 4.0;

  /// 原来用于胶囊的圆角，Fluent 里统一成小圆角。
  static const radiusPill = 4.0;

  /// 控件统一高度，与系统设置里的按钮、输入框一致。
  static const controlHeight = 34.0;

  /// 卡片不投影，靠描边分层。
  static const shadowSoft = <BoxShadow>[];

  /// 浮层（对话框、菜单）用一档很轻的阴影。
  static const shadowFloat = <BoxShadow>[
    BoxShadow(color: Color(0x1F000000), blurRadius: 20, offset: Offset(0, 6)),
  ];

  /// 没有玻璃高光。
  static const sheen = LinearGradient(
    colors: [Color(0x00000000), Color(0x00000000)],
  );

  /// 强调色不做渐变，Fluent 的主按钮是纯色。
  static const accentGradient = LinearGradient(
    colors: [Color(0xFF005FB8), Color(0xFF005FB8)],
  );

  static const gapXs = 6.0;
  static const gapSm = 10.0;
  static const gapMd = 16.0;
  static const gapLg = 24.0;
  static const gapXl = 34.0;
}

/// 一套配色的全部取值。深浅两套只差这里的常量，组件本身不判断明暗。
@immutable
class DfPalette {
  const DfPalette({
    required this.brightness,
    required this.backdropTop,
    required this.backdropBottom,
    required this.glowPrimary,
    required this.glowSecondary,
    required this.glowTertiary,
    required this.glassFill,
    required this.glassFillStrong,
    required this.glassStroke,
    required this.glassSheen,
    required this.cardFill,
    required this.cardFillHover,
    required this.cardStroke,
    required this.cardStrokeHover,
    required this.panelFill,
    required this.controlFill,
    required this.controlStroke,
    required this.surfaceSolid,
    required this.surfaceSolidAlt,
    required this.textPrimary,
    required this.textSecondary,
    required this.textTertiary,
    required this.accent,
    required this.accentAlt,
    required this.accentSoft,
    required this.divider,
    required this.danger,
    required this.success,
    required this.warning,
  });

  final Brightness brightness;

  /// 应用底色的上下两端。
  final Color backdropTop;
  final Color backdropBottom;

  /// 背景光斑。三团静态径向渐变，玻璃需要背景有内容才通透。
  final Color glowPrimary;
  final Color glowSecondary;
  final Color glowTertiary;

  /// 玻璃面板填充色。
  final Color glassFill;
  final Color glassFillStrong;

  /// 玻璃描边（1 像素，弱化边框感）。
  final Color glassStroke;

  /// 玻璃内部高光叠加，深色下更强。
  final Color glassSheen;

  /// 卡片填充与悬停填充。
  final Color cardFill;
  final Color cardFillHover;

  /// 卡片描边与悬停描边。
  final Color cardStroke;
  final Color cardStrokeHover;

  /// 侧边栏、顶栏这类固定面板的底色。
  final Color panelFill;

  /// 输入框、次要按钮的底色与描边。
  final Color controlFill;
  final Color controlStroke;

  /// 不透明面板色，给对话框、弹出菜单这类不能透出下层的控件用。
  final Color surfaceSolid;

  /// 次级不透明面板色，用于输入框、列表分组底。
  final Color surfaceSolidAlt;

  final Color textPrimary;
  final Color textSecondary;
  final Color textTertiary;

  final Color accent;
  final Color accentAlt;

  /// 强调色的低透明填充，用于选中态底、标签底。
  final Color accentSoft;

  final Color divider;
  final Color danger;
  final Color success;
  final Color warning;

  /// 深色：Fluent 深色层色，卡片比底色亮一档，靠描边分开。
  static const dark = DfPalette(
    brightness: Brightness.dark,
    backdropTop: Color(0xFF202020),
    backdropBottom: Color(0xFF202020),
    glowPrimary: Color(0x00000000),
    glowSecondary: Color(0x00000000),
    glowTertiary: Color(0x00000000),
    glassFill: Color(0xFF2B2B2B),
    glassFillStrong: Color(0xFF2B2B2B),
    glassStroke: Color(0xFF3A3A3A),
    glassSheen: Color(0x00000000),
    cardFill: Color(0xFF2B2B2B),
    cardFillHover: Color(0xFF333333),
    cardStroke: Color(0xFF3A3A3A),
    cardStrokeHover: Color(0xFF4D4D4D),
    panelFill: Color(0xFF272727),
    controlFill: Color(0xFF2D2D2D),
    controlStroke: Color(0xFF3A3A3A),
    surfaceSolid: Color(0xFF202020),
    surfaceSolidAlt: Color(0xFF2B2B2B),
    textPrimary: Color(0xFFF2F2F2),
    textSecondary: Color(0xFFC3C3C3),
    textTertiary: Color(0xFF8A8A8A),
    accent: Color(0xFF4CC2FF),
    accentAlt: Color(0xFF4CC2FF),
    accentSoft: Color(0x264CC2FF),
    divider: Color(0xFF333333),
    danger: Color(0xFFFF99A4),
    success: Color(0xFF6CCB5F),
    warning: Color(0xFFFCE100),
  );

  /// 浅色：Mica 基色底 + 白卡片。
  static const light = DfPalette(
    brightness: Brightness.light,
    backdropTop: Color(0xFFF3F3F3),
    backdropBottom: Color(0xFFF3F3F3),
    glowPrimary: Color(0x00000000),
    glowSecondary: Color(0x00000000),
    glowTertiary: Color(0x00000000),
    glassFill: Color(0xFFFFFFFF),
    glassFillStrong: Color(0xFFFFFFFF),
    glassStroke: Color(0xFFE5E5E5),
    glassSheen: Color(0x00000000),
    cardFill: Color(0xFFFFFFFF),
    cardFillHover: Color(0xFFF7F7F7),
    cardStroke: Color(0xFFE5E5E5),
    cardStrokeHover: Color(0xFFCFCFCF),
    panelFill: Color(0xFFF3F3F3),
    controlFill: Color(0xFFFFFFFF),
    controlStroke: Color(0xFFD6D6D6),
    surfaceSolid: Color(0xFFFFFFFF),
    surfaceSolidAlt: Color(0xFFF9F9F9),
    textPrimary: Color(0xFF1A1A1A),
    textSecondary: Color(0xFF5D5D5D),
    textTertiary: Color(0xFF8A8A8A),
    accent: Color(0xFF005FB8),
    accentAlt: Color(0xFF005FB8),
    accentSoft: Color(0x1F005FB8),
    divider: Color(0xFFE5E5E5),
    danger: Color(0xFFC42B1C),
    success: Color(0xFF0F7B0F),
    warning: Color(0xFF9D5D00),
  );

  static DfPalette of(BuildContext context) =>
      Theme.of(context).brightness == Brightness.dark ? dark : light;
}

/// 一套排版，卡片式界面里的字号比系统设置略大一点，层级靠颜色拉开。
abstract final class DfText {
  static TextStyle display(DfPalette p) => TextStyle(
    fontSize: 28,
    height: 1.2,
    fontWeight: FontWeight.w700,
    letterSpacing: -0.6,
    color: p.textPrimary,
  );

  static TextStyle title(DfPalette p) => TextStyle(
    fontSize: 20,
    height: 1.25,
    fontWeight: FontWeight.w600,
    letterSpacing: -0.3,
    color: p.textPrimary,
  );

  static TextStyle section(DfPalette p) => TextStyle(
    fontSize: 15,
    height: 1.3,
    fontWeight: FontWeight.w600,
    color: p.textPrimary,
  );

  static TextStyle body(DfPalette p) =>
      TextStyle(fontSize: 14, height: 1.45, color: p.textPrimary);

  static TextStyle caption(DfPalette p) =>
      TextStyle(fontSize: 12, height: 1.4, color: p.textSecondary);

  static TextStyle micro(DfPalette p) =>
      TextStyle(fontSize: 11, height: 1.35, color: p.textTertiary);

  static TextStyle number(DfPalette p) => TextStyle(
    fontSize: 22,
    height: 1.1,
    fontWeight: FontWeight.w700,
    letterSpacing: -0.2,
    color: p.textPrimary,
  );
}
