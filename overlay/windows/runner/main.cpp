#include <dwmapi.h>
#include <flutter/dart_project.h>
#include <flutter/flutter_view_controller.h>
#include <windows.h>

#include <algorithm>
#include <string>
#include <vector>

#include "flutter_window.h"
#include "utils.h"
#include "app_branding.h"

namespace {

// 本项目改造：同一时间只允许运行一个实例。
// 重复双击图标时不再弹出新窗口，而是把已经在跑的窗口激活到前台。
bool FocusRunningInstance() {
  HANDLE mutex = ::CreateMutex(nullptr, FALSE, L"DramaFetchSingleInstance");
  if (mutex == nullptr) {
    return false;
  }
  if (::GetLastError() != ERROR_ALREADY_EXISTS) {
    return false;  // 第一个实例，正常继续启动
  }
  HWND existing = ::FindWindow(nullptr, APP_WINDOW_TITLE);
  if (existing != nullptr) {
    if (::IsIconic(existing)) {
      ::ShowWindow(existing, SW_RESTORE);
    }
    ::SetForegroundWindow(existing);
  }
  return true;
}

// 系统缩放比例（96 DPI 为 1.0）。
double SystemScale() {
  HDC screen = ::GetDC(nullptr);
  if (screen == nullptr) {
    return 1.0;
  }
  const int dpi = ::GetDeviceCaps(screen, LOGPIXELSX);
  ::ReleaseDC(nullptr, screen);
  if (dpi <= 0) {
    return 1.0;
  }
  return static_cast<double>(dpi) / 96.0;
}

// 窗口大小按**逻辑像素**计算。
//
// 关键点：Flutter 的窗口创建会把我们给的尺寸再乘一次系统缩放，所以这里必须先
// 把屏幕物理尺寸换算回逻辑尺寸，否则在高缩放屏上会得到一个超出屏幕的大窗口
// （表现为看不到窗口最下方）。
void ComputeWindowBounds(Win32Window::Point* origin, Win32Window::Size* size) {
  const double scale = SystemScale();

  RECT work_area = {};
  if (!::SystemParametersInfo(SPI_GETWORKAREA, 0, &work_area, 0)) {
    origin->x = 40;
    origin->y = 40;
    size->width = 1180;
    size->height = 760;
    return;
  }

  const double logical_width =
      (work_area.right - work_area.left) / scale;
  const double logical_height =
      (work_area.bottom - work_area.top) / scale;

  // 以较小的窗口打开，够用即可；上限避免在超大屏上开出一个过宽的窗口
  int width = static_cast<int>(logical_width * 0.68);
  int height = static_cast<int>(logical_height * 0.72);
  width = std::clamp(width, 940, 1120);
  height = std::clamp(height, 600, 740);
  if (width > logical_width) width = static_cast<int>(logical_width);
  if (height > logical_height) height = static_cast<int>(logical_height);

  origin->x = static_cast<int>((logical_width - width) / 2);
  origin->y = static_cast<int>((logical_height - height) / 2);
  size->width = width;
  size->height = height;
}

// Windows 11 的圆角窗口；系统不支持时静默跳过。
void ApplyRoundedCorners(HWND window) {
  if (window == nullptr) {
    return;
  }
  // 33 = DWMWA_WINDOW_CORNER_PREFERENCE，2 = 圆角
  const int preference = 2;
  ::DwmSetWindowAttribute(window, 33, &preference, sizeof(preference));
}

}  // namespace

int APIENTRY wWinMain(_In_ HINSTANCE instance, _In_opt_ HINSTANCE prev,
                      _In_ wchar_t *command_line, _In_ int show_command) {
  std::vector<std::string> command_line_arguments = GetCommandLineArguments();

  // 冒烟自检模式不做单实例限制，避免和正在运行的程序互相干扰
  bool smoke_mode = false;
  for (const auto& argument : command_line_arguments) {
    if (argument == "--package-smoke") {
      smoke_mode = true;
      break;
    }
  }
  if (!smoke_mode && FocusRunningInstance()) {
    return EXIT_SUCCESS;
  }

  // Attach to console when present (e.g., 'flutter run') or create a
  // new console when running with a debugger.
  if (!::AttachConsole(ATTACH_PARENT_PROCESS) && ::IsDebuggerPresent()) {
    CreateAndAttachConsole();
  }

  // Initialize COM, so that it is available for use in the library and/or
  // plugins.
  ::CoInitializeEx(nullptr, COINIT_APARTMENTTHREADED);

  flutter::DartProject project(L"data");

  project.set_dart_entrypoint_arguments(std::move(command_line_arguments));

  FlutterWindow window(project);
  Win32Window::Point origin(10, 10);
  Win32Window::Size size(1180, 760);
  ComputeWindowBounds(&origin, &size);
  if (!window.Create(APP_WINDOW_TITLE, origin, size)) {
    return EXIT_FAILURE;
  }
  ApplyRoundedCorners(window.GetHandle());
  // 关闭窗口即退出程序，不驻留后台
  window.SetQuitOnClose(true);

  ::MSG msg;
  while (::GetMessage(&msg, nullptr, 0, 0)) {
    ::TranslateMessage(&msg);
    ::DispatchMessage(&msg);
  }

  ::CoUninitialize();
  return EXIT_SUCCESS;
}
