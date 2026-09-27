from __future__ import annotations

"""短剧页：搜索 / 分类浏览 → 剧卡片 → 弹选集对话框下载。"""

from PySide6.QtCore import QT_TRANSLATE_NOOP as N, Qt, Signal
from PySide6.QtGui import QColor, QPixmap
from PySide6.QtWidgets import QGridLayout, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from qfluentwidgets import (
    BodyLabel,
    CaptionLabel,
    CardWidget,
    ComboBox,
    FluentIcon,
    IndeterminateProgressRing,
    InfoBar,
    InfoBarPosition,
    PrimaryPushButton,
    PushButton,
    SearchLineEdit,
    StrongBodyLabel,
    TransparentToolButton,
    ToolTipFilter,
)

from app.models.pack import PackPage
from app.view.components.scroll_area import ScrollArea as PageScrollArea

from . import api
from .picker import EpisodePickerDialog

CARD_WIDTH = 260
COVER_WIDTH, COVER_HEIGHT = 232, 130
GRID_SPACING = 12
GRID_MARGIN = 16


class LoadingState(QWidget):
    retryRequested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._ring = IndeterminateProgressRing(self)
        self._ring.setFixedSize(44, 44)
        self._label = CaptionLabel("正在加载…", self)
        self._label.setTextColor(QColor(120, 120, 120), QColor(180, 180, 180))
        self._label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._label.setWordWrap(True)
        self._retry = PushButton("重试", self)
        self._retry.hide()
        self._retry.clicked.connect(self.retryRequested)

        self._errorIcon = TransparentToolButton(FluentIcon.CANCEL, self)
        self._errorIcon.setFixedSize(40, 40)
        self._errorIcon.hide()

        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._ring, 0, Qt.AlignmentFlag.AlignHCenter)
        layout.addWidget(self._errorIcon, 0, Qt.AlignmentFlag.AlignHCenter)
        layout.addWidget(self._label, 0, Qt.AlignmentFlag.AlignHCenter)
        layout.addWidget(self._retry, 0, Qt.AlignmentFlag.AlignHCenter)

    def setLoading(self, text: str = "正在加载…"):
        self._ring.show()
        self._errorIcon.hide()
        self._retry.hide()
        self._label.setText(text)
        self.show()

    def setError(self, text: str):
        self._ring.hide()
        self._errorIcon.show()
        self._retry.show()
        self._label.setText(text)
        self.show()


class DramaCard(CardWidget):
    downloadRequested = Signal(object)

    def __init__(self, drama: api.Drama, parent=None):
        super().__init__(parent)
        self._drama = drama
        self.setFixedSize(CARD_WIDTH, 290)

        self._cover = QLabel(self)
        self._cover.setFixedSize(COVER_WIDTH, COVER_HEIGHT)
        self._cover.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._title = StrongBodyLabel(drama.title, self)
        self._title.setToolTip(drama.title)
        self._meta = CaptionLabel(self._metaText(), self)
        self._meta.setTextColor(QColor(120, 120, 120), QColor(170, 170, 170))
        self._intro = BodyLabel(drama.intro or "", self)
        self._intro.setTextColor(QColor(96, 96, 96), QColor(150, 150, 150))
        self._intro.setWordWrap(True)
        self._intro.setFixedHeight(40)
        if drama.intro:
            self._intro.setToolTip(drama.intro)

        self._download = PrimaryPushButton(FluentIcon.DOWNLOAD, "下载", self)
        self._download.setFixedHeight(32)
        self._download.clicked.connect(lambda: self.downloadRequested.emit(self._drama))

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(6)
        layout.addWidget(self._cover, 0, Qt.AlignmentFlag.AlignHCenter)
        layout.addWidget(self._title)
        layout.addWidget(self._meta)
        layout.addWidget(self._intro)
        layout.addStretch(1)
        layout.addWidget(self._download)

    def _metaText(self) -> str:
        parts = [self._drama.category or "短剧"]
        if self._drama.remark:
            parts.append(self._drama.remark)
        elif self._drama.episodeCount:
            parts.append(f"共{self._drama.episodeCount}集")
        if self._drama.vidList:
            parts.append(f"可下{len(self._drama.vidList)}集")
        return " · ".join(parts)

    def setCover(self, data: bytes):
        pixmap = QPixmap()
        if pixmap.loadFromData(data):
            self._cover.setPixmap(pixmap.scaled(
                COVER_WIDTH, COVER_HEIGHT,
                Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                Qt.TransformationMode.SmoothTransformation,
            ))


class DramaPage(PackPage, PageScrollArea):
    icon = FluentIcon.VIDEO
    title = N("PackPage", "短剧")

    def __init__(self, pack, parent=None):
        super().__init__(parent)
        self._pack = pack
        self.setObjectName("DramaPage")
        self._cards: list[DramaCard] = []
        self._route = api.CATEGORY_ROUTES[0][0]
        self._categoryName = api.CATEGORY_ROUTES[0][1]
        self._page = 1
        self._totalPages = 1
        self._loading = False

        self._scrollWidget = QWidget()
        self._layout = QVBoxLayout(self._scrollWidget)
        self._grid = QGridLayout()
        self._grid.setSpacing(GRID_SPACING)
        self._grid.setContentsMargins(0, 0, 0, 0)
        self._state = LoadingState(self._scrollWidget)

        self._initTopBar()
        self._initLayout()
        self._startup()

    def _startup(self):
        self._loadCategory(self._route, page=1)

    # ── 界面搭建 ──

    def _initTopBar(self):
        self._searchBox = SearchLineEdit(self._scrollWidget)
        self._searchBox.setPlaceholderText("搜索剧名，或粘贴果子分享链接")
        self._searchBox.setClearButtonEnabled(True)
        self._searchBox.setFixedWidth(360)
        self._searchBox.searchSignal.connect(self._onSearch)
        self._searchBox.returnPressed.connect(
            lambda: self._onSearch(self._searchBox.text()))

        self._categoryBox = ComboBox(self._scrollWidget)
        for _, name in api.CATEGORY_ROUTES:
            self._categoryBox.addItem(name)
        self._categoryBox.setCurrentIndex(0)
        self._categoryBox.currentIndexChanged.connect(self._onCategoryChanged)

        self._backButton = TransparentToolButton(FluentIcon.RETURN, self._scrollWidget)
        self._backButton.setToolTip("返回分类浏览")
        self._backButton.installEventFilter(ToolTipFilter(self._backButton))
        self._backButton.hide()
        self._backButton.clicked.connect(self._onBackToCategory)

        self._moreButton = PushButton("加载更多", self._scrollWidget)
        self._moreButton.hide()
        self._moreButton.clicked.connect(self._onMore)

    def _initLayout(self):
        self._layout.setSpacing(10)
        self._layout.setContentsMargins(GRID_MARGIN, 16, GRID_MARGIN, 16)
        self._layout.addLayout(self._buildTopBar())
        self._layout.addWidget(self._state, 0, Qt.AlignmentFlag.AlignCenter)
        self._layout.addLayout(self._grid)
        self._layout.addWidget(self._moreButton, 0, Qt.AlignmentFlag.AlignHCenter)
        self._layout.addStretch(1)

        self.setWidget(self._scrollWidget)
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.enableTransparentBackground()

    def _buildTopBar(self) -> QHBoxLayout:
        topBar = QHBoxLayout()
        topBar.setSpacing(10)
        topBar.addWidget(self._backButton)
        topBar.addWidget(self._searchBox, 0, Qt.AlignmentFlag.AlignLeft)
        topBar.addStretch(1)
        topBar.addWidget(self._categoryBox)
        return topBar

    # ── 数据加载 ──

    def _clearCards(self):
        for card in self._cards:
            self._grid.removeWidget(card)
            card.deleteLater()
        self._cards.clear()

    def _addCards(self, dramas):
        for drama in dramas:
            card = DramaCard(drama, self._scrollWidget)
            card.downloadRequested.connect(self._onDownload)
            self._cards.append(card)
            if drama.cover:
                self._loadCover(card, drama.cover)
        self._reflowCards()

    def _reflowCards(self):
        """按可用宽度把卡片重排进网格，窄窗口单列、宽窗口多列。"""
        width = self.viewport().width() - GRID_MARGIN * 2 + GRID_SPACING
        cols = max(1, width // (CARD_WIDTH + GRID_SPACING))
        for i, card in enumerate(self._cards):
            self._grid.addWidget(card, i // cols, i % cols)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, "_grid"):
            self._reflowCards()

    def _loadCover(self, card: DramaCard, url: str):
        def done(data: bytes):
            try:
                card.setCover(data)
            except RuntimeError:
                pass

        def failed(error: str):
            pass

        self._pack.submit(api.getBytes(url), done=done, failed=failed, owner=card)

    def _showError(self, text: str):
        self._state.setError(text)

    def _onCategoryChanged(self, index: int):
        route, name = api.CATEGORY_ROUTES[index]
        self._loadCategory(route, page=1, categoryName=name)

    def _loadCategory(self, route: str, page: int, categoryName: str = "", append: bool = False):
        if self._loading:
            return
        self._loading = True
        self._route = route
        self._categoryName = categoryName or self._categoryName
        self._page = page
        if not append:
            self._clearCards()
            self._moreButton.hide()
            self._state.setLoading("正在加载分类…")
            self._state.show()
        self._backButton.hide()
        self._categoryBox.show()

        def done(result):
            self._loading = False
            dramas, totalPages = result
            self._totalPages = totalPages
            if not append:
                self._state.hide()
            self._addCards(dramas)
            if page < totalPages and dramas:
                self._moreButton.show()
            if not append and not dramas:
                self._showError("该分类暂时没有内容")

        def failed(error: str):
            self._loading = False
            self._showError("加载失败：\n" + str(error))

        self._pack.submit(
            api.category(route, page, self._categoryName),
            done=done, failed=failed, owner=self,
        )

    def _onMore(self):
        self._loadCategory(self._route, self._page + 1, append=True)

    def _onSearch(self, keyword: str):
        keyword = (keyword or "").strip()
        if not keyword or self._loading:
            return
        if keyword.startswith(("http://", "https://")):
            self._downloadFromLink(keyword)
            return
        if keyword.isdigit():
            self._openById(keyword)
            return
        self._loading = True
        self._clearCards()
        self._moreButton.hide()
        self._categoryBox.hide()
        self._backButton.show()
        self._state.setLoading("正在搜索…")
        self._state.show()

        def done(dramas):
            self._loading = False
            self._state.hide()
            self._addCards(dramas)
            if not dramas:
                self._showError("没有搜到相关短剧")

        def failed(error: str):
            self._loading = False
            self._showError("搜索失败：\n" + str(error))

        self._pack.submit(api.search(keyword), done=done, failed=failed, owner=self)

    def _openById(self, seriesId: str):
        """纯数字输入视为剧集 ID，直接拉取详情并弹选集。"""
        self._loading = True
        self._state.setLoading(f"正在获取剧集 {seriesId} …")
        self._state.show()

        def done(dramaDetail):
            self._loading = False
            self._state.hide()
            EpisodePickerDialog(self._pack, dramaDetail, self.window()).exec()

        def failed(error: str):
            self._loading = False
            self._state.hide()
            InfoBar.error(
                "没有找到该剧",
                f"ID {seriesId} 无效或网络异常：{error}",
                duration=4000, position=InfoBarPosition.BOTTOM_RIGHT, parent=self.window(),
            )

        self._pack.submit(api.detail(seriesId), done=done, failed=failed, owner=self)

    # ── 主窗口顶栏搜索框接入 ──

    def searchShortDrama(self, text: str):
        """主窗口搜索框回车：切到本页并执行搜索。"""
        text = (text or "").strip()
        if not text:
            return
        self._searchBox.setText(text)
        self._onSearch(text)

    def _onBackToCategory(self):
        self._searchBox.clear()
        self._loadCategory(self._route, page=1, categoryName=self._categoryName)

    def _downloadFromLink(self, url: str):
        InfoBar.info(
            "正在解析链接", "已识别果子链接，请到下载页查看任务",
            duration=3000, position=InfoBarPosition.BOTTOM_RIGHT, parent=self.window(),
        )

        def onParsed(task):
            self._pack.addTask(task)

        def onFailed(error: str):
            InfoBar.error("解析失败", str(error), duration=-1,
                          position=InfoBarPosition.BOTTOM_RIGHT, parent=self.window())

        from app.models.task import TaskOptions

        self._pack.submit(
            self._pack.parse(TaskOptions(url=url)),
            done=onParsed, failed=onFailed, owner=self.window(),
        )

    def _onDownload(self, drama: api.Drama):
        if self._loading:
            return
        self._loading = True

        def done(dramaDetail):
            self._loading = False
            EpisodePickerDialog(self._pack, dramaDetail, self.window()).exec()

        def failed(error: str):
            self._loading = False
            InfoBar.error("获取剧集列表失败", str(error), duration=-1,
                          position=InfoBarPosition.BOTTOM_RIGHT, parent=self.window())

        self._pack.submit(api.detail(drama.seriesId), done=done, failed=failed, owner=self)


class RankPage(DramaPage):
    """独立排行榜页：左侧导航直达，榜单切换 + 网格卡片。"""

    icon = FluentIcon.CALORIES
    title = N("PackPage", "排行榜")

    def __init__(self, pack, parent=None):
        super().__init__(pack, parent)
        self.setObjectName("RankPage")
        # 短剧页特有的控件在榜单页一律隐藏
        self._searchBox.hide()
        self._categoryBox.hide()
        self._backButton.hide()

    def _initTopBar(self):
        super()._initTopBar()
        self._rankRoute = api.RANK_ROUTES[0][0]
        self._rankName = api.RANK_ROUTES[0][1]
        self._rankPage = 1
        self._rankTotal = 1
        self._rankBox = ComboBox(self._scrollWidget)
        for _, name in api.RANK_ROUTES:
            self._rankBox.addItem(name)
        self._rankBox.setCurrentIndex(0)
        self._rankBox.currentIndexChanged.connect(self._onRankChanged)

    def _buildTopBar(self) -> QHBoxLayout:
        topBar = QHBoxLayout()
        topBar.setSpacing(10)
        topBar.addWidget(self._rankBox, 0, Qt.AlignmentFlag.AlignLeft)
        topBar.addStretch(1)
        return topBar

    def _startup(self):
        self._loadRank(self._rankRoute, page=1)

    def _onRankChanged(self, index: int):
        route, name = api.RANK_ROUTES[index]
        self._loadRank(route, page=1, rankName=name)

    def _onMore(self):
        self._loadRank(self._rankRoute, self._rankPage + 1, append=True)

    def _loadRank(self, route: str, page: int, rankName: str = "", append: bool = False):
        if self._loading:
            return
        self._loading = True
        self._rankRoute = route
        self._rankName = rankName or self._rankName
        self._rankPage = page
        if not append:
            self._clearCards()
            self._moreButton.hide()
            self._state.setLoading("正在加载榜单…")
            self._state.show()

        def done(result):
            self._loading = False
            dramas, totalPages = result
            self._rankTotal = totalPages
            if not append:
                self._state.hide()
            self._addCards(dramas)
            if page < totalPages and dramas:
                self._moreButton.show()
            if not append and not dramas:
                self._showError("该榜单暂时没有内容")

        def failed(error: str):
            self._loading = False
            self._showError("加载榜单失败：\n" + str(error))

        self._pack.submit(api.rank(route, page), done=done, failed=failed, owner=self)
