from __future__ import annotations

import sys
from typing import TYPE_CHECKING

from PySide6.QtCore import Qt, QCoreApplication, QRect, QRectF, QSize, Signal
from PySide6.QtGui import QColor, QIcon, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import (
    QApplication, QFileDialog, QHBoxLayout, QLabel, QVBoxLayout, QWidget,
)
from qfluentwidgets import (
    BodyLabel, CaptionLabel, CardWidget, CheckBox, ComboBox,
    DrillInTransitionStackedWidget, FluentIcon, FluentWidget,
    GroupHeaderCardWidget, HorizontalPipsPager, IconWidget,
    PipsScrollButtonDisplayMode,
    PrimaryPushButton, PushButton, SubtitleLabel, SwitchButton, Theme,
    TitleLabel, TransparentPushButton, isDarkTheme, qconfig, themeColor,
)
from qfluentwidgets.common.style_sheet import updateStyleSheet

from app.config.cfg import cfg

if sys.platform == "win32":
    from ctypes import cast, POINTER
    from ctypes.wintypes import MSG

    import win32con
    from qframelesswindow.windows.c_structures import PWINDOWPOS

if TYPE_CHECKING:
    from app.models.pack import BinaryRuntime

WINDOW_SIZE = QSize(960, 600)

NEUTRAL_CHIP_COLORS = ("#EFEFEF", "#666666", "#3D3D3D", "#AAAAAA")
SUCCESS_CHIP_COLORS = ("#E8F5E9", "#0F7B46", "#1A3A1A", "#4ADE80")


class IconChip(QWidget):

    def __init__(self, icon: FluentIcon, colors: tuple[str, str, str, str],
                 size: int = 40, parent=None):
        super().__init__(parent)
        self._icon = icon
        self._colors = colors
        self.setFixedSize(size, size)

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        lightBg, lightFg, darkBg, darkFg = self._colors
        bg, fg = (darkBg, darkFg) if isDarkTheme() else (lightBg, lightFg)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(bg))
        painter.drawRoundedRect(self.rect(), 8, 8)
        margin = round(self.width() * 0.25)
        iconRect = self.rect().adjusted(margin, margin, -margin, -margin)
        self._icon.render(painter, iconRect, fill=fg)


class ThemePreview(QWidget):

    def __init__(self, mode: str, parent=None):
        super().__init__(parent)
        self._mode = mode
        self.setFixedHeight(96)

    def _drawMini(self, painter: QPainter, rect: QRectF, isDark: bool) -> None:
        bg = QColor("#232323") if isDark else QColor("#F5F7FA")
        titleBar = QColor("#2E2E2E") if isDark else QColor("#E9EDF2")
        bar = QColor("#333333") if isDark else QColor("#FFFFFF")

        painter.fillRect(rect, bg)
        painter.fillRect(QRectF(rect.x(), rect.y(), rect.width(), 14), titleBar)

        padding = 8
        barX = rect.x() + padding
        barWidth = rect.width() - padding * 2
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(bar)
        painter.drawRoundedRect(QRectF(barX, rect.y() + 22, barWidth, 9), 3, 3)
        painter.drawRoundedRect(QRectF(barX, rect.y() + 37, barWidth * 0.55, 9), 3, 3)
        painter.setBrush(themeColor())
        painter.drawRoundedRect(
            QRectF(barX, rect.y() + rect.height() - 20, barWidth * 0.34, 11), 3, 3
        )

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        outer = QRectF(self.rect())
        clipPath = QPainterPath()
        clipPath.addRoundedRect(outer, 6, 6)
        painter.setClipPath(clipPath)

        if self._mode == "auto":
            half = outer.width() / 2
            self._drawMini(painter, QRectF(outer.x(), outer.y(), half, outer.height()), isDark=False)
            self._drawMini(painter, QRectF(outer.x() + half, outer.y(), half, outer.height()), isDark=True)
        else:
            self._drawMini(painter, outer, isDark=self._mode == "dark")

        painter.setClipping(False)
        painter.setPen(QPen(QColor(128, 128, 128, 60), 1))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(outer.adjusted(0.5, 0.5, -0.5, -0.5), 6, 6)


class ThemeCard(CardWidget):

    def __init__(self, theme: Theme, label: str, parent=None):
        super().__init__(parent)
        self.theme = theme
        self._isSelected = False
        self._initWidget(label)
        self._initLayout()

    def _initWidget(self, label: str) -> None:
        self.setClickEnabled(True)
        mode = {Theme.LIGHT: "light", Theme.DARK: "dark"}.get(self.theme, "auto")
        self.preview = ThemePreview(mode, self)
        self.label = BodyLabel(label, self)
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)

    def _initLayout(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 12)
        layout.setSpacing(10)
        layout.addWidget(self.preview)
        layout.addWidget(self.label)

    def setSelected(self, isSelected: bool) -> None:
        self._isSelected = isSelected
        self.update()

    def paintEvent(self, event) -> None:
        super().paintEvent(event)
        if not self._isSelected:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(QPen(themeColor(), 2))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        radius = self.borderRadius
        painter.drawRoundedRect(self.rect().adjusted(1, 1, -1, -1), radius, radius)


class OptionCard(CardWidget):

    def __init__(self, icon: FluentIcon, title: str, desc: str,
                 isChecked: bool = False, parent=None):
        super().__init__(parent)
        self._initWidget(icon, title, desc, isChecked)
        self._initLayout()

    def _initWidget(self, icon: FluentIcon, title: str, desc: str, isChecked: bool) -> None:
        self.setFixedHeight(64)
        self.iconChip = IconChip(icon, NEUTRAL_CHIP_COLORS, size=34, parent=self)
        self.titleLabel = BodyLabel(title, self)
        self.descLabel = CaptionLabel(desc, self)
        self.descLabel.setTextColor(Qt.GlobalColor.gray, Qt.GlobalColor.gray)
        self.switch = SwitchButton(self)
        self.switch.setOnText("")
        self.switch.setOffText("")
        self.switch.setChecked(isChecked)

    def _initLayout(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(18, 8, 18, 8)
        layout.setSpacing(14)
        layout.addWidget(self.iconChip)

        textCol = QVBoxLayout()
        textCol.setSpacing(0)
        textCol.addWidget(self.titleLabel)
        textCol.addWidget(self.descLabel)
        layout.addLayout(textCol, 1)
        layout.addWidget(self.switch)

    def isChecked(self) -> bool:
        return self.switch.isChecked()


class PageHeader(QWidget):

    def __init__(self, title: str, desc: str, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)
        layout.addWidget(SubtitleLabel(title, self))
        descLabel = CaptionLabel(desc, self)
        descLabel.setTextColor(Qt.GlobalColor.gray, Qt.GlobalColor.gray)
        layout.addWidget(descLabel)


class WelcomePage(QWidget):

    startClicked = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._initWidget()
        self._initLayout()
        self._bind()

    def _initWidget(self) -> None:
        self.iconLabel = QLabel(self)
        self.iconLabel.setPixmap(QIcon(":/image/logo.png").pixmap(88, 88))
        self.iconLabel.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.titleLabel = TitleLabel(self.tr("欢迎使用 DramaFetch"), self)
        self.titleLabel.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.subtitleLabel = BodyLabel(
            self.tr("快速、智能的下载管理器。\n接下来的几步将帮助你完成基本配置。"), self
        )
        self.subtitleLabel.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.subtitleLabel.setWordWrap(True)

        self.startButton = PrimaryPushButton(self.tr("开始配置"), self)
        self.startButton.setFixedWidth(200)

    def _initLayout(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(8)
        layout.addStretch(3)
        layout.addWidget(self.iconLabel, 0, Qt.AlignmentFlag.AlignCenter)
        layout.addSpacing(16)
        layout.addWidget(self.titleLabel)
        layout.addWidget(self.subtitleLabel)
        layout.addSpacing(28)
        layout.addWidget(self.startButton, 0, Qt.AlignmentFlag.AlignCenter)
        layout.addStretch(4)

    def _bind(self) -> None:
        self.startButton.clicked.connect(self.startClicked)


class BasicSettingsPage(QWidget):

    def __init__(self, parent=None):
        super().__init__(parent)
        self._initWidget()
        self._initLayout()
        self._bind()

    def _initWidget(self) -> None:
        self.header = PageHeader(
            self.tr("基本设置"),
            self.tr("选择你喜欢的外观，设置下载文件的保存位置"), self,
        )

        self._themeCards: list[ThemeCard] = []
        for theme, label in [(Theme.LIGHT, self.tr("浅色")),
                              (Theme.DARK, self.tr("深色")),
                              (Theme.AUTO, self.tr("跟随系统"))]:
            self._themeCards.append(ThemeCard(theme, label, self))
        self._refreshThemeCards()

        self.settingsCard = GroupHeaderCardWidget(self.tr("偏好"), self)

        self.browseButton = PushButton(self.tr("浏览..."), self)

    def _initLayout(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self.header)
        layout.addStretch(1)

        themeRow = QHBoxLayout()
        themeRow.setSpacing(14)
        for card in self._themeCards:
            themeRow.addWidget(card)
        layout.addLayout(themeRow)
        layout.addStretch(1)

        self._folderGroup = self.settingsCard.addGroup(
            FluentIcon.FOLDER, self.tr("下载保存位置"),
            str(cfg.downloadFolder.value), self.browseButton,
        )
        layout.addWidget(self.settingsCard)
        layout.addStretch(1)

    def _bind(self) -> None:
        for card in self._themeCards:
            card.clicked.connect(lambda t=card.theme: self._onThemePicked(t))
        self.browseButton.clicked.connect(self._onBrowseClicked)

    def _onThemePicked(self, theme: Theme) -> None:
        cfg.set(cfg.themeMode, theme)
        updateStyleSheet()
        qconfig.themeChangedFinished.emit()
        self._refreshThemeCards()

    def _refreshThemeCards(self) -> None:
        current = cfg.themeMode.value
        for card in self._themeCards:
            card.setSelected(card.theme == current)

    def _onBrowseClicked(self) -> None:
        folder = QFileDialog.getExistingDirectory(
            self, self.tr("选择下载目录"), str(cfg.downloadFolder.value)
        )
        if folder:
            cfg.set(cfg.downloadFolder, folder)
            self._folderGroup.setContent(folder)


class RuntimeInstallPage(QWidget):

    def __init__(self, featureService, parent=None):
        super().__init__(parent)
        self._featureService = featureService
        self._checkBoxes: list[tuple[CheckBox, BinaryRuntime]] = []
        self._isMounted = False
        self._initWidget()
        self._initLayout()

    def _initWidget(self) -> None:
        self.header = PageHeader(
            self.tr("安装推荐组件"),
            self.tr("点击下一步将自动安装勾选的组件，稍后可在设置中管理"), self,
        )
        self._card = GroupHeaderCardWidget(self.tr("推荐组件"), self)

    def _initLayout(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self.header)
        layout.addStretch(1)
        layout.addWidget(self._card)
        layout.addStretch(1)

    def mount(self) -> None:
        if self._isMounted:
            return
        self._isMounted = True

        entries = [rt for rt in self._featureService.runtimes() if rt.canInstall and rt.title]
        entries.sort(key=lambda rt: not rt.isRecommended)

        for runtime in entries:
            trailing = QWidget(self)
            trailingLayout = QHBoxLayout(trailing)
            trailingLayout.setContentsMargins(0, 0, 0, 0)
            trailingLayout.setSpacing(12)

            tag = CaptionLabel(runtime.name, trailing)
            tag.setTextColor(Qt.GlobalColor.gray, Qt.GlobalColor.gray)
            trailingLayout.addWidget(tag)

            if runtime.path():
                installedLabel = CaptionLabel(self.tr("已安装"), trailing)
                installedLabel.setTextColor(Qt.GlobalColor.darkGreen, Qt.GlobalColor.green)
                trailingLayout.addWidget(installedLabel)
            else:
                checkBox = CheckBox(trailing)
                checkBox.setChecked(runtime.isRecommended)
                trailingLayout.addWidget(checkBox)
                self._checkBoxes.append((checkBox, runtime))

            self._card.addGroup(
                getattr(FluentIcon, runtime.icon, FluentIcon.APPLICATION),
                QCoreApplication.translate("BinaryRuntime", runtime.title),
                QCoreApplication.translate("BinaryRuntime", runtime.description),
                trailing,
            )

    def selectedRuntimes(self) -> list[BinaryRuntime]:
        return [rt for cb, rt in self._checkBoxes if cb.isChecked()]


class AdvancedOptionsPage(QWidget):

    def __init__(self, featureService, parent=None):
        super().__init__(parent)
        self._featureService = featureService
        self._initWidget()
        self._initLayout()

    def _initWidget(self) -> None:
        self.header = PageHeader(
            self.tr("更多选项"),
            self.tr("按需开启以下功能，也可以稍后在设置中修改"), self,
        )
        self.runAtLoginCard = OptionCard(
            FluentIcon.POWER_BUTTON, self.tr("开机自启"),
            self.tr("登录系统时自动在后台启动，随时接管下载"),
            isChecked=cfg.shouldRunAtLogin.value, parent=self,
        )
        self.clipboardCard = OptionCard(
            FluentIcon.PASTE, self.tr("剪贴板监听"),
            self.tr("复制下载链接时自动弹出新任务提示"),
            isChecked=cfg.isClipboardListenerEnabled.value, parent=self,
        )
        self.categoryCard = OptionCard(
            FluentIcon.TAG, self.tr("自动分类保存"),
            self.tr("按文件类型自动保存到 视频、音频、文档 等子文件夹"),
            isChecked=cfg.isCategoryEnabled.value, parent=self,
        )
        if sys.platform != "darwin":
            self.fileAssocCard = OptionCard(
                FluentIcon.DOCUMENT, self.tr("关联文件类型"),
                self.tr("双击 .torrent 等文件时用 DramaFetch 打开"),
                isChecked=self._featureService.isFileAssociationEnabled(), parent=self,
            )
            self.uriSchemeCard = OptionCard(
                FluentIcon.LINK, self.tr("处理协议链接"),
                self.tr("点击 drama:// 链接时唤起 DramaFetch"),
                isChecked=self._featureService.isUriSchemeAssociationEnabled(), parent=self,
            )
            self.urlSchemeCard = OptionCard(
                FluentIcon.GLOBE, self.tr("允许链接唤起"),
                self.tr("允许通过 dramafetch:// 协议启动桌面端"),
                isChecked=cfg.isUrlSchemeRegistered.value, parent=self,
            )
        else:
            self.fileAssocCard = None
            self.uriSchemeCard = None
            self.urlSchemeCard = None

    def _initLayout(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self.header)
        layout.addStretch(1)

        listLayout = QVBoxLayout()
        listLayout.setSpacing(8)
        for card in [self.runAtLoginCard, self.clipboardCard, self.categoryCard,
                     self.fileAssocCard, self.uriSchemeCard, self.urlSchemeCard]:
            if card is not None:
                listLayout.addWidget(card)
        layout.addLayout(listLayout)
        layout.addStretch(1)

    def save(self) -> None:
        if self.runAtLoginCard.isChecked() != cfg.shouldRunAtLogin.value:
            from app.platform.run_at_login import setRunAtLogin
            setRunAtLogin(self.runAtLoginCard.isChecked())
            cfg.set(cfg.shouldRunAtLogin, self.runAtLoginCard.isChecked())

        cfg.set(cfg.isClipboardListenerEnabled, self.clipboardCard.isChecked())

        cfg.set(cfg.isCategoryEnabled, self.categoryCard.isChecked())

        if self.fileAssocCard is not None:
            for pack in self._featureService.packs:
                config = pack.config
                if config is not None and config.associateFileTypes is not None:
                    cfg.set(config.associateFileTypes, self.fileAssocCard.isChecked())
                if config is not None and config.associateUriSchemes is not None:
                    cfg.set(config.associateUriSchemes, self.uriSchemeCard.isChecked())

        if self.urlSchemeCard is not None:
            from app.platform.url_scheme import registerUrlScheme, unregisterUrlScheme
            if self.urlSchemeCard.isChecked():
                registerUrlScheme()
            else:
                unregisterUrlScheme()
            cfg.set(cfg.isUrlSchemeRegistered, self.urlSchemeCard.isChecked())


class CompletePage(QWidget):

    finishClicked = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._initWidget()
        self._initLayout()
        self._bind()

    def _initWidget(self) -> None:
        self.checkIcon = IconChip(FluentIcon.ACCEPT, SUCCESS_CHIP_COLORS, size=80, parent=self)

        self.titleLabel = TitleLabel(self.tr("一切就绪"), self)
        self.titleLabel.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.descLabel = BodyLabel(
            self.tr("DramaFetch 已准备好为你工作。\n你可以随时在设置中调整所有选项。"),
            self,
        )
        self.descLabel.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.descLabel.setWordWrap(True)

        self.finishButton = PrimaryPushButton(self.tr("开始使用"), self)
        self.finishButton.setFixedWidth(200)

    def _initLayout(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(8)
        layout.addStretch(3)
        layout.addWidget(self.checkIcon, 0, Qt.AlignmentFlag.AlignCenter)
        layout.addSpacing(16)
        layout.addWidget(self.titleLabel)
        layout.addWidget(self.descLabel)
        layout.addSpacing(28)
        layout.addWidget(self.finishButton, 0, Qt.AlignmentFlag.AlignCenter)
        layout.addStretch(4)

    def _bind(self) -> None:
        self.finishButton.clicked.connect(self.finishClicked)


class OobeWindow(FluentWidget):

    finished = Signal()

    PAGE_COUNT = 5

    def __init__(self, coroutineRunner, featureService,
                 runtimeStatusService, parent=None):
        super().__init__(parent=parent)
        self._coroutineRunner = coroutineRunner
        self._featureService = featureService
        self._runtimeStatusService = runtimeStatusService
        self._currentIndex = 0
        self._isFinished = False
        self._initWidget()
        self._initContent()
        self._initLayout()
        self._bind()
        self._refreshNavigation()

    def _initWidget(self) -> None:
        from qfluentwidgets import MSFluentTitleBar
        self.setTitleBar(MSFluentTitleBar(self))
        self.setWindowTitle("DramaFetch")
        self.setWindowIcon(QIcon(":/image/logo.png"))
        self.titleBar.hBoxLayout.insertSpacing(2, 6)
        if sys.platform == "darwin":
            self.titleBar.hBoxLayout.insertSpacing(0, 60)
        self.titleBar.maxBtn.hide()
        self.setFixedSize(WINDOW_SIZE)
        self.setResizeEnabled(False)
        desktop = QApplication.primaryScreen().availableGeometry()
        self.move(desktop.center() - self.rect().center())

    def systemTitleBarRect(self, size) -> QRect:
        return QRect(0, 10, 75, size.height())

    def _initContent(self) -> None:
        self.welcomePage = WelcomePage(self)
        self.basicSettingsPage = BasicSettingsPage(self)
        self.runtimeInstallPage = RuntimeInstallPage(self._featureService, self)
        self.advancedOptionsPage = AdvancedOptionsPage(self._featureService, self)
        self.completePage = CompletePage(self)

        self.stackedWidget = DrillInTransitionStackedWidget(self)
        self.stackedWidget.addWidget(self.welcomePage)
        self.stackedWidget.addWidget(self.basicSettingsPage)
        self.stackedWidget.addWidget(self.runtimeInstallPage)
        self.stackedWidget.addWidget(self.advancedOptionsPage)
        self.stackedWidget.addWidget(self.completePage)

        self.backButton = PushButton(self.tr("上一步"), self)
        self.skipButton = TransparentPushButton(self.tr("跳过全部"), self)
        self.nextButton = PrimaryPushButton(self.tr("下一步"), self)
        self.pipsPager = HorizontalPipsPager(self)
        self.pipsPager.setPageNumber(self.PAGE_COUNT)
        self.pipsPager.setVisibleNumber(self.PAGE_COUNT)
        self.pipsPager.setPreviousButtonDisplayMode(PipsScrollButtonDisplayMode.NEVER)
        self.pipsPager.setNextButtonDisplayMode(PipsScrollButtonDisplayMode.NEVER)
        self.pipsPager.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

    def _initLayout(self) -> None:
        mainLayout = QVBoxLayout(self)
        mainLayout.setContentsMargins(36, self.titleBar.height() + 8, 36, 16)
        mainLayout.setSpacing(0)
        mainLayout.addWidget(self.stackedWidget, 1)

        navLayout = QHBoxLayout()
        navLayout.setContentsMargins(0, 14, 0, 0)

        leftBox = QHBoxLayout()
        leftBox.addWidget(self.skipButton)
        leftBox.addWidget(self.backButton)
        leftBox.addStretch()

        rightBox = QHBoxLayout()
        rightBox.addStretch()
        rightBox.addWidget(self.nextButton)

        navLayout.addLayout(leftBox, 1)
        navLayout.addWidget(self.pipsPager)
        navLayout.addLayout(rightBox, 1)
        mainLayout.addLayout(navLayout)

    def _bind(self) -> None:
        self.welcomePage.startClicked.connect(self._onNextClicked)
        self.completePage.finishClicked.connect(self._finish)
        self.backButton.clicked.connect(self._onBackClicked)
        self.nextButton.clicked.connect(self._onNextClicked)
        self.skipButton.clicked.connect(self._finish)

    def _refreshNavigation(self) -> None:
        i = self._currentIndex
        isFirst = i == 0
        isLast = i == self.PAGE_COUNT - 1

        self.backButton.setVisible(not isFirst and not isLast)
        self.nextButton.setVisible(not isFirst and not isLast)
        self.skipButton.setVisible(isFirst)
        self.pipsPager.setCurrentIndex(i)

    def _onNextClicked(self) -> None:
        if self._currentIndex >= self.PAGE_COUNT - 1:
            return

        if self._currentIndex == 2:
            self._installSelectedRuntimes()

        self._currentIndex += 1
        self.stackedWidget.setCurrentIndex(self._currentIndex)
        self._refreshNavigation()
        if self._currentIndex == 2:
            self.runtimeInstallPage.mount()

    def _onBackClicked(self) -> None:
        if self._currentIndex <= 0:
            return
        self._currentIndex -= 1
        self.stackedWidget.setCurrentIndex(self._currentIndex, isBack=True)
        self._refreshNavigation()

    def _installSelectedRuntimes(self) -> None:
        runtimes = self.runtimeInstallPage.selectedRuntimes()
        if not runtimes:
            return

        for runtime in runtimes:
            if runtime.path():
                continue
            self._runtimeStatusService.install(runtime)

    def _finish(self) -> None:
        if self._isFinished:
            return
        self._isFinished = True
        self.advancedOptionsPage.save()
        cfg.set(cfg.hasCompletedOobe, True)
        self.finished.emit()
        self.close()

    def nativeEvent(self, eventType, message):
        # Win10 WS_THICKFRAME 拖动时会短暂注入错误高度
        if sys.platform == "win32":
            msg = MSG.from_address(message.__int__())
            if msg.message == win32con.WM_WINDOWPOSCHANGING:
                pos = cast(msg.lParam, POINTER(PWINDOWPOS)).contents
                if not (pos.flags & win32con.SWP_NOSIZE):
                    dpr = self.devicePixelRatio()
                    pos.cx = int(WINDOW_SIZE.width() * dpr)
                    pos.cy = int(WINDOW_SIZE.height() * dpr)
        return super().nativeEvent(eventType, message)

    def closeEvent(self, event) -> None:
        # 用户直接关窗视为"跳过全部"
        if not self._isFinished:
            self._isFinished = True
            cfg.set(cfg.hasCompletedOobe, True)
            self.finished.emit()
        super().closeEvent(event)
