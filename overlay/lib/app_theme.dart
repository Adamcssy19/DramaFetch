import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

/// WinUI 3（Fluent Design）风格主题。
///
/// 取色与圆角参考 Windows 11 的设计语言：
/// - 底色使用 Mica 基色（浅色 #F3F3F3 / 深色 #202020）
/// - 内容分层用卡片色（浅色 #FFFFFF / 深色 #2B2B2B）配细描边
/// - 强调色用系统默认蓝（浅色 #005FB8 / 深色 #60CDFF）
/// - 控件圆角 4 像素，卡片与图层圆角 8 像素
abstract final class AppTheme {
  static const accentLight = Color(0xFF005FB8);
  static const accentDark = Color(0xFF60CDFF);

  static const radiusControl = 4.0;
  static const radiusCard = 8.0;

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

  static ThemeData _theme(Brightness brightness) {
    final dark = brightness == Brightness.dark;
    final background = dark ? const Color(0xFF202020) : const Color(0xFFF3F3F3);
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
      surface: dark ? const Color(0xFF2B2B2B) : Colors.white,
      onSurface: dark ? const Color(0xFFE8E8E8) : const Color(0xFF1A1A1A),
      onSurfaceVariant: dark ? const Color(0xFF9A9A9A) : const Color(0xFF646464),
      outline: dark ? const Color(0xFF3A3A3A) : const Color(0xFFD6D6D6),
      outlineVariant: dark ? const Color(0xFF313131) : const Color(0xFFE5E5E5),
      surfaceContainerLowest: dark
          ? const Color(0xFF1A1A1A)
          : const Color(0xFFFFFFFF),
      surfaceContainerLow: dark
          ? const Color(0xFF232323)
          : const Color(0xFFF9F9F9),
      surfaceContainer: dark ? const Color(0xFF272727) : const Color(0xFFF6F6F6),
      surfaceContainerHigh: dark
          ? const Color(0xFF2E2E2E)
          : const Color(0xFFF0F0F0),
      surfaceContainerHighest: dark
          ? const Color(0xFF353535)
          : const Color(0xFFEAEAEA),
      surfaceTint: Colors.transparent,
    );

    // WinUI 按钮：矩形小圆角、无阴影、按下时底色压暗
    final controlShape = RoundedRectangleBorder(
      borderRadius: BorderRadius.circular(radiusControl),
    );

    return ThemeData(
      useMaterial3: true,
      brightness: brightness,
      colorScheme: scheme,
      scaffoldBackgroundColor: background,
      splashFactory: NoSplash.splashFactory,
      appBarTheme: AppBarTheme(
        backgroundColor: background,
        foregroundColor: scheme.onSurface,
        scrolledUnderElevation: 0,
        elevation: 0,
        centerTitle: false,
        systemOverlayStyle: systemBars(brightness),
      ),
      dividerTheme: DividerThemeData(
        color: scheme.outlineVariant,
        thickness: 1,
        space: 1,
      ),
      navigationRailTheme: NavigationRailThemeData(
        backgroundColor: background,
        useIndicator: true,
        indicatorColor: dark
            ? const Color(0xFF2D2D2D)
            : const Color(0xFFE8F0FA),
        indicatorShape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(radiusCard),
        ),
        selectedIconTheme: IconThemeData(color: scheme.primary),
        unselectedIconTheme: IconThemeData(color: scheme.onSurfaceVariant),
        selectedLabelTextStyle: TextStyle(
          color: scheme.primary,
          fontWeight: FontWeight.w600,
        ),
        unselectedLabelTextStyle: TextStyle(color: scheme.onSurfaceVariant),
      ),
      inputDecorationTheme: InputDecorationTheme(
        filled: true,
        fillColor: dark ? const Color(0xFF2D2D2D) : const Color(0xFFFFFFFF),
        hintStyle: TextStyle(color: scheme.onSurfaceVariant),
        contentPadding: const EdgeInsets.symmetric(
          horizontal: 12,
          vertical: 10,
        ),
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
          padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
          textStyle: const TextStyle(fontWeight: FontWeight.w600),
        ),
      ),
      elevatedButtonTheme: ElevatedButtonThemeData(
        style: ElevatedButton.styleFrom(
          shape: controlShape,
          elevation: 0,
          backgroundColor: dark
              ? const Color(0xFF2D2D2D)
              : const Color(0xFFFFFFFF),
          foregroundColor: scheme.onSurface,
          padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
        ),
      ),
      outlinedButtonTheme: OutlinedButtonThemeData(
        style: OutlinedButton.styleFrom(
          shape: controlShape,
          side: BorderSide(color: scheme.outlineVariant),
          padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
        ),
      ),
      textButtonTheme: TextButtonThemeData(
        style: TextButton.styleFrom(shape: controlShape),
      ),
      snackBarTheme: SnackBarThemeData(
        behavior: SnackBarBehavior.floating,
        backgroundColor: dark ? const Color(0xFF2D2D2D) : const Color(0xFFF0F0F0),
        contentTextStyle: TextStyle(color: scheme.onSurface),
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(radiusCard),
        ),
      ),
      // 卡片：细描边、无阴影、8 像素圆角，贴近 WinUI 的卡片分层
      cardTheme: CardThemeData(
        elevation: 0,
        color: dark ? const Color(0xFF2B2B2B) : const Color(0xFFFFFFFF),
        surfaceTintColor: Colors.transparent,
        margin: EdgeInsets.zero,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(radiusCard),
          side: BorderSide(color: scheme.outlineVariant),
        ),
      ),
      dialogTheme: DialogThemeData(
        backgroundColor: dark ? const Color(0xFF2B2B2B) : const Color(0xFFF9F9F9),
        surfaceTintColor: Colors.transparent,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(radiusCard),
        ),
      ),
      bottomSheetTheme: BottomSheetThemeData(
        backgroundColor: dark ? const Color(0xFF2B2B2B) : const Color(0xFFF9F9F9),
        surfaceTintColor: Colors.transparent,
        shape: const RoundedRectangleBorder(
          borderRadius: BorderRadius.vertical(top: Radius.circular(12)),
        ),
      ),
      listTileTheme: ListTileThemeData(
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(radiusControl),
        ),
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
        backgroundColor: dark
            ? const Color(0xFF2D2D2D)
            : const Color(0xFFFFFFFF),
        side: BorderSide(color: scheme.outlineVariant),
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(radiusCard),
        ),
        labelStyle: TextStyle(color: scheme.onSurface, fontSize: 13),
      ),
    );
  }
}
