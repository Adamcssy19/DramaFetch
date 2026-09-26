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

// 初始窗口尺寸，单位是**逻辑像素**。
//
// 关键点：Flutter 的窗口创建会把我们给的尺寸再乘一次系统缩放，所以这里必须先把
// 屏幕物理尺寸换算回逻辑尺寸，否则在高缩放屏上会得到一个超出屏幕的大窗口。
// 真正的最终位置与大小稍后由 FitToWorkArea 用物理坐标定死，这里只是给个合理初值。
void ComputeWindowBounds(Win32Window::Point* origin, Win32Window::Size* size) {
  const double scale = SystemScale();

  RECT work_area = {};
  if (!::SystemParametersInfo(SPI_GETWORKAREA, 0, &work_area, 0)) {
    origin->x = 0;
    origin->y = 0;
    size->width = 1280;
    size->height = 800;
    return;
  }

  const double logical_width = (work_area.right - work_area.left) / scale;
  const double logical_height = (work_area.bottom - work_area.top) / scale;

  origin->x = 0;
  origin->y = 0;
  size->width = static_cast<int>(logical_width);
  size->height = static_cast<int>(logical_height);
}

// 去掉系统标题栏。
//
// 最小化与关闭改在应用界面里自己画（见 overlay/lib/design/df_window_bar.dart），
// 所以这里把边框、标题栏、系统菜单与系统按钮的样式位全部摘掉，只留一个可激活的弹出窗口。
// 尺寸与位置随后由 FitToWorkArea 定死，窗口不需要拖拽与缩放。
void MakeFrameless(HWND window) {
  if (window == nullptr) {
    return;
  }
  LONG_PTR style = ::GetWindowLongPtr(window, GWL_STYLE);
  style &= ~(WS_CAPTION | WS_THICKFRAME | WS_MINIMIZEBOX | WS_MAXIMIZEBOX |
             WS_SYSMENU | WS_BORDER | WS_DLGFRAME);
  style |= WS_POPUP;
  ::SetWindowLongPtr(window, GWL_STYLE, style);

  LONG_PTR ex_style = ::GetWindowLongPtr(window, GWL_EXSTYLE);
  ex_style &= ~(WS_EX_CLIENTEDGE | WS_EX_WINDOWEDGE | WS_EX_DLGMODALFRAME);
  ex_style |= WS_EX_APPWINDOW;  // 无边框窗口默认不出现在任务栏，这行把它加回去
  ::SetWindowLongPtr(window, GWL_EXSTYLE, ex_style);

  ::SetWindowPos(window, nullptr, 0, 0, 0, 0,
                 SWP_NOMOVE | SWP_NOSIZE | SWP_NOZORDER | SWP_NOACTIVATE |
                     SWP_FRAMECHANGED);
}

// 用**物理像素**把窗口铺满屏幕工作区（任务栏仍然可见）。
// 这里不走逻辑坐标，省掉一次缩放换算，位置不会因为 DPI 而偏。
void FitToWorkArea(HWND window) {
  if (window == nullptr) {
    return;
  }
  RECT work_area = {};
  if (!::SystemParametersInfo(SPI_GETWORKAREA, 0, &work_area, 0)) {
    return;
  }
  ::SetWindowPos(window, HWND_TOP, work_area.left, work_area.top,
                 work_area.right - work_area.left,
                 work_area.bottom - work_area.top,
                 SWP_NOACTIVATE | SWP_FRAMECHANGED);
}

// 窗口圆角偏好：1 = 直角。
// 铺满整个工作区后圆角只会在四角露出桌面，所以明确关掉。
void ApplyCorners(HWND window) {
  if (window == nullptr) {
    return;
  }
  // 33 = DWMWA_WINDOW_CORNER_PREFERENCE，1 = DWMWCP_DONOTROUND
  const int preference = 1;
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
  Win32Window::Point origin(0, 0);
  Win32Window::Size size(1280, 800);
  ComputeWindowBounds(&origin, &size);
  if (!window.Create(APP_WINDOW_TITLE, origin, size)) {
    return EXIT_FAILURE;
  }
  HWND handle = window.GetHandle();
  MakeFrameless(handle);
  FitToWorkArea(handle);
  ApplyCorners(handle);
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
