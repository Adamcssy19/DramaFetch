import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import 'design/df_tokens.dart';

/// DramaFetch 主题：卡片式布局 + 液态玻璃。
///
/// 这一层是**全局换肤的入口** —— 上游几十个页面都直接读 [ThemeData] 与
/// [ColorScheme]，把卡片、对话框、列表项、输入框、按钮的形状与玻璃色在这里统一改掉，
/// 那些页面不用逐页改代码就能跟着变。
///
/// ## 性能
/// 全局不开背景模糊：卡片用半透明填充加细描边表达玻璃感即可。
/// 真正需要模糊的只有侧边栏、顶栏、对话框三处，各自由页面自己用 `DfGlass(blur:)` 控制。
abstract final class AppTheme {
  /// 控件圆角，与 [DfTokens] 保持一致。
  static const radiusControl = DfTokens.radiusControl;

  /// 卡片圆角。
  static const radiusCard = DfTokens.radiusCard;

  /// 大面板圆角。
  static const radiusPanel = DfTokens.radiusPanel;

  /// 控件统一高度。
  static const controlHeight = DfTokens.controlHeight;

  static const _fontFamily = 'Microsoft YaHei UI';
  static const _fontFamilyFallback = [
    'Segoe UI Variable Text',
    'Segoe UI',
    'PingFang SC',
  ];

  static final light = _theme(Brightness.light);
  static final dark = _theme(Brightness.dark);

  static ThemeMode mode(String preference) => switch (preference) {
    'light' => ThemeMode.light,
    'dark' => ThemeMode.dark,
    _ => ThemeMode.system,
  };

  static String label(String preference) => switch (preference) {
    'light' => '浅色',
    'dark' => '深色',
    _ => '跟随系统',
  };

  static SystemUiOverlayStyle systemBars(Brightness brightness) {
    final icons = brightness == Brightness.dark
        ? Brightness.light
        : Brightness.dark;
    return SystemUiOverlayStyle(
      statusBarColor: Colors.transparent,
      statusBarIconBrightness: icons,
      statusBarBrightness: brightness,
      systemStatusBarContrastEnforced: false,
      systemNavigationBarColor: Colors.transparent,
      systemNavigationBarDividerColor: Colors.transparent,
      systemNavigationBarIconBrightness: icons,
      systemNavigationBarContrastEnforced: false,
    );
  }

  /// 页面主标题。
  static TextStyle title(BuildContext context) =>
      DfText.display(DfPalette.of(context));

  /// 区块标题。
  static TextStyle section(BuildContext context) =>
      DfText.section(DfPalette.of(context));

  /// 次要说明文字。
  static TextStyle caption(BuildContext context) =>
      DfText.caption(DfPalette.of(context));

  static ThemeData _theme(Brightness brightness) {
    final dark = brightness == Brightness.dark;
    final p = dark ? DfPalette.dark : DfPalette.light;

    final scheme =
        ColorScheme.fromSeed(
          seedColor: p.accent,
          brightness: brightness,
        ).copyWith(
          primary: p.accent,
          onPrimary: dark ? const Color(0xFF04121C) : Colors.white,
          primaryContainer: p.accentSoft,
          onPrimaryContainer: p.textPrimary,
          secondary: p.accentAlt,
          onSecondary: dark ? const Color(0xFF0B0A18) : Colors.white,
          tertiary: p.accentAlt,
          onTertiary: dark ? const Color(0xFF0B0A18) : Colors.white,
          error: p.danger,
          onError: dark ? const Color(0xFF20060B) : Colors.white,
          surface: p.surfaceSolid,
          onSurface: p.textPrimary,
          onSurfaceVariant: p.textSecondary,
          surfaceTint: Colors.transparent,
          outline: p.cardStroke,
          outlineVariant: p.divider,
          surfaceContainerLowest: p.surfaceSolid,
          surfaceContainerLow: p.surfaceSolid,
          surfaceContainer: p.surfaceSolidAlt,
          surfaceContainerHigh: p.surfaceSolidAlt,
          surfaceContainerHighest: p.controlFill,
          shadow: const Color(0x33101828),
          scrim: const Color(0x99000000),
        );

    final pillShape = RoundedRectangleBorder(
      borderRadius: BorderRadius.circular(DfTokens.radiusPill),
    );
    final cardShape = RoundedRectangleBorder(
      borderRadius: BorderRadius.circular(DfTokens.radiusCard),
      side: BorderSide(color: p.cardStroke),
    );

    final textTheme = TextTheme(
      displaySmall: DfText.display(p),
      headlineSmall: DfText.display(p),
      titleLarge: DfText.title(p),
      titleMedium: DfText.section(p),
      titleSmall: TextStyle(
        fontSize: 13.5,
        height: 1.4,
        fontWeight: FontWeight.w600,
        color: p.textPrimary,
      ),
      bodyLarge: TextStyle(fontSize: 15, height: 1.5, color: p.textPrimary),
      bodyMedium: DfText.body(p),
      bodySmall: DfText.caption(p),
      labelLarge: TextStyle(
        fontSize: 13.5,
        height: 1.4,
        fontWeight: FontWeight.w600,
        color: p.textPrimary,
      ),
      labelMedium: DfText.micro(p),
      labelSmall: DfText.micro(p),
    );

    return ThemeData(
      useMaterial3: true,
      brightness: brightness,
      colorScheme: scheme,
      textTheme: textTheme,
      fontFamily: _fontFamily,
      fontFamilyFallback: _fontFamilyFallback,
      // 背景交给 DfBackdrop 画渐变与光斑，页面自己保持透明
      scaffoldBackgroundColor: Colors.transparent,
      canvasColor: Colors.transparent,
      splashFactory: NoSplash.splashFactory,
      highlightColor: Colors.transparent,
      hoverColor: p.cardFillHover,
      focusColor: Colors.transparent,
      // 桌面应用不做页面切换动画，省一次全屏合成
      pageTransitionsTheme: const PageTransitionsTheme(
        builders: {
          TargetPlatform.windows: _InstantPageTransitionsBuilder(),
          TargetPlatform.macOS: _InstantPageTransitionsBuilder(),
          TargetPlatform.linux: _InstantPageTransitionsBuilder(),
        },
      ),
      appBarTheme: AppBarTheme(
        backgroundColor: Colors.transparent,
        foregroundColor: p.textPrimary,
        surfaceTintColor: Colors.transparent,
        scrolledUnderElevation: 0,
        elevation: 0,
        centerTitle: false,
        titleSpacing: 18,
        titleTextStyle: TextStyle(
          fontFamily: _fontFamily,
          fontFamilyFallback: _fontFamilyFallback,
          fontSize: 15,
          fontWeight: FontWeight.w600,
          color: p.textPrimary,
        ),
        systemOverlayStyle: systemBars(brightness),
      ),
      dividerTheme: DividerThemeData(
        color: p.divider,
        thickness: 1,
        space: 1,
      ),
      iconTheme: IconThemeData(color: p.textSecondary, size: 18),
      inputDecorationTheme: InputDecorationTheme(
        filled: true,
        fillColor: p.controlFill,
        hintStyle: TextStyle(color: p.textTertiary, fontSize: 14),
        contentPadding: const EdgeInsets.symmetric(
          horizontal: 14,
          vertical: 10,
        ),
        constraints: const BoxConstraints(minHeight: DfTokens.controlHeight),
        border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(DfTokens.radiusControl),
          borderSide: BorderSide(color: p.controlStroke),
        ),
        enabledBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(DfTokens.radiusControl),
          borderSide: BorderSide(color: p.controlStroke),
        ),
        focusedBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(DfTokens.radiusControl),
          borderSide: BorderSide(
            color: p.accent.withValues(alpha: 0.75),
            width: 1.5,
          ),
        ),
      ),
      filledButtonTheme: FilledButtonThemeData(
        style: FilledButton.styleFrom(
          shape: pillShape,
          minimumSize: const Size(0, DfTokens.controlHeight),
          padding: const EdgeInsets.symmetric(horizontal: 18),
          textStyle: const TextStyle(fontSize: 13.5, fontWeight: FontWeight.w600),
        ),
      ),
      elevatedButtonTheme: ElevatedButtonThemeData(
        style: ElevatedButton.styleFrom(
          shape: pillShape,
          elevation: 0,
          minimumSize: const Size(0, DfTokens.controlHeight),
          backgroundColor: p.controlFill,
          foregroundColor: p.textPrimary,
          side: BorderSide(color: p.controlStroke),
          padding: const EdgeInsets.symmetric(horizontal: 16),
          textStyle: const TextStyle(fontSize: 13.5, fontWeight: FontWeight.w500),
        ),
      ),
      outlinedButtonTheme: OutlinedButtonThemeData(
        style: OutlinedButton.styleFrom(
          shape: pillShape,
          minimumSize: const Size(0, DfTokens.controlHeight),
          side: BorderSide(color: p.controlStroke),
          foregroundColor: p.textPrimary,
          padding: const EdgeInsets.symmetric(horizontal: 16),
          textStyle: const TextStyle(fontSize: 13.5, fontWeight: FontWeight.w500),
        ),
      ),
      textButtonTheme: TextButtonThemeData(
        style: TextButton.styleFrom(
          shape: pillShape,
          minimumSize: const Size(0, DfTokens.controlHeight),
          foregroundColor: p.accent,
          padding: const EdgeInsets.symmetric(horizontal: 12),
          textStyle: const TextStyle(fontSize: 13.5, fontWeight: FontWeight.w500),
        ),
      ),
      iconButtonTheme: IconButtonThemeData(
        style: IconButton.styleFrom(
          shape: const CircleBorder(),
          minimumSize: const Size(34, 34),
          foregroundColor: p.textSecondary,
          highlightColor: p.cardFillHover,
        ),
      ),
      snackBarTheme: SnackBarThemeData(
        behavior: SnackBarBehavior.floating,
        backgroundColor: p.surfaceSolidAlt,
        contentTextStyle: TextStyle(color: p.textPrimary, fontSize: 13.5),
        actionTextColor: p.accent,
        elevation: 0,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(DfTokens.radiusControl),
          side: BorderSide(color: p.cardStroke),
        ),
      ),
      cardTheme: CardThemeData(
        elevation: 0,
        color: p.cardFill,
        surfaceTintColor: Colors.transparent,
        margin: EdgeInsets.zero,
        shape: cardShape,
      ),
      dialogTheme: DialogThemeData(
        backgroundColor: p.surfaceSolid,
        surfaceTintColor: Colors.transparent,
        elevation: 0,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(DfTokens.radiusPanel),
          side: BorderSide(color: p.cardStroke),
        ),
        titleTextStyle: TextStyle(
          fontFamily: _fontFamily,
          fontFamilyFallback: _fontFamilyFallback,
          fontSize: 19,
          fontWeight: FontWeight.w600,
          color: p.textPrimary,
        ),
        contentTextStyle: TextStyle(
          fontFamily: _fontFamily,
          fontFamilyFallback: _fontFamilyFallback,
          fontSize: 14,
          height: 1.5,
          color: p.textSecondary,
        ),
      ),
      bottomSheetTheme: BottomSheetThemeData(
        backgroundColor: p.surfaceSolid,
        surfaceTintColor: Colors.transparent,
        elevation: 0,
        shape: const RoundedRectangleBorder(
          borderRadius: BorderRadius.vertical(
            top: Radius.circular(DfTokens.radiusPanel),
          ),
        ),
      ),
      listTileTheme: ListTileThemeData(
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(DfTokens.radiusControl),
        ),
        minVerticalPadding: 10,
        iconColor: p.textSecondary,
        titleTextStyle: TextStyle(
          fontSize: 13.5,
          fontWeight: FontWeight.w500,
          color: p.textPrimary,
        ),
        subtitleTextStyle: TextStyle(fontSize: 12, color: p.textSecondary),
      ),
      chipTheme: ChipThemeData(
        backgroundColor: p.controlFill,
        selectedColor: p.accentSoft,
        side: BorderSide(color: p.controlStroke),
        shape: const StadiumBorder(),
        labelStyle: TextStyle(color: p.textSecondary, fontSize: 12.5),
        secondaryLabelStyle: TextStyle(color: p.accent, fontSize: 12.5),
        padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 2),
      ),
      popupMenuTheme: PopupMenuThemeData(
        color: p.surfaceSolid,
        surfaceTintColor: Colors.transparent,
        elevation: 0,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(DfTokens.radiusControl),
          side: BorderSide(color: p.cardStroke),
        ),
        textStyle: TextStyle(fontSize: 13.5, color: p.textPrimary),
      ),
      tooltipTheme: TooltipThemeData(
        decoration: BoxDecoration(
          color: p.surfaceSolidAlt,
          borderRadius: BorderRadius.circular(8),
          border: Border.all(color: p.cardStroke),
        ),
        textStyle: TextStyle(fontSize: 12, color: p.textPrimary),
        waitDuration: const Duration(milliseconds: 500),
      ),
      scrollbarTheme: ScrollbarThemeData(
        thickness: const WidgetStatePropertyAll(8),
        radius: const Radius.circular(4),
        thumbColor: WidgetStatePropertyAll(p.textTertiary.withValues(alpha: 0.5)),
        crossAxisMargin: 2,
      ),
      progressIndicatorTheme: ProgressIndicatorThemeData(
        color: p.accent,
        linearMinHeight: 4,
        linearTrackColor: p.divider,
      ),
      sliderTheme: SliderThemeData(
        activeTrackColor: p.accent,
        inactiveTrackColor: p.divider,
        thumbColor: p.accent,
        overlayColor: p.accentSoft,
        trackHeight: 4,
      ),
      switchTheme: SwitchThemeData(
        thumbColor: WidgetStateProperty.resolveWith(
          (states) => states.contains(WidgetState.selected)
              ? Colors.white
              : p.textTertiary,
        ),
        trackColor: WidgetStateProperty.resolveWith(
          (states) => states.contains(WidgetState.selected)
              ? p.accent
              : p.controlFill,
        ),
        trackOutlineColor: WidgetStatePropertyAll(p.controlStroke),
      ),
      dropdownMenuTheme: DropdownMenuThemeData(
        menuStyle: MenuStyle(
          backgroundColor: WidgetStatePropertyAll(p.surfaceSolid),
          surfaceTintColor: const WidgetStatePropertyAll(Colors.transparent),
          shape: WidgetStatePropertyAll(
            RoundedRectangleBorder(
              borderRadius: BorderRadius.circular(DfTokens.radiusControl),
              side: BorderSide(color: p.cardStroke),
            ),
          ),
        ),
      ),
      checkboxTheme: CheckboxThemeData(
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(5)),
        side: BorderSide(color: p.controlStroke, width: 1.4),
        fillColor: WidgetStateProperty.resolveWith(
          (states) => states.contains(WidgetState.selected)
              ? p.accent
              : Colors.transparent,
        ),
        checkColor: WidgetStatePropertyAll(
          dark ? const Color(0xFF04121C) : Colors.white,
        ),
      ),
    );
  }
}

/// 页面切换不做动画，符合桌面应用的观感。
class _InstantPageTransitionsBuilder extends PageTransitionsBuilder {
  const _InstantPageTransitionsBuilder();

  @override
  Widget buildTransitions<T>(
    PageRoute<T> route,
    BuildContext context,
    Animation<double> animation,
    Animation<double> secondaryAnimation,
    Widget child,
  ) => child;
}
