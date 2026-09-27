from __future__ import annotations

"""短剧任务卡片：竖版海报圆角图标 + ID + 已下载集数。"""

import re
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import Qt, QT_TRANSLATE_NOOP as N
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPixmap
from PySide6.QtWidgets import QApplication, QHBoxLayout
from qfluentwidgets import FluentIcon, ToolTipFilter, TransparentToolButton, themeColor

from app.models.task import TaskStatus
from app.view.cards.task_cards import (
    TaskCard, FieldSpec, ButtonSpec, SPEED_FIELD, ETA_FIELD, SIZE_FIELD,
)

from .task import POSTER_NAME, parseDramaTaskUrl

ICON_SIZE = 48
ICON_RADIUS = 8


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


def _makeCopyButton(text: str, ref=None):
    btn = TransparentToolButton(FluentIcon.COPY)
    fm = ref.fontMetrics() if ref is not None else btn.fontMetrics()
    h = max(fm.height() + 2, 14)
    btn.setFixedSize(h, h)
    btn.setToolTip("复制")
    btn.installEventFilter(ToolTipFilter(btn))
    btn.clicked.connect(lambda: QApplication.clipboard().setText(text))
    return btn


def toDramaIdText(task, speed: int, received: int) -> str | None:
    try:
        seriesId = parseDramaTaskUrl(task.url)[0]
    except Exception:
        return None
    return f"ID {seriesId}" if seriesId else None


def toEpisodesText(task, speed: int, received: int) -> str | None:
    steps = task.steps
    if not steps:
        return None
    done = sum(1 for s in steps if s.status == TaskStatus.COMPLETED)
    if task.status == TaskStatus.COMPLETED:
        return f"共 {len(steps)} 集"
    return f"已下 {done}/{len(steps)} 集"


ID_FIELD = FieldSpec("id", FluentIcon.TAG, {None: toDramaIdText})
EPISODE_FIELD = FieldSpec("episode", FluentIcon.VIDEO, {None: toEpisodesText})


class DramaTaskCard(TaskCard):
    infoFields = [ID_FIELD, EPISODE_FIELD, SPEED_FIELD, ETA_FIELD, SIZE_FIELD]
    buttons = [b for b in TaskCard.buttons if b.name != "selectFiles"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.idLabel.setToolTip(self._dramaId())
        self.idLabel.installEventFilter(ToolTipFilter(self.idLabel))
        self.episodeLabel.installEventFilter(ToolTipFilter(self.episodeLabel))
        self.statusLabel.installEventFilter(ToolTipFilter(self.statusLabel))

        # 剧名右侧复制图标（同字号）
        self._titleCopy = _makeCopyButton(self._task.name, self.nameLabel)
        idx = self.contentLayout.indexOf(self.nameLabel)
        self.contentLayout.removeWidget(self.nameLabel)
        titleRow = QHBoxLayout()
        titleRow.setContentsMargins(0, 0, 0, 0)
        titleRow.setSpacing(4)
        # nameLabel 的水平 sizePolicy 是 Ignored（基类设定），不给 stretch
        # 的话布局会把宽度全让给拉伸项，剧名会被压成 0 宽而看不见。
        titleRow.addWidget(self.nameLabel, 1)
        titleRow.addWidget(self._titleCopy, 0)
        self.contentLayout.insertLayout(idx, titleRow)

        # ID 右侧复制图标（紧贴 ID 文本）
        dramaId = self._dramaId()
        if dramaId:
            self._idCopy = _makeCopyButton(dramaId, self.idLabel)
            self.infoLayout.insertWidget(1, self._idCopy)

    def _dramaId(self) -> str:
        try:
            return parseDramaTaskUrl(self._task.url)[0]
        except Exception:
            return ""

    def _episodeNumberOf(self, step) -> int | None:
        name = Path(getattr(step, "outputFile", "") or "").stem
        match = re.search(r"(\d+)\s*$", name)
        if match:
            return int(match.group(1))
        fileIndex = getattr(step, "fileIndex", None)
        return None if fileIndex is None else fileIndex + 1

    def _refreshForStatus(self, task: Task) -> None:
        super()._refreshForStatus(task)
        if task.status == TaskStatus.RUNNING:
            step = next((s for s in task.steps if s.status == TaskStatus.RUNNING), None)
            if step is None:
                return
            stage = (getattr(step, "stageText", "") or "下载中").strip()
            episode = self._episodeNumberOf(step)
            text = f"正在下载 第{episode}集 · {stage}" if episode else f"正在下载 · {stage}"
            if stage == "下载中" and step.progress > 0:
                text += f" {int(step.progress)}%"
            self.statusLabel.setTextColor(QColor(themeColor()))
            self.statusLabel.setText(text)
            self.statusLabel.show()
        elif task.status == TaskStatus.COMPLETED and not self._isFileMissing:
            total = len(task.steps)
            if total:
                self.statusLabel.setText(f"全 {total} 集下载完成 🎉")
                if task.completedAt:
                    self.statusLabel.setToolTip(datetime.fromtimestamp(task.completedAt)
                                                .strftime("完成于 %Y-%m-%d %H:%M:%S"))
        elif task.status == TaskStatus.PAUSED:
            done = sum(1 for s in task.steps if s.status == TaskStatus.COMPLETED)
            if len(task.steps):
                self.statusLabel.setText(f"已暂停 · 已下 {done}/{len(task.steps)} 集")

    def refresh(self, force: bool = False) -> None:
        super().refresh(force)
        self.episodeLabel.setToolTip(self._episodeTooltip())

    def _episodeTooltip(self) -> str:
        done = [Path(s.outputFile).stem for s in self._task.steps
                if s.status == TaskStatus.COMPLETED and getattr(s, "outputFile", "")]
        if not done:
            return ""
        shown = "、".join(done[:30])
        if len(done) > 30:
            shown += f" 等 {len(done)} 集"
        return f"已下载 {len(done)} 集：{shown}"

    def _refreshIcon(self) -> None:
        poster = Path(self._task.outputPath) / (self._task.posterFile or POSTER_NAME)
        pixmap = QPixmap()
        if poster.exists() and pixmap.load(str(poster)):
            scaled = pixmap.scaled(
                ICON_SIZE, ICON_SIZE,
                Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                Qt.TransformationMode.SmoothTransformation,
            )
            x = max(0, (scaled.width() - ICON_SIZE) // 2)
            y = max(0, (scaled.height() - ICON_SIZE) // 2)
            scaled = scaled.copy(x, y, min(ICON_SIZE, scaled.width()),
                                 min(ICON_SIZE, scaled.height()))
            self.iconLabel.setPixmap(_roundedPixmap(scaled, ICON_RADIUS))
            self.iconLabel.setFixedSize(ICON_SIZE, ICON_SIZE)
            return
        super()._refreshIcon()
