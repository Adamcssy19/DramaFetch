from __future__ import annotations

"""选集对话框：海报/ID 头部 + 区间语法/逐集按钮选集 + 渠道清晰度 + 输出目录。"""

import asyncio
import threading
from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPixmap
from PySide6.QtWidgets import QGridLayout, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget
from qfluentwidgets import (
    BodyLabel,
    CaptionLabel,
    ComboBox,
    FluentIcon,
    InfoBar,
    InfoBarPosition,
    LineEdit,
    MessageBoxBase,
    PrimaryPushButton,
    ScrollArea,
    StrongBodyLabel,
    ToolTipFilter,
    TransparentToolButton,
)

from app.models.task import ResourceTaskOptions
from app.view.components.card_groups import OptionCardGroup
from app.view.components.option_cards import OutputFolderCard

from . import api
from .api import parsePickSpec
from .task import buildDramaTaskUrl

POSTER_WIDTH, POSTER_HEIGHT = 88, 118
POSTER_RADIUS = 8
GRID_COLUMNS = 8
GRID_HEIGHT = 150

CHANNEL_OPTIONS = [
    ("智能（自动选择可用渠道）", "auto"),
    ("App源（原画，最清晰）", "app"),
    ("官网直链", "web"),
    ("备用解析", "backup"),
    ("镜像站", "mirror"),
]
CHANNEL_VALUES = [v for _, v in CHANNEL_OPTIONS]
QUALITY_OPTIONS = [
    ("最高清晰度", 0),
    ("1080P", 1080),
    ("720P", 720),
    ("540P", 540),
    ("480P", 480),
]
QUALITY_VALUES = [v for _, v in QUALITY_OPTIONS]

_EPISODE_QSS = """
QPushButton#epBtn {{
    border: 1px solid {}; border-radius: 4px;
    background: transparent; min-height: 26px; font-size: 12px;
}}
QPushButton#epBtn:hover {{ background: rgba(128, 128, 128, 0.15); }}
QPushButton#epBtn:checked {{ background: {}; color: white; border: none; font-weight: 600; }}
"""


def _accentColor() -> str:
    try:
        from qfluentwidgets import qconfig

        value = qconfig.themeColor.value
        return value.name(QColor.HexRgb) if isinstance(value, QColor) else str(value)
    except Exception:
        return "#008577"


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


def _makeCopyButton(text: str, ref=None) -> TransparentToolButton:
    button = TransparentToolButton(FluentIcon.COPY)
    metrics = ref.fontMetrics() if ref is not None else button.fontMetrics()
    size = max(metrics.height() + 2, 16)
    button.setFixedSize(size, size)
    button.setIconSize(button.size() * 0.55)
    button.setToolTip("复制")
    button.installEventFilter(ToolTipFilter(button))
    button.clicked.connect(lambda: QApplication_copy(text))
    return button


def QApplication_copy(text: str):
    from PySide6.QtWidgets import QApplication

    QApplication.clipboard().setText(text)


class EpisodePickerDialog(MessageBoxBase):
    coverLoaded = Signal(bytes)

    def __init__(self, pack, drama, parent=None):
        super().__init__(parent)
        self._pack = pack
        self._drama = drama
        self._options = None
        self._updatingEdit = False
        self._total = len(drama.vidList)
        self._picked: set[int] = set()

        # ── 头部：海报 + 剧名/ID ──────────────────────────────
        self._posterLabel = QLabel(self)
        self._posterLabel.setFixedSize(POSTER_WIDTH, POSTER_HEIGHT)
        self._posterLabel.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._posterLabel.setStyleSheet(
            f"background-color: rgba(128, 128, 128, 0.18); border-radius: {POSTER_RADIUS}px;")

        accent = _accentColor()

        self._titleLabel = StrongBodyLabel(drama.title, self)
        self._titleLabel.setToolTip(drama.title)
        titleRow = QHBoxLayout()
        titleRow.setContentsMargins(0, 0, 0, 0)
        titleRow.setSpacing(4)
        titleRow.addWidget(self._titleLabel)
        titleRow.addWidget(_makeCopyButton(drama.title, self._titleLabel))
        titleRow.addStretch(1)

        self._idLabel = CaptionLabel(f"ID {drama.seriesId}", self)
        self._idLabel.setToolTip(drama.seriesId)
        self._idLabel.setTextColor(QColor(120, 120, 120), QColor(170, 170, 170))
        idRow = QHBoxLayout()
        idRow.setContentsMargins(0, 0, 0, 0)
        idRow.setSpacing(4)
        idRow.addWidget(self._idLabel)
        idRow.addWidget(_makeCopyButton(drama.seriesId, self._idLabel))
        idRow.addStretch(1)

        self._metaLabel = CaptionLabel(f"共 {self._total} 集 · 选择要下载的剧集", self)
        self._metaLabel.setTextColor(QColor(120, 120, 120), QColor(170, 170, 170))

        infoColumn = QVBoxLayout()
        infoColumn.setContentsMargins(0, 0, 0, 0)
        infoColumn.setSpacing(6)
        infoColumn.addLayout(titleRow)
        infoColumn.addLayout(idRow)
        infoColumn.addWidget(self._metaLabel)
        infoColumn.addStretch(1)

        header = QHBoxLayout()
        header.setSpacing(12)
        header.addWidget(self._posterLabel)
        header.addLayout(infoColumn, 1)

        # ── 选集输入 ─────────────────────────────────────────
        self._edit = LineEdit(self)
        self._edit.setPlaceholderText("选集范围，如：1-50、1-10, 25, 30-45、-20（前20集）")
        self._edit.setClearButtonEnabled(True)
        self._edit.setText("1-20")

        self._hintLabel = CaptionLabel("", self)
        self._hintLabel.setTextColor(QColor(160, 160, 160), QColor(140, 140, 140))

        # ── 逐集按钮网格（含「全选」） ────────────────────────
        gridHost = QWidget(self)
        gridHost.setObjectName("episodeGridHost")
        gridHost.setStyleSheet(_EPISODE_QSS.format("rgba(128, 128, 128, 0.4)", accent))
        grid = QGridLayout(gridHost)
        grid.setContentsMargins(4, 4, 4, 4)
        grid.setSpacing(6)

        self._selectAllButton = PrimaryPushButton("全选", gridHost)
        self._selectAllButton.setFixedHeight(28)
        self._selectAllButton.clicked.connect(self._onSelectAll)
        grid.addWidget(self._selectAllButton, 0, 0)

        self._episodeButtons: dict[int, QPushButton] = {}
        for index in range(1, self._total + 1):
            button = QPushButton(str(index), gridHost)
            button.setObjectName("epBtn")
            button.setCheckable(True)
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.setToolTip(f"第 {index} 集")
            button.clicked.connect(
                lambda checked, i=index: self._onEpisodeClicked(i, checked))
            self._episodeButtons[index] = button
            row, col = divmod(index, GRID_COLUMNS)
            # 第 0 格是「全选」，集数从第 1 列排到第 7 列，之后每行 8 格
            grid.addWidget(button, row, col + 1 if row == 0 else col)

        # 注意：ScrollArea 的父级**不能**是随后 setWidget 的那个控件，
        # 否则父子关系成环，Qt 布局会无限递归直接卡死（无异常、无日志）。
        # 这里先挂在 self 下，稍后由 viewLayout.addWidget 接管。
        scroll = ScrollArea(self)
        scroll.setWidget(gridHost)
        scroll.setWidgetResizable(True)
        scroll.setFixedHeight(GRID_HEIGHT)
        try:
            scroll.enableTransparentBackground()
        except AttributeError:
            pass

        # ── 渠道 / 清晰度 ────────────────────────────────────
        self._channelBox = ComboBox(self)
        for label, _ in CHANNEL_OPTIONS:
            self._channelBox.addItem(label)
        self._channelBox.setCurrentIndex(0)

        self._qualityBox = ComboBox(self)
        for label, _ in QUALITY_OPTIONS:
            self._qualityBox.addItem(label)
        self._qualityBox.setCurrentIndex(0)
        self._qualityBox.setToolTip("对 App源 / 备用解析 生效，选择最接近的清晰度")

        channelLabel = CaptionLabel("下载渠道", self)
        qualityLabel = CaptionLabel("清晰度", self)
        channelRow = QHBoxLayout()
        channelRow.setContentsMargins(0, 0, 0, 0)
        channelRow.setSpacing(8)
        channelRow.addWidget(channelLabel)
        channelRow.addWidget(self._channelBox, 1)
        channelRow.addSpacing(16)
        channelRow.addWidget(qualityLabel)
        channelRow.addWidget(self._qualityBox, 1)

        # ── 输出目录 ─────────────────────────────────────────
        self._optionGroup = OptionCardGroup(self)
        self._optionGroup.addCard(OutputFolderCard(self._optionGroup))

        self.yesButton.setText("开始下载")
        self.cancelButton.setText("取消")

        self.viewLayout.addLayout(header)
        self.viewLayout.addSpacing(4)
        self.viewLayout.addWidget(self._edit)
        self.viewLayout.addWidget(self._hintLabel)
        self.viewLayout.addWidget(scroll)
        self.viewLayout.addSpacing(4)
        self.viewLayout.addLayout(channelRow)
        self.viewLayout.addWidget(self._optionGroup)

        self.widget.setFixedWidth(620)
        self._edit.textChanged.connect(self._onEditChanged)
        self._applySpec(self._edit.text())

        self.yesButton.clicked.disconnect()
        self.yesButton.clicked.connect(self._onStartClicked)

        if drama.cover:
            self.coverLoaded.connect(self._setPoster)
            threading.Thread(target=self._loadPoster, daemon=True).start()

    # ── 海报 ────────────────────────────────────────────────
    def _loadPoster(self):
        try:
            data = asyncio.run(api.getBytes(self._drama.cover))
            if data:
                self.coverLoaded.emit(data)
        except RuntimeError:
            pass  # 对话框已销毁
        except Exception:
            pass

    def _setPoster(self, data: bytes):
        pixmap = QPixmap()
        if not pixmap.loadFromData(data):
            return
        # KeepAspectRatio：海报按 3:4 完整显示，裁掉边缘会丢失剧名/人物构图
        scaled = pixmap.scaled(
            POSTER_WIDTH, POSTER_HEIGHT,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self._posterLabel.setPixmap(_roundedPixmap(scaled, POSTER_RADIUS))
        self._posterLabel.setStyleSheet("")

    # ── 选集逻辑 ────────────────────────────────────────────
    def _onSelectAll(self):
        self._picked = set(range(1, self._total + 1))
        self._updatingEdit = True
        self._edit.setText("all")
        self._updatingEdit = False
        self._refreshButtons()
        self._refreshHint()

    def _onEpisodeClicked(self, index: int, checked: bool):
        if checked:
            self._picked.add(index)
        else:
            self._picked.discard(index)
        self._updatingEdit = True
        self._edit.setText(self._formatPicks())
        self._updatingEdit = False
        self._refreshHint()

    def _onEditChanged(self):
        if self._updatingEdit:
            return
        self._applySpec(self._edit.text())

    def _applySpec(self, text: str):
        self._picked = set(parsePickSpec(text, self._total))
        self._refreshButtons()
        self._refreshHint()

    def _refreshButtons(self):
        for index, button in self._episodeButtons.items():
            button.setChecked(index in self._picked)

    def _formatPicks(self) -> str:
        picks = sorted(self._picked)
        if not picks:
            return ""
        if len(picks) == self._total:
            return "all"
        runs: list[tuple[int, int]] = []
        start = previous = picks[0]
        for value in picks[1:]:
            if value == previous + 1:
                previous = value
                continue
            runs.append((start, previous))
            start = previous = value
        runs.append((start, previous))
        return ", ".join(f"{a}" if a == b else f"{a}-{b}" for a, b in runs)

    def _refreshHint(self):
        count = len(self._picked)
        self._hintLabel.setText(
            f"已选 {count} 集，创建任务时会逐集解析下载地址，集数越多等待越久"
            if count else "尚未选中任何剧集"
        )

    def _onStartClicked(self):
        picks = sorted(self._picked)
        if not picks:
            InfoBar.warning("还没有选中剧集", "请填写选集范围或点击集数按钮",
                            duration=3000, position=InfoBarPosition.BOTTOM_RIGHT,
                            parent=self.window())
            return
        options = dict(self._optionGroup.options())
        outputFolder = Path(options.get("outputFolder") or ".")

        url = buildDramaTaskUrl(
            self._drama.seriesId, self._drama.title, picks, self._drama.category,
            channel=CHANNEL_VALUES[self._channelBox.currentIndex()],
            quality=QUALITY_VALUES[self._qualityBox.currentIndex()],
        )
        window = self.window()

        def onParsed(task):
            self._pack.addTask(task)

        def onFailed(error: str):
            InfoBar.error("创建下载任务失败", str(error), duration=-1,
                          position=InfoBarPosition.BOTTOM_RIGHT, parent=window)

        self._pack.submit(
            self._pack.parse(ResourceTaskOptions(
                url=url,
                name=self._drama.title,
                outputFolder=outputFolder,
            )),
            done=onParsed, failed=onFailed, owner=window,
        )
        self.accept()
