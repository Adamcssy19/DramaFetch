from __future__ import annotations

"""已下载页：按「剧」归纳，一部剧一张卡片，显示这部剧下载了多少集。

与「下载中」页的区别：
- 下载中 = 一集一集的任务卡片（TaskPage + DramaTaskCard）
- 已下载 = 一部剧一张海报卡片（本页），聚合该剧已下载 / 总集数

数据来源仍是 TaskService：短剧任务（packId == "drama"，
url 为 drama://hongguo/{seriesId}）按 seriesId 归并，同一 seriesId
在 TaskService.add 里已有去重，天然一剧一条。
"""

from pathlib import Path
from urllib.parse import urlparse

from PySide6.QtCore import QT_TRANSLATE_NOOP as N, Qt, QTimer
from PySide6.QtGui import QColor, QFontMetrics, QPainter, QPainterPath, QPixmap
from PySide6.QtWidgets import (
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from qfluentwidgets import (
    CaptionLabel,
    CardWidget,
    FluentIcon,
    InfoBar,
    InfoBarPosition,
    PrimaryPushButton,
    SegmentedToggleToolWidget,
    StrongBodyLabel,
    ToolTipFilter,
)

from app.models.pack import PackPage
from app.models.task import TaskStatus
from app.platform.desktop import revealInFolder
from app.view.components.scroll_area import ScrollArea as PageScrollArea

from .task import POSTER_NAME, parseDramaTaskUrl

CARD_WIDTH = 180
POSTER_WIDTH, POSTER_HEIGHT = 150, 200   # 3:4 竖版海报完整显示，不裁剪
POSTER_RADIUS = 10
CARD_HEIGHT = 320
GRID_SPACING = 14
GRID_MARGIN = 20

_FILTER_ALL = "all"
_FILTER_DONE = "done"
_FILTER_PARTIAL = "partial"


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


def _elide(text: str, font, width: int) -> str:
    if not text:
        return ""
    return QFontMetrics(font).elidedText(text, Qt.TextElideMode.ElideRight, width)


def _sipDelete(widget) -> None:
    """立刻释放 Qt 对象的 Python 包装层。

    deleteLater 只是把析构排进事件队列，重新建卡片的循环里旧实例会一直挂着。
    这里用 sip.delete 主动回收（PySide6 由 shiboken6 提供，缺失时静默降级，
    不影响功能）。
    """
    try:
        import shiboken6

        if shiboken6.Shiboken.isValid(widget):
            shiboken6.delete(widget)
    except Exception:
        pass


class DownloadedCard(CardWidget):
    """一部剧一张卡片：海报 + 剧名 + 「已下载 X/Y 集」+ 打开文件夹。"""

    def __init__(self, record: dict, parent=None):
        super().__init__(parent)
        self._record = record
        self.setFixedSize(CARD_WIDTH, CARD_HEIGHT)
        contentWidth = CARD_WIDTH - 24

        self._poster = QLabel(self)
        self._poster.setFixedSize(POSTER_WIDTH, POSTER_HEIGHT)
        self._poster.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._poster.setStyleSheet(
            f"background-color: rgba(128, 128, 128, 0.14);"
            f"border-radius: {POSTER_RADIUS}px;"
        )

        title = record.get("title") or record.get("seriesId") or "未命名短剧"
        self._title = StrongBodyLabel(self)
        self._title.setText(_elide(title, self._title.font(), contentWidth))
        self._title.setToolTip(title)

        self._count = CaptionLabel(self)
        self._count.setFixedHeight(18)

        self._meta = CaptionLabel(self)
        self._meta.setFixedHeight(18)
        self._meta.setTextColor(QColor(120, 120, 120), QColor(170, 170, 170))

        self._openButton = PrimaryPushButton(FluentIcon.FOLDER, "打开文件夹", self)
        self._openButton.setFixedHeight(30)
        self._openButton.clicked.connect(self._onOpen)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(6)
        layout.addWidget(self._poster, 0, Qt.AlignmentFlag.AlignHCenter)
        layout.addWidget(self._title)
        layout.addWidget(self._count)
        layout.addWidget(self._meta)
        layout.addStretch(1)
        layout.addWidget(self._openButton)

        self.refresh(record)

    def refresh(self, record: dict) -> None:
        """更新集数文案；海报与剧名按 seriesId 不变，无需重载。"""
        self._record = record
        done = int(record.get("downloaded") or 0)
        total = int(record.get("total") or 0)
        status = record.get("status")
        try:
            status = TaskStatus(status)
        except (TypeError, ValueError):
            status = None

        if total and done >= total:
            text = f"✓ 已下载全部 {total} 集"
            color = QColor(30, 150, 80)
        elif status is TaskStatus.RUNNING:
            text = f"↓ 下载中 {done}/{total} 集"
            color = QColor(20, 120, 210)
        elif status is TaskStatus.PAUSED:
            text = f"⏸ 已暂停 {done}/{total} 集"
            color = QColor(180, 130, 20)
        elif status is TaskStatus.FAILED:
            text = f"⚠ 已下载 {done}/{total} 集"
            color = QColor(190, 90, 90)
        else:
            text = f"已下载 {done}/{total} 集"
            color = QColor(120, 120, 120)
        self._count.setText(text)
        self._count.setTextColor(color, color)

        parts = [f"ID {record.get('seriesId', '')}"]
        if total:
            parts.append(f"共 {total} 集")
        self._meta.setText(_elide(" · ".join(parts), self._meta.font(),
                                  CARD_WIDTH - 24))

    def _posterPath(self) -> Path:
        folder = self._record.get("folder") or ""
        if not folder:
            return Path()
        name = self._record.get("posterFile") or POSTER_NAME
        return Path(folder) / name

    def loadPoster(self) -> None:
        """优先读任务目录里已下载的海报；没有则留灰色占位。"""
        path = self._posterPath()
        pixmap = QPixmap()
        if path and path.exists() and pixmap.load(str(path)):
            self.setPosterPixmap(pixmap)

    def setPosterPixmap(self, pixmap: QPixmap) -> None:
        # KeepAspectRatio：海报完整显示，不裁剪边缘
        scaled = pixmap.scaled(
            POSTER_WIDTH, POSTER_HEIGHT,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self._poster.setPixmap(_roundedPixmap(scaled, POSTER_RADIUS))
        # 海报比例不等于容器比例时贴图会居中留白，缩短标签避免露出灰底
        self._poster.setFixedSize(scaled.width(), scaled.height())
        self._poster.setStyleSheet("")

    def _onOpen(self) -> None:
        folder = self._record.get("folder") or ""
        if folder:
            revealInFolder(str(folder))
        else:
            InfoBar.warning(
                "找不到文件夹", "该任务还没有产出文件",
                duration=3000, position=InfoBarPosition.BOTTOM_RIGHT,
                parent=self.window(),
            )


class DownloadedPage(PackPage, PageScrollArea):
    """已下载页：按剧归纳已下载集数。"""

    icon = FluentIcon.LIBRARY
    title = N("PackPage", "已下载")

    def __init__(self, pack, parent=None):
        super().__init__(parent)
        self._pack = pack
        self.setObjectName("DownloadedPage")
        self._cards: list[DownloadedCard] = []
        self._taskService = None
        self._signalsBound = False
        self._filter = _FILTER_ALL
        self._records: list[dict] = []

        self._scrollWidget = QWidget()
        self._layout = QVBoxLayout(self._scrollWidget)
        self._layout.setSpacing(12)
        self._layout.setContentsMargins(GRID_MARGIN, 16, GRID_MARGIN, 16)

        self._grid = QGridLayout()
        self._grid.setSpacing(GRID_SPACING)
        self._grid.setContentsMargins(0, 0, 0, 0)

        self._empty = CaptionLabel("还没有已下载的短剧\n去「短剧」页选一部下载吧", self._scrollWidget)
        self._empty.setTextColor(QColor(120, 120, 120), QColor(170, 170, 170))
        self._empty.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._initTopBar()
        self._layout.addLayout(self._buildTopBar())
        self._layout.addWidget(self._empty, 0, Qt.AlignmentFlag.AlignCenter)
        self._layout.addLayout(self._grid)
        self._layout.addStretch(1)

        self.setWidget(self._scrollWidget)
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.enableTransparentBackground()

        self._refreshTimer = QTimer(self, singleShot=True)
        self._refreshTimer.setInterval(0)
        self._refreshTimer.timeout.connect(self._refresh)
        self._refreshTimer.start()

    def _startup(self):
        pass

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self._ensureTaskService()
        self._bindSignals()
        self._refreshTimer.start()

    # ── 界面 ──

    def _initTopBar(self):
        self._filterSegment = SegmentedToggleToolWidget(self._scrollWidget)
        self._filterSegment.addItem(_FILTER_ALL, FluentIcon.HOME)
        self._filterSegment.addItem(_FILTER_DONE, FluentIcon.ACCEPT)
        self._filterSegment.addItem(_FILTER_PARTIAL, FluentIcon.DOWNLOAD)
        self._filterSegment.setCurrentItem(_FILTER_ALL)
        for key, tip in (
            (_FILTER_ALL, "全部短剧"),
            (_FILTER_DONE, "已下完"),
            (_FILTER_PARTIAL, "未下完"),
        ):
            widget = self._filterSegment.widget(key)
            widget.setToolTip(tip)
            widget.installEventFilter(ToolTipFilter(widget))
        self._filterSegment.currentItemChanged.connect(self._onFilterChanged)

        self._summary = CaptionLabel(self._scrollWidget)
        self._summary.setTextColor(QColor(120, 120, 120), QColor(170, 170, 170))

    def _buildTopBar(self) -> QHBoxLayout:
        bar = QHBoxLayout()
        bar.setSpacing(10)
        bar.addWidget(self._filterSegment)
        bar.addWidget(self._summary)
        bar.addStretch(1)
        return bar

    # ── 数据 ──

    def _ensureTaskService(self):
        if self._taskService is not None:
            return self._taskService
        self._taskService = getattr(self.window(), "taskService", None)
        return self._taskService

    def _bindSignals(self):
        svc = self._ensureTaskService()
        if svc is None or self._signalsBound:
            return
        self._signalsBound = True
        for name in ("taskAdded", "taskRemoved", "taskStarted", "taskPaused",
                     "taskCompleted", "taskFailed", "queueChanged"):
            signal = getattr(svc, name, None)
            if signal is not None:
                signal.connect(lambda *_: self._refreshTimer.start())

    def _collectRecords(self) -> list[dict]:
        """把短剧任务按 seriesId 归并为「一剧一条」的下载记录。"""
        svc = self._ensureTaskService()
        if svc is None:
            return []
        records: dict[str, dict] = {}
        for task in svc.tasks:
            if getattr(task, "packId", "") != "drama":
                continue
            # 只有 drama://hongguo/{seriesId} 才算短剧任务。
            # 兜底分支必须同样校验 hostname，否则别的 drama 协议任务
            # （如 drama://other/...）会被误当成一部剧塞进列表。
            parsed = urlparse(task.url or "")
            if parsed.scheme != "drama" or parsed.hostname != "hongguo":
                continue
            seriesId = parsed.path.strip("/")
            title = ""
            try:
                seriesId, title, _picks, _cat, _ch, _q = parseDramaTaskUrl(task.url)
            except Exception:
                pass
            if not seriesId:
                continue

            files = task.files or []
            total = len(files)
            if total:
                done = sum(1 for f in files if getattr(f, "completed", False))
            else:
                done = sum(1 for s in task.steps
                           if s.status == TaskStatus.COMPLETED)

            record = {
                "seriesId": seriesId,
                "title": title or task.name or seriesId,
                "status": int(task.status),
                "total": total,
                "downloaded": done,
                "folder": task.outputPath,
                "posterFile": getattr(task, "posterFile", "") or POSTER_NAME,
            }
            existing = records.get(seriesId)
            # 同一 seriesId 理论上只有一条；保险起见保留进度更靠前的
            if existing is None or done > existing["downloaded"]:
                records[seriesId] = record
        return sorted(
            records.values(),
            key=lambda r: (r["downloaded"] < r["total"], -r["downloaded"]),
        )

    def _onFilterChanged(self, key: str) -> None:
        self._filter = key
        self._refresh()

    def _refresh(self) -> None:
        self._records = self._collectRecords()
        records = self._records
        if self._filter == _FILTER_DONE:
            records = [r for r in records if r["total"] and r["downloaded"] >= r["total"]]
        elif self._filter == _FILTER_PARTIAL:
            records = [r for r in records if not r["total"] or r["downloaded"] < r["total"]]

        totalEpisodes = sum(r["total"] for r in self._records)
        doneEpisodes = sum(r["downloaded"] for r in self._records)
        self._summary.setText(
            f"共 {len(self._records)} 部剧 · 已下载 {doneEpisodes}/{totalEpisodes} 集"
            if self._records else ""
        )

        self._clearCards()
        if not records:
            self._empty.setText(
                "还没有已下载的短剧\n去「短剧」页选一部下载吧"
                if not self._records else "该筛选下暂无短剧"
            )
            self._empty.show()
            return
        self._empty.hide()

        for record in records:
            card = DownloadedCard(record, self._scrollWidget)
            card.loadPoster()
            self._cards.append(card)
        self._reflowCards()

    def _clearCards(self):
        for card in self._cards:
            self._grid.removeWidget(card)
            # setParent(None) 摘离父子树 → deleteLater 排进事件队列回收 Qt 侧 →
            # _sipDelete 立刻释放 Python 包装对象。少了最后一步，反复刷新 20 次
            # 后进程里仍堆着 140+ 个 DownloadedCard 实例（存活数只增不减）。
            card.setParent(None)
            card.deleteLater()
            _sipDelete(card)
        self._cards.clear()

    def _reflowCards(self):
        while self._grid.count():
            self._grid.takeAt(0)
        width = self.viewport().width() - GRID_MARGIN * 2 + GRID_SPACING
        cols = max(1, width // (CARD_WIDTH + GRID_SPACING))
        # 清掉上一次留下的列拉伸，否则残留的拉伸因子会把列宽越挤越歪
        for column in range(self._grid.columnCount() + 1):
            self._grid.setColumnStretch(column, 0)
        for i, card in enumerate(self._cards):
            self._grid.addWidget(card, i // cols, i % cols)
        # 末尾留一列弹性空位，卡片左对齐而不是被均匀摊开
        self._grid.setColumnStretch(cols, 1)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, "_grid"):
            self._reflowCards()
