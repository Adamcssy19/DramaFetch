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
  /// 大面板（侧边栏、卡片组）圆角。
  static const radiusPanel = 24.0;

  /// 卡片圆角。
  static const radiusCard = 18.0;

  /// 输入框、按钮等控件圆角。
  static const radiusControl = 12.0;

  /// 胶囊（标签、状态点）圆角。
  static const radiusPill = 999.0;

  /// 控件统一高度，保证一屏内所有可点区域手感一致。
  static const controlHeight = 38.0;

  /// 卡片外阴影，比普通 Material 阴影更淡更散，接近玻璃落在桌面上的感觉。
  static const shadowSoft = <BoxShadow>[
    BoxShadow(
      color: Color(0x14101828),
      blurRadius: 18,
      offset: Offset(0, 6),
    ),
  ];

  /// 浮层阴影，比卡片更重一档。
  static const shadowFloat = <BoxShadow>[
    BoxShadow(
      color: Color(0x24101828),
      blurRadius: 34,
      offset: Offset(0, 14),
    ),
  ];

  /// 玻璃高光渐变：左上亮、右下灭，模拟玻璃板受光。
  static const sheen = LinearGradient(
    begin: Alignment.topLeft,
    end: Alignment.bottomRight,
    colors: [Color(0x1FFFFFFF), Color(0x08FFFFFF), Color(0x03FFFFFF)],
    stops: [0.0, 0.45, 1.0],
  );

  /// 强调色渐变（青 → 紫），用于主按钮与选中态。
  static const accentGradient = LinearGradient(
    begin: Alignment.topLeft,
    end: Alignment.bottomRight,
    colors: [Color(0xFF5AC8FA), Color(0xFF7B7BFF), Color(0xFFB06BFF)],
    stops: [0.0, 0.55, 1.0],
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

  /// 深色：玻璃在暗背景上靠高光立起来。
  static const dark = DfPalette(
    brightness: Brightness.dark,
    backdropTop: Color(0xFF0A0C11),
    backdropBottom: Color(0xFF0D1017),
    glowPrimary: Color(0x333D6BFF),
    glowSecondary: Color(0x2E8B5CF6),
    glowTertiary: Color(0x2414B8A6),
    glassFill: Color(0x14FFFFFF),
    glassFillStrong: Color(0x1FFFFFFF),
    glassStroke: Color(0x1FFFFFFF),
    glassSheen: Color(0x1AFFFFFF),
    cardFill: Color(0x10FFFFFF),
    cardFillHover: Color(0x1AFFFFFF),
    cardStroke: Color(0x17FFFFFF),
    cardStrokeHover: Color(0x33FFFFFF),
    panelFill: Color(0x0DFFFFFF),
    controlFill: Color(0x14FFFFFF),
    controlStroke: Color(0x1FFFFFFF),
    surfaceSolid: Color(0xFF14171E),
    surfaceSolidAlt: Color(0xFF1C2029),
    textPrimary: Color(0xFFF2F4F8),
    textSecondary: Color(0xB3E6EAF2),
    textTertiary: Color(0x80A9B2C3),
    accent: Color(0xFF5AC8FA),
    accentAlt: Color(0xFF9B8CFF),
    accentSoft: Color(0x2E5AC8FA),
    divider: Color(0x14FFFFFF),
    danger: Color(0xFFFF6B81),
    success: Color(0xFF4ADE80),
    warning: Color(0xFFFBBF24),
  );

  /// 浅色：玻璃靠白色填充加极淡阴影浮起来。
  static const light = DfPalette(
    brightness: Brightness.light,
    backdropTop: Color(0xFFEFF2F8),
    backdropBottom: Color(0xFFE6EBF5),
    glowPrimary: Color(0x337EA6FF),
    glowSecondary: Color(0x2EB79BFF),
    glowTertiary: Color(0x2690E0D0),
    glassFill: Color(0xB8FFFFFF),
    glassFillStrong: Color(0xE6FFFFFF),
    glassStroke: Color(0x99FFFFFF),
    glassSheen: Color(0x0DFFFFFF),
    cardFill: Color(0xCCFFFFFF),
    cardFillHover: Color(0xF2FFFFFF),
    cardStroke: Color(0xB3FFFFFF),
    cardStrokeHover: Color(0xFFD8DEF0),
    panelFill: Color(0xA6FFFFFF),
    controlFill: Color(0xCCFFFFFF),
    controlStroke: Color(0x99FFFFFF),
    surfaceSolid: Color(0xFFFFFFFF),
    surfaceSolidAlt: Color(0xFFF6F8FC),
    textPrimary: Color(0xFF14161C),
    textSecondary: Color(0xA614161C),
    textTertiary: Color(0x7314161C),
    accent: Color(0xFF1F7AE0),
    accentAlt: Color(0xFF6A5AE0),
    accentSoft: Color(0x1F1F7AE0),
    divider: Color(0x14000000),
    danger: Color(0xFFD92D4B),
    success: Color(0xFF12805C),
    warning: Color(0xFFB4690E),
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
