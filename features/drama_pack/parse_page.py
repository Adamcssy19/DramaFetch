from __future__ import annotations

"""解析页：粘贴分享链接 → 去水印下载 / 提取文案。

位于排行榜页之后（drama_pack.pack.pages 中排在 RankPage 后面），
与短剧/排行榜共用同一侧边栏入口。去水印走 parser_api（parse-video-py），
文案提取走 parser_asr（可插拔 ASR 接口）。
"""

from pathlib import Path

from PySide6.QtCore import QT_TRANSLATE_NOOP as N, Qt, QUrl
from PySide6.QtGui import QClipboard, QColor, QPainter, QPainterPath, QPixmap
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkRequest
from PySide6.QtWidgets import QApplication, QHBoxLayout, QLabel, QTextEdit, QVBoxLayout, QWidget

from qfluentwidgets import (
    BodyLabel,
    CaptionLabel,
    CardWidget,
    FluentIcon,
    InfoBar,
    InfoBarPosition,
    LineEdit,
    PrimaryPushButton,
    PushButton,
    StrongBodyLabel,
    TransparentToolButton,
    ToolTipFilter,
)

from app.config.cfg import cfg
from app.models.pack import PackPage
from app.platform.filesystem import toSafeFilename
from app.view.components.scroll_area import ScrollArea as PageScrollArea
from http_pack.task import HttpTask, HttpTaskStep

from . import parser_api, parser_asr


COVER_W, COVER_H, COVER_R = 150, 200, 10


def _rounded_pixmap(pixmap: QPixmap, radius: int) -> QPixmap:
    if pixmap.isNull():
        return pixmap
    out = QPixmap(pixmap.size())
    out.fill(Qt.GlobalColor.transparent)
    painter = QPainter(out)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    path = QPainterPath()
    path.addRoundedRect(0, 0, pixmap.width(), pixmap.height(), radius, radius)
    painter.setClipPath(path)
    painter.drawPixmap(0, 0, pixmap)
    painter.end()
    return out


class _CoverLoader:
    def __init__(self, label: QLabel):
        self._label = label
        self._mgr = QNetworkAccessManager()
        self._mgr.finished.connect(self._on_finished)

    def load(self, url: str):
        if not url:
            return
        self._mgr.get(QNetworkRequest(QUrl(url)))

    def _on_finished(self, reply):
        try:
            data = reply.readAll().data()
            pix = QPixmap()
            if pix.loadFromData(data):
                scaled = pix.scaled(
                    COVER_W, COVER_H,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
                self._label.setPixmap(_rounded_pixmap(scaled, COVER_R))
        finally:
            reply.deleteLater()


def build_parse_task(title: str, video_url: str) -> HttpTask:
    """用 http_pack 的底座把无水印直链落成一条下载任务。"""
    safe = toSafeFilename(title or "解析视频", fallback="解析视频")
    base = Path(str(cfg.downloadFolder.value))
    sub = str(cfg.dramaSubfolder.value or "").strip()
    if sub:
        base = base / toSafeFilename(sub)
    out_file = str(base / safe / f"{safe}.mp4")
    task = HttpTask(
        name=safe,
        url=video_url,
        packId="http",
        outputFolder=Path(str(cfg.downloadFolder.value)),
    )
    task.addStep(HttpTaskStep(stepIndex=1, url=video_url, subworkerCount=8, outputFile=out_file))
    return task


class ParsePage(PackPage, PageScrollArea):
    icon = FluentIcon.SEARCH
    title = N("PackPage", "解析")

    def __init__(self, pack, parent=None):
        super().__init__(parent)
        self._pack = pack
        self.setObjectName("ParsePage")
        self._result: parser_api.ParseResult | None = None
        self._coverLoader = None

        self._scrollWidget = QWidget()
        self._layout = QVBoxLayout(self._scrollWidget)
        self._layout.setSpacing(14)
        self._layout.setContentsMargins(20, 16, 20, 16)

        self._initTopBar()
        self._initResultCard()
        self._initTranscript()

        self._layout.addStretch(1)
        self.setWidget(self._scrollWidget)
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.enableTransparentBackground()

    # ── 界面 ──

    def _initTopBar(self):
        self._input = LineEdit(self._scrollWidget)
        self._input.setPlaceholderText("粘贴抖音 / 快手 / 小红书等分享链接，例如 https://v.douyin.com/xxxx")
        self._input.returnPressed.connect(self._onParse)

        self._parseBtn = PrimaryPushButton(FluentIcon.SEARCH, "解析", self._scrollWidget)
        self._parseBtn.clicked.connect(self._onParse)
        self._clearBtn = PushButton(FluentIcon.DELETE, "清空", self._scrollWidget)
        self._clearBtn.clicked.connect(self._onClear)

        bar = QHBoxLayout()
        bar.setSpacing(8)
        bar.addWidget(self._input, 1)
        bar.addWidget(self._parseBtn)
        bar.addWidget(self._clearBtn)
        self._layout.addLayout(bar)

        self._hint = CaptionLabel(self._scrollWidget)
        self._hint.setText(
            "解析由开源库 parse-video-py 提供（26 平台，纯 Python）；"
            "未安装时首次解析会提示安装方式。"
        )
        self._hint.setTextColor(QColor(120, 120, 120), QColor(170, 170, 170))
        self._layout.addWidget(self._hint)

    def _initResultCard(self):
        self._card = CardWidget(self._scrollWidget)
        self._card.setVisible(False)

        self._cover = QLabel(self._card)
        self._cover.setFixedSize(COVER_W, COVER_H)
        self._cover.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._title = StrongBodyLabel(self._card)
        self._titleCopy = self._makeCopyBtn("")
        titleRow = QHBoxLayout()
        titleRow.setSpacing(4)
        titleRow.addWidget(self._title)
        titleRow.addWidget(self._titleCopy)
        titleRow.addStretch(1)

        self._sub = CaptionLabel(self._card)
        self._sub.setTextColor(QColor(120, 120, 120), QColor(170, 170, 170))

        self._urlLine = LineEdit(self._card)
        self._urlLine.setReadOnly(True)
        self._urlCopyBtn = self._makeCopyBtn("")
        urlRow = QHBoxLayout()
        urlRow.setSpacing(4)
        urlRow.addWidget(self._urlLine, 1)
        urlRow.addWidget(self._urlCopyBtn)

        self._dlBtn = PrimaryPushButton(FluentIcon.DOWNLOAD, "去水印下载", self._card)
        self._dlBtn.clicked.connect(self._onDownload)
        self._textBtn = PushButton(FluentIcon.DOCUMENT, "提取文案", self._card)
        self._textBtn.clicked.connect(self._onExtract)
        btnRow = QHBoxLayout()
        btnRow.setSpacing(8)
        btnRow.addWidget(self._dlBtn)
        btnRow.addWidget(self._textBtn)

        meta = QVBoxLayout()
        meta.setSpacing(4)
        meta.addLayout(titleRow)
        meta.addWidget(self._sub)
        meta.addLayout(urlRow)
        meta.addLayout(btnRow)

        body = QHBoxLayout()
        body.setSpacing(12)
        body.addWidget(self._cover)
        body.addLayout(meta, 1)

        cl = QVBoxLayout(self._card)
        cl.setContentsMargins(14, 14, 14, 14)
        cl.setSpacing(8)
        cl.addLayout(body)

        self._layout.addWidget(self._card)

    def _initTranscript(self):
        self._textEdit = QTextEdit(self._scrollWidget)
        self._textEdit.setReadOnly(True)
        self._textEdit.setPlaceholderText("提取的文案（字幕 / 声音转写）会显示在这里")
        self._textEdit.setMinimumHeight(160)
        self._textEdit.setVisible(False)

        self._copyTextBtn = PushButton(FluentIcon.COPY, "复制文案", self._scrollWidget)
        self._copyTextBtn.clicked.connect(self._onCopyText)
        self._copyTextBtn.setVisible(False)

        row = QHBoxLayout()
        row.addStretch(1)
        row.addWidget(self._copyTextBtn)
        self._layout.addWidget(self._textEdit)
        self._layout.addLayout(row)

    def _makeCopyBtn(self, text: str) -> TransparentToolButton:
        btn = TransparentToolButton(FluentIcon.COPY, self._scrollWidget)
        btn.setToolTip("复制")
        btn.installEventFilter(ToolTipFilter(btn))
        btn.clicked.connect(lambda: self._copy(text))
        return btn

    # ── 行为 ──

    def _onParse(self):
        url = self._input.text().strip()
        if not url:
            InfoBar.warning("请输入链接", "", parent=self.window())
            return
        self._parseBtn.setEnabled(False)
        self._card.setVisible(False)
        self._textEdit.setVisible(False)
        self._copyTextBtn.setVisible(False)

        def done(result: parser_api.ParseResult):
            self._parseBtn.setEnabled(True)
            if result.isGallery and not result.ok:
                # 图集作品：没有视频直链，提示暂不支持（本次只做视频去水印）
                InfoBar.warning(
                    "这是图集作品",
                    f"共 {len(result.images)} 张图片，当前仅支持视频去水印下载",
                    duration=5000, position=InfoBarPosition.BOTTOM_RIGHT,
                    parent=self.window(),
                )
                self._showResult(result)
                return
            if not result.ok:
                InfoBar.error("解析失败", "未拿到无水印直链", parent=self.window())
                return
            self._showResult(result)

        def failed(error: str):
            self._parseBtn.setEnabled(True)
            InfoBar.error("解析失败", str(error), duration=-1, parent=self.window())

        self._pack.submit(parser_api.parse(url), done=done, failed=failed, owner=self)

    def _showResult(self, result: parser_api.ParseResult):
        self._result = result
        self._title.setText(result.title or "(无标题)")
        self._titleCopy.clicked.disconnect()
        self._titleCopy.clicked.connect(lambda: self._copy(result.title))

        meta = " · ".join(p for p in (result.platform, result.author) if p)
        if result.isGallery:
            meta = (meta + " · " if meta else "") + f"图集 {len(result.images)} 张"
        self._sub.setText(meta or "解析结果")

        link = result.video_url or (result.images[0]["url"] if result.images else "")
        self._urlLine.setText(link)
        self._urlCopyBtn.clicked.disconnect()
        self._urlCopyBtn.clicked.connect(lambda: self._copy(link))

        self._dlBtn.setEnabled(bool(result.video_url))
        self._textBtn.setEnabled(bool(result.video_url))

        self._card.setVisible(True)
        if result.cover_url:
            if self._coverLoader is None:
                self._coverLoader = _CoverLoader(self._cover)
            self._coverLoader.load(result.cover_url)

    def _onDownload(self):
        if not self._result or not self._result.ok:
            return
        task = build_parse_task(self._result.title, self._result.video_url)
        self._pack.addTask(task)
        InfoBar.success("已加入下载", self._result.title or "视频", parent=self.window())

    def _onExtract(self):
        if not self._result or not self._result.ok:
            return
        self._textEdit.setVisible(True)
        self._copyTextBtn.setVisible(True)
        self._textEdit.setPlainText("提取中…（抽取音频并转写）")
        source = self._result.video_url

        def done(text: str):
            self._textEdit.setPlainText(text)
            InfoBar.success("提取完成", "文案已生成", parent=self.window())

        def failed(error: str):
            self._textEdit.setPlainText(f"提取失败：{error}")
            InfoBar.error("提取失败", str(error), duration=-1, parent=self.window())

        self._pack.submit(parser_asr.transcribe(source), done=done, failed=failed, owner=self)

    def _onClear(self):
        self._input.clear()
        self._result = None
        self._card.setVisible(False)
        self._textEdit.setVisible(False)
        self._copyTextBtn.setVisible(False)
        self._textEdit.clear()

    def _onCopyText(self):
        self._copy(self._textEdit.toPlainText())

    @staticmethod
    def _copy(text: str):
        if text:
            QApplication.clipboard().setText(text, QClipboard.Mode.Clipboard)
