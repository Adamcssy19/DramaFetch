from __future__ import annotations

"""选集对话框：区间语法选集 + 输出目录，确认后创建下载任务。"""

from pathlib import Path

from PySide6.QtGui import QColor
from PySide6.QtWidgets import QHBoxLayout, QVBoxLayout, QWidget
from qfluentwidgets import (
    BodyLabel,
    CaptionLabel,
    FluentIcon,
    InfoBar,
    InfoBarPosition,
    LineEdit,
    MessageBoxBase,
    PushButton,
    StrongBodyLabel,
)

from app.models.task import ResourceTaskOptions
from app.view.components.card_groups import OptionCardGroup
from app.view.components.option_cards import OutputFolderCard

from .api import parsePickSpec
from .task import buildDramaTaskUrl


class EpisodePickerDialog(MessageBoxBase):
    def __init__(self, pack, drama, parent=None):
        super().__init__(parent)
        self._pack = pack
        self._drama = drama
        self._options = None

        total = len(drama.vidList)

        self._titleLabel = StrongBodyLabel(drama.title, self)
        self._metaLabel = CaptionLabel(f"共 {total} 集 · 选择要下载的剧集", self)
        self._metaLabel.setTextColor(QColor(120, 120, 120), QColor(170, 170, 170))

        self._edit = LineEdit(self)
        self._edit.setPlaceholderText("选集范围，如：1-50、1-10, 25, 30-45、-20（前20集）")
        self._edit.setClearButtonEnabled(True)
        self._edit.setText("1-20")

        quickBar = QHBoxLayout()
        quickBar.setSpacing(8)
        for text, spec in (("全选", "all"), ("前 50", "-50"), ("后 50", "50-")):
            button = PushButton(text, self)
            button.clicked.connect(lambda _=False, s=spec: self._applyQuick(s))
            quickBar.addWidget(button)
        quickBar.addStretch(1)

        self._hintLabel = CaptionLabel("", self)
        self._hintLabel.setTextColor(QColor(160, 160, 160), QColor(140, 140, 140))

        self._optionGroup = OptionCardGroup(self)
        self._optionGroup.addCard(OutputFolderCard(self._optionGroup))

        self.yesButton.setText("开始下载")
        self.cancelButton.setText("取消")

        self.viewLayout.addWidget(self._titleLabel)
        self.viewLayout.addWidget(self._metaLabel)
        self.viewLayout.addWidget(self._edit)
        self.viewLayout.addLayout(quickBar)
        self.viewLayout.addWidget(self._hintLabel)
        self.viewLayout.addWidget(self._optionGroup)

        self.widget.setFixedWidth(620)
        self._edit.textChanged.connect(self._refreshHint)
        self._refreshHint()

        self.yesButton.clicked.disconnect()
        self.yesButton.clicked.connect(self._onStartClicked)

    def _applyQuick(self, spec: str):
        self._edit.setText(spec)

    def _pickedCount(self) -> int:
        return len(parsePickSpec(self._edit.text(), len(self._drama.vidList)))

    def _refreshHint(self):
        count = self._pickedCount()
        self._hintLabel.setText(
            f"已选 {count} 集，创建任务时会逐集解析下载地址，集数越多等待越久"
            if count else "尚未选中任何剧集"
        )

    def _onStartClicked(self):
        picks = parsePickSpec(self._edit.text(), len(self._drama.vidList))
        if not picks:
            InfoBar.warning("还没有选中剧集", "请填写选集范围，如 1-20",
                            duration=3000, position=InfoBarPosition.BOTTOM_RIGHT,
                            parent=self.window())
            return
        options = dict(self._optionGroup.options())
        outputFolder = Path(options.get("outputFolder") or ".")

        url = buildDramaTaskUrl(
            self._drama.seriesId, self._drama.title, picks, self._drama.category,
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
