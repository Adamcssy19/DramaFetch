from __future__ import annotations

import sys

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QVBoxLayout, QWidget, QApplication
from qfluentwidgets import (
    ComboBoxSettingCard, FluentIcon, HyperlinkCard, InfoBar,
    InfoBarPosition, MessageBox, PrimaryPushSettingCard, PushButton, PushSettingCard,
    RangeSettingCard, SwitchSettingCard, ToolButton, ToolTipFilter,
)

from app.view.components.scroll_area import ScrollArea

from app.config.cfg import cfg, LANGUAGE_TEXTS
from app.platform.android import IS_ANDROID
from app.config.constants import (
    AUTHOR, AUTHOR_URL, FEEDBACK_URL, VERSION, YEAR,
)
from app.view.components.setting_card_group import (
    CollapsibleSettingCard, CollapsibleSettingCardGroup, QWIDGETSIZE_MAX,
)
from app.view.components.setting_cards import (
    PercentSpinBoxSettingCard, ProxySettingCard, SpinBoxSettingCard,
)
from app.view.components.editors import FolderPicker


class SettingPage(ScrollArea):

    def __init__(self, featureService, coroutineRunner, categoryService, taskService, updateService, parent=None):
        super().__init__(parent)
        self._featureService = featureService
        self._coroutineRunner = coroutineRunner
        self._categoryService = categoryService
        self._taskService = taskService
        self._updateService = updateService
        self.container = QWidget()
        self.vBoxLayout = QVBoxLayout(self.container)
        self.vBoxLayout.addStretch(1)

        self.generalGroup = CollapsibleSettingCardGroup(self.tr("综合下载设置"), "general", self.container)
        self.personalGroup = CollapsibleSettingCardGroup(self.tr("个性化"), "personalization", self.container)
        self.softwareGroup = CollapsibleSettingCardGroup(self.tr("应用"), "software", self.container)
        self.aboutGroup = CollapsibleSettingCardGroup(self.tr("关于"), "about", self.container)

        from app.view.pages.task_page import EmptyStatusWidget
        self.emptyStatusWidget = EmptyStatusWidget(FluentIcon.SEARCH_MIRROR, self.tr("未找到匹配的设置项"), self)
        self.emptyStatusWidget.hide()

        self._initWidget()
        self._initCards()
        self._initLayout()
        self._bind()

    def addSettingGroup(self, group: CollapsibleSettingCardGroup) -> None:
        self.vBoxLayout.insertWidget(self.vBoxLayout.count() - 1, group)

    def _initWidget(self) -> None:
        self.setWidget(self.container)
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setObjectName("SettingPage")
        self.enableTransparentBackground()
        self.setProperty("isStackedTransparent", False)

    def _initCards(self) -> None:
        self.speedLimitationCard = SpinBoxSettingCard(
            FluentIcon.SPEED_OFF, self.tr("下载限速"),
            self.tr("当下载任务界面限速开关开启时，所有任务将根据此值进行限速"),
            suffix=" KB/s", configItem=cfg.speedLimitation,
            singleStep=512, division=1 / 1024,
        )
        from qfluentwidgets import SettingCard
        self.downloadFolderCard = SettingCard(FluentIcon.FOLDER, self.tr("下载路径"), self.tr("文件默认保存位置"))
        self.downloadFolderPicker = FolderPicker(self.downloadFolderCard)
        self.downloadRestoreButton = ToolButton(FluentIcon.CANCEL, self.downloadFolderCard)
        self.downloadRestoreButton.setToolTip(self.tr("恢复默认路径"))
        self.downloadRestoreButton.installEventFilter(ToolTipFilter(self.downloadRestoreButton))
        self.downloadFolderPicker.refreshHistory()
        self.downloadFolderPicker.setPath(cfg.downloadFolder.value)
        self.downloadFolderCard.hBoxLayout.addWidget(self.downloadFolderPicker, 0, Qt.AlignmentFlag.AlignRight)
        self.downloadFolderCard.hBoxLayout.addSpacing(8)
        self.downloadFolderCard.hBoxLayout.addWidget(self.downloadRestoreButton, 0, Qt.AlignmentFlag.AlignRight)
        self.downloadFolderCard.hBoxLayout.addSpacing(16)

        self.generalGroup.addSettingCards([
            RangeSettingCard(cfg.maxTaskNum, FluentIcon.TRAIN, self.tr("最大任务数"),
                             self.tr("最多能同时进行的任务数量")),
            RangeSettingCard(cfg.preBlockNum, FluentIcon.CLOUD, self.tr("预分配线程数"),
                             self.tr("线程越多，下载越快。线程数大于 64 时，有触发反爬导致文件损坏的风险")),
            SwitchSettingCard(FluentIcon.SPEED_HIGH, self.tr("自动提速"),
                              self.tr("AI 实时检测各线程效率并自动增加线程数以提高下载速度"),
                              cfg.autoSpeedUp),
            SpinBoxSettingCard(FluentIcon.LIBRARY, self.tr("最小再分配大小"),
                              self.tr("每线程剩余量大于此值时, 有线程完成或自动提速条件满足会触发重新分配"),
                              " KB", cfg.maxReassignSize, singleStep=64),
            self.speedLimitationCard,
            SwitchSettingCard(FluentIcon.HISTORY, self.tr("保留文件修改时间"),
                              self.tr("下载完成后将文件的修改时间设为服务器提供的 Last-Modified 值"),
                              cfg.shouldPreserveLastModified),
            SwitchSettingCard(FluentIcon.DEVELOPER_TOOLS, self.tr("下载时验证 SSL 证书"),
                              self.tr("文件无法下载时，可尝试关闭该选项"),
                              cfg.shouldVerifySsl),
            self.downloadFolderCard,
            SwitchSettingCard(FluentIcon.CONNECT, self.tr("使用系统 DNS"),
                              self.tr("使用操作系统的 DNS 解析，兼容 TUN、VPN 和代理等网络环境"),
                              cfg.shouldUseSystemDns),
            ProxySettingCard(cfg.proxyServer, featureService=self._featureService),
        ])

        self.zoomCard = PercentSpinBoxSettingCard(
            FluentIcon.ZOOM, self.tr("界面缩放"),
            self.tr("改变应用程序界面的缩放比例, 0% 为自动"),
            configItem=cfg.dpiScale,
        )

        personalCards = [
            ComboBoxSettingCard(cfg.themeMode, FluentIcon.BRUSH, self.tr("应用主题"),
                                self.tr("更改应用程序的外观"),
                                texts=[self.tr("浅色"), self.tr("深色"), self.tr("跟随系统设置")]),
        ]
        if sys.platform == "win32":
            personalCards.append(
                ComboBoxSettingCard(cfg.backgroundEffect, FluentIcon.TRANSPARENT,
                                    self.tr("窗口背景透明材质"),
                                    self.tr("设置窗口背景透明效果和透明材质"),
                                    texts=["Acrylic", "Mica", "MicaAlt", "None"]),
            )
        elif sys.platform == "darwin":
            personalCards.append(
                ComboBoxSettingCard(cfg.backgroundEffect, FluentIcon.TRANSPARENT,
                                    self.tr("窗口背景透明材质"),
                                    self.tr("设置窗口背景透明效果和透明材质"),
                                    texts=["Acrylic", "None"]),
            )
        personalCards.append(self.zoomCard)
        if sys.platform == "darwin":
            self.showDockIconCard = SwitchSettingCard(
                FluentIcon.APPLICATION, self.tr("在 Dock 栏中显示程序"),
                self.tr("关闭后可通过菜单栏图标继续使用程序"),
                cfg.shouldShowDockIcon,
            )
            self.showDockSpeedCard = SwitchSettingCard(
                FluentIcon.SPEED_HIGH, self.tr("在 Dock 图标上显示实时速度"),
                self.tr("下载时在程序坞图标上叠加当前速度"),
                cfg.shouldShowDockSpeed,
            )
            self.showDockSpeedCard.setEnabled(cfg.shouldShowDockIcon.value)
            personalCards.extend([
                self.showDockIconCard,
                self.showDockSpeedCard,
                SwitchSettingCard(FluentIcon.SPEED_HIGH, self.tr("在菜单栏显示实时速度"),
                                  self.tr("下载时在菜单栏图标旁显示当前速度"),
                                  cfg.shouldShowMenuBarSpeed),
            ])
        personalCards.append(
            ComboBoxSettingCard(cfg.language, FluentIcon.LANGUAGE, self.tr("语言"),
                                self.tr("设置界面的首选语言"),
                                texts=[LANGUAGE_TEXTS.get(lang, self.tr("使用系统设置"))
                                       for lang in cfg.language.options]),
        )
        self.personalGroup.addSettingCards(personalCards)

        self.autoRunCard = SwitchSettingCard(
            FluentIcon.VPN, self.tr("开机启动"),
            self.tr("在系统启动时静默运行 DramaFetch"),
            cfg.shouldRunAtLogin,
        )
        from app.config.paths import APP_DATA_DIR, isPortable
        if isPortable():
            self.migrateCard = PushSettingCard(
                self.tr("切换到用户模式"), FluentIcon.SYNC,
                self.tr("数据存储模式"),
                self.tr("当前为 Portable 模式，数据保存在程序旁: {0}").format(APP_DATA_DIR),
            )
        else:
            self.migrateCard = PushSettingCard(
                self.tr("切换到 Portable 模式"), FluentIcon.SYNC,
                self.tr("数据存储模式"),
                self.tr("当前为用户模式，数据保存在: {0}").format(APP_DATA_DIR),
            )

        softwareCards = [
            SwitchSettingCard(FluentIcon.UPDATE, self.tr("在应用程序启动时检查更新"),
                              self.tr("新版本将更稳定，并具有更多功能"),
                              cfg.shouldCheckUpdateAtStartup),
            self.autoRunCard,
        ]
        softwareCards.append(
            SwitchSettingCard(FluentIcon.PASTE, self.tr("剪贴板监听"),
                              self.tr("剪贴板监听器将自动检测剪贴板中的链接并添加下载任务"),
                              cfg.isClipboardListenerEnabled),
        )
        softwareCards.append(
            SwitchSettingCard(FluentIcon.RINGER, self.tr("下载完成提示音"),
                              self.tr("任务下载完成时播放提示音"),
                              cfg.shouldPlayCompletionSound),
        )
        if not IS_ANDROID:
            softwareCards.append(self.migrateCard)
        self.softwareGroup.addSettingCards(softwareCards)

        self.feedbackCard = PrimaryPushSettingCard(
            self.tr("提供反馈"), FluentIcon.FEEDBACK,
            self.tr("提供反馈"),
            self.tr("通过提供反馈来帮助我们改进 DramaFetch，也可查看日志排查问题"),
        )
        self.openLogButton = PushButton(self.tr("查看日志"), self.feedbackCard)
        self.feedbackCard.hBoxLayout.insertSpacing(6, 8)
        self.feedbackCard.hBoxLayout.insertWidget(
            7, self.openLogButton, 0, Qt.AlignmentFlag.AlignRight,
        )

        self.packInfoCard = PrimaryPushSettingCard(
            self.tr("查看详情"), FluentIcon.IOT, self.tr("功能包"),
            self.tr("管理已安装的功能包"),
        )
        self.aboutCard = PrimaryPushSettingCard(
            self.tr("检查更新"), FluentIcon.INFO, self.tr("关于"),
            f"© Copyright {YEAR}, {AUTHOR}. Version {VERSION}",
        )

        self.aboutGroup.addSettingCards([
            HyperlinkCard(AUTHOR_URL, self.tr("打开作者的个人空间"), FluentIcon.PROJECTOR,
                          self.tr("了解作者"), self.tr("发现更多 {} 的作品").format(AUTHOR)),
            self.feedbackCard,
            self.packInfoCard,
            self.aboutCard,
        ])

    def _initLayout(self) -> None:
        self.addSettingGroup(self.generalGroup)
        self.addSettingGroup(self.personalGroup)
        self.addSettingGroup(self.softwareGroup)
        for group in self._featureService.settingGroups(self.container):
            self.addSettingGroup(group)
        self.addSettingGroup(self.aboutGroup)

    def _bind(self) -> None:
        cfg.appRestartSig.connect(self._showRestartTooltip)
        if sys.platform == "darwin":
            cfg.shouldShowDockIcon.valueChanged.connect(self.showDockSpeedCard.setEnabled)

        self.downloadFolderPicker.pathChanged.connect(self._onDownloadFolderChanged)
        self.downloadRestoreButton.clicked.connect(
            lambda: (self.downloadFolderPicker.setPath(cfg.downloadFolder.defaultValue),
                     cfg.set(cfg.downloadFolder, cfg.downloadFolder.defaultValue))
        )

        self.autoRunCard.checkedChanged.connect(self._onRunAtLoginChanged)
        self.packInfoCard.clicked.connect(self._onPackInfoClicked)
        self.aboutCard.clicked.connect(self._onAboutCardClicked)
        self.feedbackCard.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(FEEDBACK_URL)))
        self.openLogButton.clicked.connect(self._onOpenLogClicked)
        if not IS_ANDROID:
            self.migrateCard.clicked.connect(self._onMigrateClicked)

    def _onDownloadFolderChanged(self, path: str) -> None:
        cfg.set(cfg.downloadFolder, path)
        self.downloadFolderPicker.saveHistory(path)

    def _showRestartTooltip(self) -> None:
        InfoBar.success(self.tr("已配置"), self.tr("重启软件后生效"), duration=1500, parent=self)

    def _onRunAtLoginChanged(self, enabled: bool) -> None:
        from app.platform.run_at_login import setRunAtLogin
        setRunAtLogin(enabled)

    def _onMigrateClicked(self) -> None:
        from app.config.paths import isPortable, migrate, PORTABLE_DIR, USER_DATA_DIR

        target = USER_DATA_DIR if isPortable() else PORTABLE_DIR
        mode = self.tr("用户模式") if isPortable() else self.tr("Portable 模式")
        dialog = MessageBox(
            self.tr("切换数据存储模式"),
            self.tr("确定要切换到{0}吗？\n\n数据将被复制到新位置，程序随后退出。请手动重新打开。").format(mode),
            self.window(),
        )
        if not dialog.exec():
            return

        QApplication.instance().aboutToQuit.connect(lambda: migrate(target))
        QApplication.instance().quit()

    def _onPackInfoClicked(self) -> None:
        from app.view.dialogs.pack_info import PackInfoDialog
        dialog = PackInfoDialog(self._featureService.packs, self._updateService, self.window())
        dialog.exec()

    def _onAboutCardClicked(self) -> None:
        from app.services.update_service import UpdateState

        InfoBar.info(self.tr("检查更新"), self.tr("正在检查更新..."),
                     duration=1500, position=InfoBarPosition.BOTTOM_RIGHT, parent=self.window())

        def onChecked(info):
            if info.targetId != "app" or info.state not in (UpdateState.AVAILABLE, UpdateState.IDLE):
                return
            self._updateService.changed.disconnect(onChecked)
            if info.state == UpdateState.IDLE:
                if info.error is not None:
                    InfoBar.error(self.tr("检查更新失败"), self.tr("无法获取最新版本信息"),
                                  duration=3000, position=InfoBarPosition.BOTTOM_RIGHT, parent=self.window())
                else:
                    InfoBar.success(self.tr("当前已是最新版本"), "",
                                    duration=3000, position=InfoBarPosition.BOTTOM_RIGHT, parent=self.window())

        self._updateService.changed.connect(onChecked)
        self._updateService.check()

    def _onOpenLogClicked(self) -> None:
        from app.config.paths import APP_DATA_DIR
        from app.platform.desktop import revealInFolder
        revealInFolder(f"{APP_DATA_DIR}/DramaFetch.log")

    @property
    def searchPlaceholder(self) -> str:
        return self.tr("搜索设置")

    def setSearchText(self, text: str) -> None:
        text = text.strip().lower()
        if not text:
            self._clearSearchFilter()
            return

        hasMatch = False
        for i in range(self.vBoxLayout.count()):
            group = self.vBoxLayout.itemAt(i).widget()
            if not isinstance(group, CollapsibleSettingCardGroup):
                continue
            groupHasMatch = False
            for j in range(group.cardLayout.count()):
                card = group.cardLayout.itemAt(j).widget()
                if card is None:
                    continue
                if self._isSearchMatch(card, text):
                    card.show()
                    groupHasMatch = True
                else:
                    card.hide()
            if groupHasMatch:
                group.show()
                group.cardContainer.setMaximumHeight(QWIDGETSIZE_MAX)
                hasMatch = True
            else:
                group.hide()

        self.emptyStatusWidget.setVisible(not hasMatch)
        if not hasMatch:
            self.emptyStatusWidget.adjustSize()
            self._refreshEmptyWidgetGeometry()

    def _isSearchMatch(self, widget, text: str) -> bool:
        if isinstance(widget, CollapsibleSettingCard):
            widget = widget.card
        title = widget.titleLabel.text().lower()
        content = widget.contentLabel.text().lower()
        return text in title or text in content

    def _clearSearchFilter(self) -> None:
        for i in range(self.vBoxLayout.count()):
            group = self.vBoxLayout.itemAt(i).widget()
            if not isinstance(group, CollapsibleSettingCardGroup):
                continue
            group.show()
            for j in range(group.cardLayout.count()):
                card = group.cardLayout.itemAt(j).widget()
                if card is not None:
                    card.show()
            group.cardContainer.setMaximumHeight(
                0 if group._collapsed else QWIDGETSIZE_MAX
            )
        self.emptyStatusWidget.hide()

    def _refreshEmptyWidgetGeometry(self) -> None:
        self.emptyStatusWidget.move(
            (self.width() - self.emptyStatusWidget.width()) // 2,
            (self.height() - self.emptyStatusWidget.height()) // 2,
        )

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        if self.emptyStatusWidget.isVisible():
            self._refreshEmptyWidgetGeometry()

    def showEvent(self, event) -> None:
        self._restoreOrder()
        super().showEvent(event)

    def _restoreOrder(self) -> None:
        groups = [
            self.vBoxLayout.itemAt(i).widget()
            for i in range(self.vBoxLayout.count())
            if self.vBoxLayout.itemAt(i).widget()
        ]
        keyToWidget = {g.objectName(): g for g in groups}
        order = [k for k in cfg.settingGroupOrder.value if k in keyToWidget]
        rest = [k for k in keyToWidget if k not in order]
        aboutKey = self.aboutGroup.objectName()
        if aboutKey in rest:
            rest.remove(aboutKey)
            rest.append(aboutKey)
        order += rest
        for idx, key in enumerate(order):
            self.vBoxLayout.insertWidget(idx, keyToWidget[key])
        for g in groups:
            if isinstance(g, CollapsibleSettingCardGroup):
                g.updateArrows()
