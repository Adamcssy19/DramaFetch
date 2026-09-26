import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

/// Windows 11 / WinUI 3 风格主题。
///
/// 取值参考 Windows 11 的设计语言：
/// - 底色用 Mica 基色（浅色 #F3F3F3 / 深色 #202020）
/// - 内容分层用卡片色配细描边，不用阴影
/// - 强调色用系统默认蓝（浅色 #005FB8 / 深色 #60CDFF）
/// - 控件圆角 4 像素，卡片与浮层圆角 8 像素
/// - 字体用 Segoe UI 变量字体，控件高度统一 32 像素
abstract final class AppTheme {
  static const accentLight = Color(0xFF005FB8);
  static const accentDark = Color(0xFF60CDFF);

  static const radiusControl = 4.0;
  static const radiusCard = 8.0;

  /// 控件统一高度，与系统设置里的按钮、输入框一致。
  static const controlHeight = 32.0;

  static const _fontFamily = 'Segoe UI Variable Text';
  static const _fontFamilyFallback = ['Segoe UI', 'Microsoft YaHei UI'];

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

  /// 页面主标题，对应系统里的标题文字（28 像素、半粗）。
  static TextStyle title(BuildContext context) {
    final base = Theme.of(context).textTheme.headlineSmall;
    return (base ?? const TextStyle()).copyWith(
      fontSize: 26,
      height: 1.25,
      fontWeight: FontWeight.w600,
      letterSpacing: -0.3,
      color: Theme.of(context).colorScheme.onSurface,
    );
  }

  /// 区块标题（20 像素、半粗）。
  static TextStyle section(BuildContext context) {
    final base = Theme.of(context).textTheme.titleMedium;
    return (base ?? const TextStyle()).copyWith(
      fontSize: 16,
      height: 1.35,
      fontWeight: FontWeight.w600,
      color: Theme.of(context).colorScheme.onSurface,
    );
  }

  /// 次要说明文字。
  static TextStyle caption(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return TextStyle(fontSize: 12, height: 1.4, color: scheme.onSurfaceVariant);
  }

  static ThemeData _theme(Brightness brightness) {
    final dark = brightness == Brightness.dark;

    // Windows 11 的层色
    final base = dark ? const Color(0xFF202020) : const Color(0xFFF3F3F3);
    final card = dark ? const Color(0xFF2B2B2B) : Colors.white;
    final layerAlt = dark ? const Color(0xFF272727) : const Color(0xFFEAEAEA);
    final subtleHover = dark
        ? const Color(0xFF2E2E2E)
        : const Color(0xFFEDEDED);
    final controlFill = dark ? const Color(0xFF2D2D2D) : Colors.white;
    final stroke = dark ? const Color(0xFF333333) : const Color(0xFFE0E0E0);

    final scheme = ColorScheme.fromSeed(
      seedColor: accentLight,
      brightness: brightness,
      primary: dark ? accentDark : accentLight,
      onPrimary: dark ? const Color(0xFF003E66) : Colors.white,
      primaryContainer: dark
          ? const Color(0xFF004578)
          : const Color(0xFFCFE4FF),
      onPrimaryContainer: dark
          ? const Color(0xFFCFE4FF)
          : const Color(0xFF001C38),
      secondary: dark ? const Color(0xFF9A9A9A) : const Color(0xFF5C5C5C),
      onSecondary: dark ? const Color(0xFF1A1A1A) : Colors.white,
      tertiary: dark ? const Color(0xFFB4C7E7) : const Color(0xFF3A5A9B),
      surface: card,
      onSurface: dark ? const Color(0xFFF2F2F2) : const Color(0xFF1A1A1A),
      onSurfaceVariant: dark
          ? const Color(0xFFC3C3C3)
          : const Color(0xFF5D5D5D),
      outline: stroke,
      outlineVariant: dark ? const Color(0xFF313131) : const Color(0xFFE8E8E8),
      surfaceContainerLowest: dark
          ? const Color(0xFF1B1B1B)
          : const Color(0xFFFFFFFF),
      surfaceContainerLow: dark
          ? const Color(0xFF232323)
          : const Color(0xFFF9F9F9),
      surfaceContainer: dark ? const Color(0xFF272727) : const Color(0xFFF6F6F6),
      surfaceContainerHigh: dark
          ? const Color(0xFF2C2C2C)
          : const Color(0xFFF1F1F1),
      surfaceContainerHighest: dark
          ? const Color(0xFF333333)
          : const Color(0xFFEAEAEA),
      surfaceTint: Colors.transparent,
    );

    final controlShape = RoundedRectangleBorder(
      borderRadius: BorderRadius.circular(radiusControl),
    );
    final cardShape = RoundedRectangleBorder(
      borderRadius: BorderRadius.circular(radiusCard),
      side: BorderSide(color: scheme.outlineVariant),
    );

    // 文字层级按系统设置的类型渐变：正文 14、标题 20/28
    final textTheme = TextTheme(
      displaySmall: TextStyle(
        fontSize: 32,
        height: 1.2,
        fontWeight: FontWeight.w600,
        letterSpacing: -0.5,
        color: scheme.onSurface,
      ),
      headlineSmall: TextStyle(
        fontSize: 26,
        height: 1.25,
        fontWeight: FontWeight.w600,
        letterSpacing: -0.3,
        color: scheme.onSurface,
      ),
      titleLarge: TextStyle(
        fontSize: 20,
        height: 1.3,
        fontWeight: FontWeight.w600,
        color: scheme.onSurface,
      ),
      titleMedium: TextStyle(
        fontSize: 16,
        height: 1.35,
        fontWeight: FontWeight.w600,
        color: scheme.onSurface,
      ),
      titleSmall: TextStyle(
        fontSize: 14,
        height: 1.4,
        fontWeight: FontWeight.w600,
        color: scheme.onSurface,
      ),
      bodyLarge: TextStyle(fontSize: 15, height: 1.5, color: scheme.onSurface),
      bodyMedium: TextStyle(fontSize: 14, height: 1.45, color: scheme.onSurface),
      bodySmall: TextStyle(
        fontSize: 12,
        height: 1.4,
        color: scheme.onSurfaceVariant,
      ),
      labelLarge: TextStyle(
        fontSize: 14,
        height: 1.4,
        fontWeight: FontWeight.w500,
        color: scheme.onSurface,
      ),
      labelMedium: TextStyle(
        fontSize: 12,
        height: 1.35,
        color: scheme.onSurfaceVariant,
      ),
      labelSmall: TextStyle(
        fontSize: 11,
        height: 1.35,
        color: scheme.onSurfaceVariant,
      ),
    );

    return ThemeData(
      useMaterial3: true,
      brightness: brightness,
      colorScheme: scheme,
      textTheme: textTheme,
      fontFamily: _fontFamily,
      fontFamilyFallback: _fontFamilyFallback,
      scaffoldBackgroundColor: base,
      splashFactory: NoSplash.splashFactory,
      highlightColor: Colors.transparent,
      hoverColor: subtleHover,
      focusColor: Colors.transparent,
      // Windows 应用不做页面切换动画
      pageTransitionsTheme: const PageTransitionsTheme(
        builders: {
          TargetPlatform.windows: _InstantPageTransitionsBuilder(),
          TargetPlatform.macOS: _InstantPageTransitionsBuilder(),
          TargetPlatform.linux: _InstantPageTransitionsBuilder(),
        },
      ),
      appBarTheme: AppBarTheme(
        backgroundColor: base,
        foregroundColor: scheme.onSurface,
        surfaceTintColor: Colors.transparent,
        scrolledUnderElevation: 0,
        elevation: 0,
        centerTitle: false,
        titleSpacing: 16,
        titleTextStyle: TextStyle(
          fontFamily: _fontFamily,
          fontFamilyFallback: _fontFamilyFallback,
          fontSize: 15,
          fontWeight: FontWeight.w600,
          color: scheme.onSurface,
        ),
        systemOverlayStyle: systemBars(brightness),
      ),
      dividerTheme: DividerThemeData(
        color: scheme.outlineVariant,
        thickness: 1,
        space: 1,
      ),
      iconTheme: IconThemeData(color: scheme.onSurfaceVariant, size: 18),
      inputDecorationTheme: InputDecorationTheme(
        filled: true,
        fillColor: controlFill,
        hintStyle: TextStyle(color: scheme.onSurfaceVariant, fontSize: 14),
        contentPadding: const EdgeInsets.symmetric(
          horizontal: 12,
          vertical: 10,
        ),
        constraints: const BoxConstraints(minHeight: controlHeight),
        border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(radiusControl),
          borderSide: BorderSide(color: scheme.outlineVariant),
        ),
        enabledBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(radiusControl),
          borderSide: BorderSide(color: scheme.outlineVariant),
        ),
        focusedBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(radiusControl),
          borderSide: BorderSide(color: scheme.primary, width: 2),
        ),
      ),
      filledButtonTheme: FilledButtonThemeData(
        style: FilledButton.styleFrom(
          shape: controlShape,
          minimumSize: const Size(0, controlHeight),
          padding: const EdgeInsets.symmetric(horizontal: 14),
          textStyle: const TextStyle(fontSize: 14, fontWeight: FontWeight.w500),
        ),
      ),
      elevatedButtonTheme: ElevatedButtonThemeData(
        style: ElevatedButton.styleFrom(
          shape: controlShape,
          elevation: 0,
          minimumSize: const Size(0, controlHeight),
          backgroundColor: controlFill,
          foregroundColor: scheme.onSurface,
          side: BorderSide(color: scheme.outlineVariant),
          padding: const EdgeInsets.symmetric(horizontal: 14),
          textStyle: const TextStyle(fontSize: 14, fontWeight: FontWeight.w500),
        ),
      ),
      outlinedButtonTheme: OutlinedButtonThemeData(
        style: OutlinedButton.styleFrom(
          shape: controlShape,
          minimumSize: const Size(0, controlHeight),
          side: BorderSide(color: scheme.outline),
          padding: const EdgeInsets.symmetric(horizontal: 14),
          textStyle: const TextStyle(fontSize: 14, fontWeight: FontWeight.w500),
        ),
      ),
      textButtonTheme: TextButtonThemeData(
        style: TextButton.styleFrom(
          shape: controlShape,
          minimumSize: const Size(0, controlHeight),
          padding: const EdgeInsets.symmetric(horizontal: 10),
          textStyle: const TextStyle(fontSize: 14, fontWeight: FontWeight.w500),
        ),
      ),
      iconButtonTheme: IconButtonThemeData(
        style: IconButton.styleFrom(
          shape: controlShape,
          minimumSize: const Size(32, controlHeight),
          highlightColor: subtleHover,
        ),
      ),
      snackBarTheme: SnackBarThemeData(
        behavior: SnackBarBehavior.floating,
        backgroundColor: dark ? const Color(0xFF2D2D2D) : const Color(0xFFF0F0F0),
        contentTextStyle: TextStyle(color: scheme.onSurface, fontSize: 14),
        shape: cardShape,
      ),
      cardTheme: CardThemeData(
        elevation: 0,
        color: card,
        surfaceTintColor: Colors.transparent,
        margin: EdgeInsets.zero,
        shape: cardShape,
      ),
      dialogTheme: DialogThemeData(
        backgroundColor: dark ? const Color(0xFF2B2B2B) : const Color(0xFFF9F9F9),
        surfaceTintColor: Colors.transparent,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(radiusCard),
        ),
        titleTextStyle: TextStyle(
          fontFamily: _fontFamily,
          fontFamilyFallback: _fontFamilyFallback,
          fontSize: 20,
          fontWeight: FontWeight.w600,
          color: scheme.onSurface,
        ),
      ),
      bottomSheetTheme: BottomSheetThemeData(
        backgroundColor: dark ? const Color(0xFF2B2B2B) : const Color(0xFFF9F9F9),
        surfaceTintColor: Colors.transparent,
        shape: const RoundedRectangleBorder(
          borderRadius: BorderRadius.vertical(top: Radius.circular(8)),
        ),
      ),
      listTileTheme: ListTileThemeData(
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(radiusControl),
        ),
        minVerticalPadding: 10,
        titleTextStyle: TextStyle(
          fontSize: 14,
          fontWeight: FontWeight.w500,
          color: scheme.onSurface,
        ),
        subtitleTextStyle: TextStyle(
          fontSize: 12,
          color: scheme.onSurfaceVariant,
        ),
        iconColor: scheme.onSurfaceVariant,
      ),
      chipTheme: ChipThemeData(
        backgroundColor: layerAlt,
        side: BorderSide(color: scheme.outlineVariant),
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(radiusControl),
        ),
        labelStyle: TextStyle(color: scheme.onSurface, fontSize: 13),
        padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
      ),
      // 悬停与选中用系统里的浅色底，不做发光
      popupMenuTheme: PopupMenuThemeData(
        color: dark ? const Color(0xFF2B2B2B) : const Color(0xFFF9F9F9),
        surfaceTintColor: Colors.transparent,
        elevation: 8,
        shape: cardShape,
        textStyle: TextStyle(fontSize: 14, color: scheme.onSurface),
      ),
      tooltipTheme: TooltipThemeData(
        decoration: BoxDecoration(
          color: dark ? const Color(0xFF2D2D2D) : const Color(0xFFF9F9F9),
          borderRadius: BorderRadius.circular(radiusControl),
          border: Border.all(color: scheme.outlineVariant),
        ),
        textStyle: TextStyle(fontSize: 12, color: scheme.onSurface),
        waitDuration: const Duration(milliseconds: 500),
      ),
      scrollbarTheme: ScrollbarThemeData(
        thickness: const WidgetStatePropertyAll(10),
        radius: const Radius.circular(5),
        thumbColor: WidgetStatePropertyAll(
          dark ? const Color(0x66FFFFFF) : const Color(0x66000000),
        ),
        crossAxisMargin: 2,
      ),
      progressIndicatorTheme: ProgressIndicatorThemeData(
        color: scheme.primary,
        linearMinHeight: 3,
      ),
    );
  }
}

/// 页面切换不做动画，符合 Windows 应用的观感。
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
