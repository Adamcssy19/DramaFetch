#include <flutter/dart_project.h>
#include <flutter/flutter_view_controller.h>
#include <windows.h>

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

// 窗口按屏幕可用区域的比例打开，适配不同分辨率与系统缩放比例，
// 避免在小屏或高缩放的机器上开出一个超出屏幕的窗口。
void ComputeWindowBounds(Win32Window::Point* origin, Win32Window::Size* size) {
  RECT work_area = {};
  if (!::SystemParametersInfo(SPI_GETWORKAREA, 0, &work_area, 0)) {
    origin->x = 10;
    origin->y = 10;
    size->width = 1280;
    size->height = 720;
    return;
  }
  const int screen_width = work_area.right - work_area.left;
  const int screen_height = work_area.bottom - work_area.top;
  int width = screen_width * 3 / 4;
  int height = screen_height * 3 / 4;
  const int min_width = screen_width < 1024 ? screen_width : 1024;
  const int min_height = screen_height < 640 ? screen_height : 640;
  if (width < min_width) width = min_width;
  if (height < min_height) height = min_height;
  if (width > screen_width) width = screen_width;
  if (height > screen_height) height = screen_height;
  origin->x = work_area.left + (screen_width - width) / 2;
  origin->y = work_area.top + (screen_height - height) / 2;
  size->width = width;
  size->height = height;
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
  Win32Window::Size size(1280, 720);
  ComputeWindowBounds(&origin, &size);
  if (!window.Create(APP_WINDOW_TITLE, origin, size)) {
    return EXIT_FAILURE;
  }
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
