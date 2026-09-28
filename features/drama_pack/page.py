from __future__ import annotations

"""短剧页：搜索 / 分类浏览 → 剧卡片 → 弹选集对话框下载。"""

from urllib.parse import urlparse

from PySide6.QtCore import QT_TRANSLATE_NOOP as N, Qt, Signal
from PySide6.QtGui import QColor, QFontMetrics, QPainter, QPainterPath, QPixmap
from PySide6.QtWidgets import (
    QApplication, QHBoxLayout, QLabel, QSizePolicy, QVBoxLayout, QWidget,
)

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
    StrongBodyLabel,
    TransparentToolButton,
    ToolTipFilter,
)

from app.models.pack import PackPage
from app.models.task import TaskStatus
from app.view.components.scroll_area import ScrollArea as PageScrollArea

from . import api
from .picker import EpisodePickerDialog


# 排行榜前三名配色（金银铜），其余用半透明深色胶囊
_RANK_COLORS = {
    1: ("#F6B73C", "#3A2A00"),
    2: ("#C7CAD1", "#2A2D33"),
    3: ("#CD7F4A", "#3A1E08"),
}


def _rankBadgeStyle(rank: int) -> str:
    if rank in _RANK_COLORS:
        bg, fg = _RANK_COLORS[rank]
    else:
        bg, fg = "rgba(0, 0, 0, 0.62)", "#FFFFFF"
    return (
        f"QLabel{{background:{bg};color:{fg};border-radius:11px;"
        f"padding:0 6px;font-weight:700;}}"
    )

# 长条卡片：左侧竖版海报 + 右侧信息（与「已下载」页同风格）
CARD_HEIGHT = 168
POSTER_WIDTH, POSTER_HEIGHT = 108, 144   # 3:4 竖版海报完整显示，不裁剪
COVER_WIDTH, COVER_HEIGHT = POSTER_WIDTH, POSTER_HEIGHT
COVER_RADIUS = 10
CARD_SPACING = 10
GRID_MARGIN = 20
SIDE_PADDING = 20

# 旧名保留：外部（含门禁）仍按 CARD_WIDTH 引用
CARD_WIDTH = 0
GRID_SPACING = CARD_SPACING


def _elide(text: str, font, width: int) -> str:
    """单行省略号截断，超出部分靠 tooltip 展示全文。"""
    if not text:
        return ""
    return QFontMetrics(font).elidedText(text, Qt.TextElideMode.ElideRight, width)


def _roundedPixmap(src: QPixmap, radius: int) -> QPixmap:
    result = QPixmap(src.size())
    result.fill(Qt.GlobalColor.transparent)
    painter = QPainter(result)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    path = QPainterPath()
    path.addRoundedRect(0, 0, src.width(), src.height(), radius, radius)
    painter.setClipPath(path)
    painter.drawPixmap(0, 0, src)
    painter.end()
    return result


def _copyButton(text: str, ref=None, parent=None) -> TransparentToolButton:
    """同字号的小复制按钮。

    注意：**不要用子类 override `__init__`**。qfluentwidgets 的
    `TransparentToolButton.__init__` 是 `singledispatchmethod`，`(icon, parent)`
    分支内部走 `self.__init__(parent)` 回派；子类一旦 override `__init__`
    就会无限递归 RecursionError（同 app/view/components/track_bar.py 里
    「不能安全 override」的注释）。需要额外参数就用工厂函数。
    """
    button = TransparentToolButton(FluentIcon.COPY, parent)
    fm = ref.fontMetrics() if ref is not None else button.fontMetrics()
    h = max(fm.height() + 2, 14)
    button.setFixedSize(h, h)
    button.setToolTip("复制")
    button.installEventFilter(ToolTipFilter(button))
    button.clicked.connect(lambda: QApplication.clipboard().setText(text))
    return button


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
    """长条剧卡片：左侧 3:4 竖版海报，右侧剧名 / ID / 简介 / 记录 + 下载按钮。"""

    downloadRequested = Signal(object)

    def __init__(self, drama: api.Drama, parent=None, rank: int = 0, record=None):
        super().__init__(parent)
        self._drama = drama
        self.setFixedHeight(CARD_HEIGHT)

        self._cover = QLabel(self)
        self._cover.setFixedSize(POSTER_WIDTH, POSTER_HEIGHT)
        self._cover.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._cover.setStyleSheet(
            f"background-color: rgba(128, 128, 128, 0.14);"
            f"border-radius: {COVER_RADIUS}px;"
        )

        self._title = StrongBodyLabel(self)
        self._title.setText(drama.title)
        self._title.setToolTip(drama.title)
        # Ignored：剧名再长也不撑宽卡片，显示由 resizeEvent 里的 _elide 控制。
        self._title.setSizePolicy(QSizePolicy.Policy.Ignored,
                                  QSizePolicy.Policy.Preferred)
        self._title.setMinimumWidth(60)
        self._titleCopy = _copyButton(drama.title, self._title, self)
        titleRow = QHBoxLayout()
        titleRow.setContentsMargins(0, 0, 0, 0)
        titleRow.setSpacing(4)
        # 标题给 0 拉伸 + resizeEvent 里按裁剪结果 setFixedWidth，
        # 复制图标才会紧贴剧名；拉伸项放最后，把右侧空白吃掉。
        titleRow.addWidget(self._title, 0)
        titleRow.addWidget(self._titleCopy, 0)
        titleRow.addStretch(1)

        self._idLabel = CaptionLabel(self)
        self._idLabel.setText(f"ID {drama.seriesId}")
        self._idLabel.setTextColor(QColor(120, 120, 120), QColor(170, 170, 170))
        self._idCopy = _copyButton(drama.seriesId, self._idLabel, self)
        idRow = QHBoxLayout()
        idRow.setContentsMargins(0, 0, 0, 0)
        idRow.setSpacing(4)
        idRow.addWidget(self._idLabel, 0)
        idRow.addWidget(self._idCopy, 0)
        idRow.addStretch(1)

        self._meta = CaptionLabel(self)
        meta = self._metaText()
        self._meta.setText(meta)
        self._meta.setToolTip(meta)
        self._meta.setTextColor(QColor(120, 120, 120), QColor(170, 170, 170))

        self._intro = BodyLabel(self)
        intro = drama.intro or ""
        self._intro.setText(intro)
        self._intro.setToolTip(intro)
        self._intro.setWordWrap(False)
        # 水平策略设 Ignored：文本再长也不撑宽卡片（否则超长简介会把整条
        # 卡片顶到几千像素宽、横向滚动条乱窜），实际显示靠 _elide 裁。
        self._intro.setSizePolicy(QSizePolicy.Policy.Ignored,
                                  QSizePolicy.Policy.Preferred)
        self._intro.setTextColor(QColor(96, 96, 96), QColor(150, 150, 150))

        # 下载记录行：仅在该剧已存在下载任务时显示
        self._record = CaptionLabel(self)
        self._record.setFixedHeight(18)
        self._record.hide()

        self._download = PrimaryPushButton(FluentIcon.DOWNLOAD, "下载", self)
        self._download.setFixedHeight(32)
        self._download.setFixedWidth(96)
        self._download.clicked.connect(lambda: self.downloadRequested.emit(self._drama))

        buttonColumn = QVBoxLayout()
        buttonColumn.setContentsMargins(0, 0, 0, 0)
        buttonColumn.setSpacing(0)
        buttonColumn.addStretch(1)
        buttonColumn.addWidget(self._download)
        buttonColumn.addStretch(1)

        infoColumn = QVBoxLayout()
        infoColumn.setContentsMargins(0, 0, 0, 0)
        infoColumn.setSpacing(5)
        infoColumn.addLayout(titleRow)
        infoColumn.addLayout(idRow)
        infoColumn.addWidget(self._meta)
        infoColumn.addWidget(self._intro)
        infoColumn.addWidget(self._record)
        infoColumn.addStretch(1)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 12, 14, 12)
        layout.setSpacing(14)
        layout.addWidget(self._cover, 0, Qt.AlignmentFlag.AlignVCenter)
        layout.addLayout(infoColumn, 1)
        layout.addLayout(buttonColumn, 0)

        if rank > 0:
            self._buildRankBadge(rank)
        if record is not None:
            self.setDownloadRecord(record)

    def _metaText(self) -> str:
        parts = []
        if self._drama.category:
            parts.append(self._drama.category)
        if self._drama.remark:
            parts.append(self._drama.remark)
        elif self._drama.episodeCount:
            parts.append(f"共{self._drama.episodeCount}集")
        if self._drama.vidList:
            parts.append(f"可下{len(self._drama.vidList)}集")
        return " · ".join(parts)

    def _buildRankBadge(self, rank: int):
        badge = QLabel(self._cover)
        badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        badge.setText(f"第{rank}名")
        badge.setStyleSheet(_rankBadgeStyle(rank))
        # 居于海报左上角
        badge.setGeometry(6, 6, 46, 22)
        badge.raise_()

    def setDownloadRecord(self, record):
        """更新下载记录行；record=None 表示无下载记录。"""
        if record is None:
            self._record.hide()
            return
        total = record.get("total") or 0
        done = record.get("downloaded") or 0
        status = record.get("status")
        try:
            status = TaskStatus(status)
        except (TypeError, ValueError):
            status = None
        if status is TaskStatus.COMPLETED:
            text = f"✓ 已下载全部 {total} 集"
            color = QColor(30, 150, 80)
        elif status is TaskStatus.RUNNING:
            text = f"↓ 下载中 {done}/{total} 集"
            color = QColor(20, 120, 210)
        elif status is TaskStatus.PAUSED:
            text = f"⏸ 已暂停 {done}/{total} 集"
            color = QColor(180, 130, 20)
        elif status is TaskStatus.WAITING:
            text = f"⏳ 排队中 {done}/{total} 集"
            color = QColor(120, 120, 120)
        else:
            text = f"已下载 {done}/{total} 集"
            color = QColor(120, 120, 120)
        self._record.setText(text)
        self._record.setTextColor(color, color)
        self._record.show()

    def setCover(self, data: bytes):
        pixmap = QPixmap()
        if not pixmap.loadFromData(data):
            return
        # KeepAspectRatio：海报完整显示，不裁剪边缘
        scaled = pixmap.scaled(
            POSTER_WIDTH, POSTER_HEIGHT,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self._cover.setPixmap(_roundedPixmap(scaled, COVER_RADIUS))
        self._cover.setFixedSize(scaled.width(), scaled.height())
        self._cover.setStyleSheet("")
        # 海报实际宽度可能小于 POSTER_WIDTH，信息列宽度随之变化，
        # 而 setFixedSize 不会触发 resizeEvent，这里补一次重算，
        # 否则标题/简介的省略宽度会按旧值算、偏小或偏大。
        self._relayoutText()

    def _relayoutText(self) -> None:
        available = self._infoWidth()
        if available <= 0:
            return
        titleText = _elide(self._drama.title, self._title.font(), max(60, available - 24))
        self._title.setText(titleText)
        self._title.setFixedWidth(max(60, self._title.fontMetrics()
                                     .horizontalAdvance(titleText) + 2))
        if self._drama.intro:
            self._intro.setText(_elide(self._drama.intro, self._intro.font(), available))

    def _infoWidth(self) -> int:
        margins = self.layout().contentsMargins()
        spacing = self.layout().spacing()
        return max(0, self.width() - margins.left() - margins.right()
                   - self._cover.width() - self._download.width() - spacing * 2)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        # 信息列可用宽度 = 卡片宽 - 海报 - 按钮列 - 各边距/间距。
        # 不能用 label.width()：这些 label 水平策略是 Ignored/会横跨整列，
        # 拿它做 elide 等于不裁剪，长文本会一直顶到按钮底下。
        self._relayoutText()


class DramaPage(PackPage, PageScrollArea):
    icon = FluentIcon.VIDEO
    title = N("PackPage", "短剧")

    def __init__(self, pack, parent=None):
        super().__init__(parent)
        self._pack = pack
        self.setObjectName("DramaPage")
        self._cards: list[DramaCard] = []
        self._bySeries: dict[str, DramaCard] = {}
        self._taskService = None
        self._taskSignalsBound = False
        self._route = api.CATEGORY_ROUTES[0][0]
        self._categoryName = api.CATEGORY_ROUTES[0][1]
        self._page = 1
        self._totalPages = 1
        self._loading = False

        self._scrollWidget = QWidget()
        self._layout = QVBoxLayout(self._scrollWidget)
        # 长条卡片一列到底
        self._list = QVBoxLayout()
        self._list.setSpacing(CARD_SPACING)
        self._list.setContentsMargins(0, 0, 0, 0)
        self._state = LoadingState(self._scrollWidget)

        self._initTopBar()
        self._initLayout()
        self._startup()

    def _startup(self):
        self._loadCategory(self._route, page=1)

    # ── 界面搭建 ──

    def _initTopBar(self):
        # 搜索统一走主窗口顶栏搜索框（searchShortDrama），本页不再重复放搜索框
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
        self._layout.addLayout(self._list)
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
        topBar.addStretch(1)
        topBar.addWidget(self._categoryBox)
        return topBar

    # ── 数据加载 ──

    def _clearCards(self):
        for card in self._cards:
            self._list.removeWidget(card)
            card.deleteLater()
        self._cards.clear()
        self._bySeries.clear()

    def _addCards(self, dramas):
        for drama in dramas:
            record = self._recordFor(drama.seriesId)
            card = DramaCard(drama, self._scrollWidget, rank=drama.rank, record=record)
            card.downloadRequested.connect(self._onDownload)
            self._list.addWidget(card)
            self._cards.append(card)
            self._bySeries[drama.seriesId] = card
            if drama.cover:
                self._loadCover(card, drama.cover)
        self._bindTaskSignals()

    def _ensureTaskService(self):
        if self._taskService is not None:
            return self._taskService
        window = self.window()
        self._taskService = getattr(window, "taskService", None)
        return self._taskService

    def _recordFor(self, seriesId: str):
        """查该 seriesId 是否已有短剧下载任务，返回下载记录或 None。"""
        svc = self._ensureTaskService()
        if svc is None:
            return None
        for task in svc.tasks:
            if task.packId != "drama":
                continue
            parsed = urlparse(task.url)
            if parsed.scheme != "drama" or parsed.hostname != "hongguo":
                continue
            if parsed.path.strip("/") != seriesId:
                continue
            files = task.files or []
            total = len(files)
            done = sum(1 for f in files if getattr(f, "completed", False))
            return {"status": int(task.status), "total": total, "downloaded": done}
        return None

    def _bindTaskSignals(self):
        svc = self._ensureTaskService()
        if svc is None or self._taskSignalsBound or not self._bySeries:
            return
        self._taskSignalsBound = True
        for sig in ("taskAdded", "taskCompleted", "taskPaused",
                    "taskRemoved", "taskFailed"):
            signal = getattr(svc, sig, None)
            if signal is not None:
                signal.connect(lambda *_: self._refreshRecords())

    def _refreshRecords(self):
        for seriesId, card in self._bySeries.items():
            card.setDownloadRecord(self._recordFor(seriesId))

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
        """主窗口顶栏搜索框回车：切到本页并执行搜索。"""
        text = (text or "").strip()
        if not text:
            return
        self._onSearch(text)

    def _onBackToCategory(self):
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
