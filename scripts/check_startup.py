"""构建前启动冒烟检查：真实跑一遍启动流程直到主窗口显示。

为什么需要这个脚本
------------------
`scripts/check_imports.py` 只能证明「模块能导入」，证明不了「主窗口能建起来」。
0.0.6 就吃过这个亏：`MainWindow.__init__` 中间被误插入一个 `@property`，
导致其后所有赋值变成 `return` 之后的死代码 —— 窗口从未真正初始化，
启动时 `window.show()` 直接触发 Windows access violation（无 Python 异常、无日志），
用户表现为「双击没反应 / 打不开」。

本脚本用离屏 Qt 平台复刻 DramaFetch.startApp 的关键路径：
  setupEnvironment → SingletonApplication → loadEngine → createServices
  → loadPacks → MainWindow(...) → setupPacks() → show() → processEvents()

任何一步抛异常都会以非 0 退出，从而在构建前拦下「装完打不开」的包。

用法：
  uv run python scripts/check_startup.py
"""

from __future__ import annotations

import os
import sys
import traceback
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

# 必须在导入 PySide6 之前设置：离屏渲染，不弹窗、不需要显示器
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

# Windows（含 CI runner）的 stdout 默认是 cp1252，直接 print 中文会
# UnicodeEncodeError 而把检查本身搞挂，这里强制 UTF-8。
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

for path in (str(REPO), str(REPO / "features")):
    if path not in sys.path:
        sys.path.insert(0, path)


def main() -> int:
    try:
        import DramaFetch
        from app.config.constants import DESKTOP_ID
        from app.platform.application import SingletonApplication
        from PySide6.QtWidgets import QApplication

        DramaFetch.setupEnvironment()
        app = SingletonApplication(sys.argv[:1], DESKTOP_ID)

        from app.startup import createServices, loadEngine, loadPacks
        from app.services.plan import Plan
        from app.view.windows.main_window import MainWindow

        coroutineRunner, categoryService, speedMeter = loadEngine(app)
        MainWindow.refreshThemeColor()
        featureService, taskService, updateService, _ = createServices(
            coroutineRunner, categoryService, speedMeter,
        )
        loadPacks(featureService, coroutineRunner, speedMeter)

        plan = Plan(allCompleted=lambda: taskService.runningCount() == 0)
        window = MainWindow(
            taskService, featureService, categoryService,
            speedMeter, coroutineRunner, plan, updateService,
        )
        # setupPacks/show 会真正走一遍页面注册与首屏渲染
        window.setupPacks()
        window.show()
        QApplication.processEvents()

        # 特性页是懒加载的（_showPage 里才构造），必须逐个真实创建，
        # 否则页面自身的构造问题（控件搭错、属性名写错）检查不到。
        created = ["TaskPage"]
        for PageClass in featureService.pages():
            window._showPage(PageClass)
            QApplication.processEvents()
            created.append(PageClass.__name__)

        print(f"OK  主窗口创建并显示成功，已实例化页面: {created}")
        print("✓ 启动冒烟检查通过")
        return 0
    except Exception as err:
        traceback.print_exc()
        print(f"\n✗ 启动冒烟检查失败: {type(err).__name__}: {err}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
