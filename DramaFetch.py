import os
import sys
import traceback

from loguru import logger

from app.config.paths import APP_DATA_DIR

logger.add(f"{APP_DATA_DIR}/DramaFetch.log", rotation="512 KB", retention=5)


def _exceptionHook(exceptionType, value, tb):
    info = (exceptionType, value, tb)
    logger.opt(exception=info).error("Unhandled application exception")
    if "__compiled__" not in globals():
        sys.__excepthook__(*info)


sys.excepthook = _exceptionHook


def setupEnvironment():
    from app.config.cfg import cfg
    from app.config.constants import VERSION
    from app.platform.hidden_subprocess import setupHiddenSubprocess
    from qfluentwidgets import qconfig

    if sys.platform == "win32":
        setupHiddenSubprocess()

    from app.view.qfw_patch import patchFluentLabelThemeChanged, patchStackedWidgetAnimation
    from app.view.components.labels import IconBodyLabel
    patchFluentLabelThemeChanged()
    patchStackedWidgetAnimation()
    qconfig.themeChanged.connect(IconBodyLabel.clearCache)
    qconfig.load(f"{APP_DATA_DIR}/UserConfig.json", cfg)

    if cfg.dpiScale.value != 0:
        os.environ["QT_ENABLE_HIGHDPI_SCALING"] = "0"
        os.environ["QT_SCALE_FACTOR"] = str(cfg.dpiScale.value)

    if sys.platform == "win32":
        from PySide6.QtGui import QFont
        from PySide6.QtWidgets import QApplication
        font = QFont()
        font.setHintingPreference(QFont.HintingPreference.PreferNoHinting)
        QApplication.setFont(font)

    logger.info("DramaFetch v{} launched", VERSION)


def startApp(application, isSilent=False):
    import shutil
    from PySide6.QtGui import QIcon
    from app.config.cfg import cfg
    from app.config.paths import EXECUTABLE_DIR
    from app.view.shell.clipboard_listener import ClipboardListener
    from app.signal_bus import signalBus
    from app.startup import loadEngine, createServices, loadPacks, startEngine, bindNotifications, checkUpdateAtStartup, stopEngine
    from app.view.windows.main_window import MainWindow

    def exceptionHook(exceptionType, value, tb):
        _exceptionHook(exceptionType, value, tb)
        message = "".join(traceback.format_exception(exceptionType, value, tb)).rstrip()
        signalBus.exceptionCaught.emit(message)

    sys.excepthook = exceptionHook

    from PySide6.QtCore import QLocale
    from app.platform.desktop import buildFontFamilies
    localeName = cfg.language.value.value
    locale = QLocale() if localeName == "Auto" else QLocale(localeName)
    cfg.set(cfg.fontFamilies, buildFontFamilies(locale, application.font().defaultFamily()), save=False)
    application.setQuitOnLastWindowClosed(False)

    if sys.platform == "darwin":
        from app.view.shell.dock import setDockIconVisible
        setDockIconVisible(cfg.shouldShowDockIcon.value, activate=False)

    coroutineRunner, categoryService, speedMeter = loadEngine(application)

    appDir = EXECUTABLE_DIR.parent.parent if sys.platform == "darwin" else EXECUTABLE_DIR
    backupDir = appDir.parent / f"{appDir.name}_backup"
    if backupDir.is_dir():
        shutil.rmtree(backupDir, ignore_errors=True)

    MainWindow.refreshThemeColor()

    featureService, taskService, updateService, runtimeStatusService = createServices(
        coroutineRunner, categoryService, speedMeter,
    )
    loadPacks(featureService, coroutineRunner, speedMeter)

    from app.services.plan import Plan
    plan = Plan(allCompleted=lambda: taskService.runningCount() == 0)
    taskService.tasksAllCompleted.connect(plan.trigger)

    application.clipboardListener = ClipboardListener(featureService.matchPassive, parent=application)
    cfg.isClipboardListenerEnabled.valueChanged.connect(application.clipboardListener.setEnabled)
    application.clipboardListener.setEnabled(cfg.isClipboardListenerEnabled.value)

    # 下载完成提示音：随任务完成信号播放，可关
    from pathlib import Path
    from PySide6.QtCore import QUrl
    from PySide6.QtMultimedia import QSoundEffect
    completionSound = QSoundEffect(application)
    for wav in (
        EXECUTABLE_DIR / "app" / "assets" / "completed_task.wav",   # 打包后
        Path(__file__).resolve().parent / "app" / "assets" / "completed_task.wav",  # 源码运行
    ):
        if wav.exists():
            completionSound.setSource(QUrl.fromLocalFile(str(wav)))
            break
    completionSound.setVolume(0.8)
    application.completionSound = completionSound

    def onTaskCompleted(_task):
        if cfg.shouldPlayCompletionSound.value:
            completionSound.play()

    taskService.taskCompleted.connect(onTaskCompleted)

    shouldRunOobe = not cfg.hasCompletedOobe.value and not isSilent

    if shouldRunOobe:
        # 首次启动：服务先就绪，主窗口等 OOBE 结束后按最终配置创建
        from PySide6.QtCore import QEventLoop
        from app.view.windows.oobe_window import OobeWindow

        startEngine(taskService, speedMeter, featureService, coroutineRunner)

        oobe = OobeWindow(coroutineRunner, featureService, runtimeStatusService)
        oobe.show()

        loop = QEventLoop()
        oobe.finished.connect(loop.quit)
        oobe.destroyed.connect(loop.quit)
        loop.exec()

        # 必须在主线程显式销毁：闭包连接使窗口陷入循环引用，若留给
        # Python GC 会在任意工作线程 delete，主线程定时器表悬空 → 闪退
        oobe.deleteLater()

        window = MainWindow(taskService, featureService, categoryService, speedMeter, coroutineRunner, plan, updateService)
        window.setupPacks()
        window.show()
    else:
        window = MainWindow(taskService, featureService, categoryService, speedMeter, coroutineRunner, plan, updateService)

        if not isSilent and sys.platform != "darwin":
            from qfluentwidgets import SplashScreen
            splash = SplashScreen(window.windowIcon(), window, enableShadow=False)
            splash.raise_()
            window.show()
            application.processEvents()

        window.setupPacks()
        startEngine(taskService, speedMeter, featureService, coroutineRunner)

        if not isSilent and sys.platform != "darwin":
            splash.finish()

    from app.platform.windows import emptyWorkingSet

    def emptyWorkingSetIfIdle():
        if window is None and taskService.runningCount() == 0:
            emptyWorkingSet()

    def onWindowDestroyed():
        nonlocal window
        window = None
        emptyWorkingSetIfIdle()

    window.destroyed.connect(onWindowDestroyed)

    def show() -> MainWindow:
        nonlocal window
        if window is None:
            window = MainWindow(taskService, featureService, categoryService, speedMeter, coroutineRunner, plan, updateService)
            window.setupPacks()
            window.destroyed.connect(onWindowDestroyed)
        window.show()
        from app.platform.desktop import raiseWindow
        raiseWindow(window)
        return window

    if sys.platform != "darwin":
        signalBus.activationRequested.connect(show)
    signalBus.openUriRequested.connect(lambda uris: show().addUrls(uris))
    signalBus.exceptionCaught.connect(lambda msg: show().alertException(msg))

    application.clipboardListener.urlsDetected.connect(lambda urls: show().addUrls(urls))

    if sys.platform == "darwin":
        from app.view.shell.mac_status_item import MacStatusItem
        from app.view.shell.dock import setupDock
        statusItem = MacStatusItem(taskService)
        statusItem.show()
        speedMeter.speedChanged.connect(statusItem.setSpeed)
        application.statusItem = statusItem
        setupDock(speedMeter, taskService)
    else:
        from app.view.shell.tray import SystemTrayIcon
        tray = SystemTrayIcon(taskService, speedMeter, QIcon(":/image/logo.png"), parent=application)
        tray.show()

    from app.platform.desktop_keepalive import hold, release
    taskService.taskStarted.connect(lambda _: hold())
    taskService.tasksAllCompleted.connect(release)

    from app.platform.desktop_notification import init, notifyTaskCompleted, notifyDiskSpaceInsufficient
    coroutineRunner.submit(init(coroutineRunner.submit))
    bindNotifications(taskService, notifyTaskCompleted, notifyDiskSpaceInsufficient)

    taskService.tasksAllCompleted.connect(emptyWorkingSetIfIdle)

    if isSilent:
        emptyWorkingSetIfIdle()

    if sys.platform == "darwin":
        signalBus.activationRequested.connect(show)

    from app.services.update_service import UpdateState
    def onUpdateChanged(info):
        if info.targetId == "app" and info.state == UpdateState.AVAILABLE:
            show()._onUpdateAvailable(info)
        elif info.targetId != "app" and info.state == UpdateState.AVAILABLE:
            updateService.download(info.targetId)
        elif info.targetId != "app" and info.state == UpdateState.READY:
            if window is not None:
                from qfluentwidgets import InfoBar, InfoBarPosition
                InfoBar.success(
                    window.tr("功能包更新"),
                    window.tr("{0} 将在下次启动时生效").format(info.label),
                    duration=5000,
                    position=InfoBarPosition.BOTTOM_RIGHT,
                    parent=window,
                )
    updateService.changed.connect(onUpdateChanged)
    checkUpdateAtStartup(updateService)

    application.aboutToQuit.connect(lambda: stopEngine(taskService, featureService, coroutineRunner, speedMeter, updateService))


if __name__ == "__main__":
    from app.config.constants import DESKTOP_ID
    from app.platform.application import SingletonApplication
    from app.platform.url_scheme import isWakeUri

    setupEnvironment()
    app = SingletonApplication(sys.argv, DESKTOP_ID)
    isSilent = "--silence" in sys.argv or any(isWakeUri(arg) for arg in sys.argv[1:])
    startApp(app, isSilent=isSilent)
    sys.exit(app.exec())
