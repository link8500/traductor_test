#include <flutter/dart_project.h>
#include <flutter/flutter_view_controller.h>
#include <windows.h>

#include "flutter_window.h"
#include "utils.h"

int APIENTRY wWinMain(_In_ HINSTANCE instance, _In_opt_ HINSTANCE prev,
                      _In_ wchar_t *command_line, _In_ int show_command) {
  // Attach to console when present (e.g., 'flutter run') or create a
  // new console when running with a debugger.
  if (!::AttachConsole(ATTACH_PARENT_PROCESS) && ::IsDebuggerPresent()) {
    CreateAndAttachConsole();
  }

  // Initialize COM, so that it is available for use in the library and/or
  // plugins.
  ::CoInitializeEx(nullptr, COINIT_APARTMENTTHREADED);

  flutter::DartProject project(L"data");

  std::vector<std::string> command_line_arguments =
      GetCommandLineArguments();

  if (command_line_arguments.size() == 2 &&
      command_line_arguments[0] == "--overlay-self-test") {
    return ScreenTranslator::SelfTest(command_line_arguments[1]);
  }
  if (command_line_arguments.size() == 2 &&
      command_line_arguments[0] == "--overlay-toolbar-test") {
    return ScreenTranslator::ToolbarTest(command_line_arguments[1]);
  }
  if (command_line_arguments.size() == 3 && command_line_arguments[0] == "--comic-benchmark") {
    return ScreenTranslator::ComicBenchmark(command_line_arguments[1],command_line_arguments[2]);
  }
  if (command_line_arguments.size() == 3 && command_line_arguments[0] == "--translation-replay") {
    return ScreenTranslator::TranslationReplay(command_line_arguments[1],command_line_arguments[2]);
  }
  if (command_line_arguments.size() == 3 && command_line_arguments[0] == "--review-export") {
    return ScreenTranslator::ReviewExport(command_line_arguments[1],command_line_arguments[2]);
  }
  if (command_line_arguments.size() == 2 && command_line_arguments[0] == "--comic-layout-test") {
    return ScreenTranslator::LayoutTest(command_line_arguments[1]);
  }
  if (command_line_arguments.size() == 2 && command_line_arguments[0] == "--ocr-recovery-test") {
    return ScreenTranslator::RecoveryTest(command_line_arguments[1]);
  }

  project.set_dart_entrypoint_arguments(std::move(command_line_arguments));

  FlutterWindow window(project);
  Win32Window::Point origin(10, 10);
  Win32Window::Size size(820, 900);
  if (!window.Create(L"Luma - Traduce tu pantalla", origin, size)) {
    return EXIT_FAILURE;
  }
  window.SetQuitOnClose(true);

  ::MSG msg;
  while (::GetMessage(&msg, nullptr, 0, 0)) {
    ::TranslateMessage(&msg);
    ::DispatchMessage(&msg);
  }

  ::CoUninitialize();
  return EXIT_SUCCESS;
}
