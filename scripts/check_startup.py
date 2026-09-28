"""构建前启动冒烟检查：真实跑一遍启动流程直到主窗口显示。

为什么需要这个脚本
------------------
`scripts/check_imports.py` 只能证明「模块能导入」，证明不了「主窗口能建起来」。
0.0.6 就吃过这个亏：`MainWindow.__init__` 中间被误插入一个 `@property`，
导致其后所有赋值变成 `return` 之后的死代码 —— 窗口从未真正初始化，
启动时 `window.show()` 直接触发 Windows access violation（无 Python 异常、无日志），
用户表现为「双击没反应 / 打不开」。

本脚本用离屏 Qt 平台复刻 DramaFetch.startApp 的关键路径：
  setupEnvironment → SingletonApplication → loadEngine → createServices
  → loadPacks → MainWindow(...) → setupPacks() → show() → processEvents()

任何一步抛异常都会以非 0 退出，从而在构建前拦下「装完打不开」的包。

用法：
  uv run python scripts/check_startup.py
"""

from __future__ import annotations

import faulthandler
import importlib
import os
import sys
import traceback
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

# 防护超时：本脚本会真实构造窗口/卡片/对话框，一旦出现无限循环
# （例如父子关系成环导致 Qt 布局递归）就会永久挂住 —— CI 会一路拖到超时，
# 什么信息都给不出。超时后 faulthandler 打印各线程堆栈并以非 0 退出。
WATCHDOG_SECONDS = 180

# 每个特性包一个代表性任务，用来真实构造任务卡片。
# 卡片是在任务列表渲染时才创建的（_refreshViewport → _createCard），CI 上没有
# 已保存任务就永远不会走到，因此必须在这里喂一个合成任务。
# 格式：packId -> (task 所在模块, 类名, 任务 URL)
_CARD_TASKS: dict[str, tuple[str, str, str]] = {
    "http": ("http_pack.task", "HttpTask", "https://example.com/smoke.bin"),
    "m3u8": ("m3u8_pack.task", "M3U8Task", "https://example.com/smoke.m3u8"),
    "drama": (
        "drama_pack.task", "DramaTask",
        "drama://hongguo/7683196130645003288?name=%E5%86%92%E7%83%9F%E6%B5%8B%E8%AF%95&eps=1-3",
    ),
}

# 必须在导入 PySide6 之前设置：离屏渲染，不弹窗、不需要显示器
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

# Windows（含 CI runner）的 stdout 默认是 cp1252，直接 print 中文会
# UnicodeEncodeError 而把检查本身搞挂，这里强制 UTF-8。
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

for path in (str(REPO), str(REPO / "features")):
    if path not in sys.path:
        sys.path.insert(0, path)


def main() -> int:
    faulthandler.enable()
    faulthandler.dump_traceback_later(WATCHDOG_SECONDS, exit=True)
    try:
        import DramaFetch
        from PySide6.QtWidgets import QApplication

        DramaFetch.setupEnvironment()
        # 刻意不用 SingletonApplication：单实例锁在有别的实例在跑时（本地开发很常见）
        # 会让检查直接退出，导致结果依赖环境、随机失败。这里只关心启动与渲染路径。
        app = QApplication(sys.argv[:1])

        from app.startup import createServices, loadEngine, loadPacks
        from app.services.plan import Plan
        from app.view.windows.main_window import MainWindow

        coroutineRunner, categoryService, speedMeter = loadEngine(app)
        MainWindow.refreshThemeColor()
        featureService, taskService, updateService, _ = createServices(
            coroutineRunner, categoryService, speedMeter,
        )
        loadPacks(featureService, coroutineRunner, speedMeter)

        plan = Plan(allCompleted=lambda: taskService.runningCount() == 0)
        window = MainWindow(
            taskService, featureService, categoryService,
            speedMeter, coroutineRunner, plan, updateService,
        )
        # setupPacks/show 会真正走一遍页面注册与首屏渲染
        window.setupPacks()
        window.show()
        QApplication.processEvents()

        # 特性页是懒加载的（_showPage 里才构造），必须逐个真实创建，
        # 否则页面自身的构造问题（控件搭错、属性名写错）检查不到。
        created = ["TaskPage"]
        for PageClass in featureService.pages():
            window._showPage(PageClass)
            QApplication.processEvents()
            created.append(PageClass.__name__)

        # 任务卡片同样是按需构造的，这里逐个包真实建一张卡并 refresh 一遍。
        cards = []
        for pack in featureService.packs:
            spec = _CARD_TASKS.get(pack.packId)
            if spec is None:
                continue
            moduleName, className, url = spec
            taskCls = getattr(importlib.import_module(moduleName), className)
            task = taskCls(name="冒烟测试", url=url, packId=pack.packId)
            card = featureService.taskCard(task)
            if card is None:
                raise RuntimeError(f"{pack.packId} 未返回任务卡片实例")
            card.refresh(force=True)
            # 走一次真实布局：名字被布局压成 0 宽是「看得见但没内容」的隐形 bug，
            # 只看构造成功查不出来，所以这里断言标题确实占到了宽度。
            card.resize(960, card.height())
            card.show()
            QApplication.processEvents()
            if card.nameLabel.width() <= 0:
                raise RuntimeError(
                    f"{type(card).__name__} 的标题宽度为 0（布局把名字挤没了）"
                )
            cards.append(type(card).__name__)

        # 「下载中」页必须只展示短剧任务（主窗口注册时 setPackFilter("drama")）
        taskPage = window._pages.get("TaskPage")
        if taskPage is None:
            raise RuntimeError("TaskPage 未在侧边栏创建")
        if getattr(taskPage, "_packFilter", "") != "drama":
            raise RuntimeError(
                "「下载中」页未按 drama 包过滤，"
                f"实得 {getattr(taskPage, '_packFilter', None)!r}"
            )

        # 剧卡片：短剧页 / 排行榜页的渲染单元，同样是按需构造的。
        from drama_pack import api as dramaApi
        from drama_pack.page import DramaCard

        for rank in (0, 1):
            drama = dramaApi.Drama(
                seriesId="7683196130645003288", title="冒烟测试剧", cover="",
                intro="简介", episodeCount="3", category="榜单",
                vidList=("a", "b", "c"), rank=rank,
            )
            card = DramaCard(drama, None, rank=rank, record=None)
            # 长条卡片按容器宽度横向铺开，给足宽度才有真实的右侧信息区
            card.resize(1000, card.height())
            card.show()
            QApplication.processEvents()
            if card._title.width() <= 0:
                raise RuntimeError(f"DramaCard(rank={rank}) 的标题宽度为 0")
            if card._cover.width() <= 0 or card._cover.height() <= 0:
                raise RuntimeError(f"DramaCard(rank={rank}) 的海报位尺寸为 0")
            # 长条样式：海报必须高于宽（3:4 竖版），信息区必须真的拿到宽度
            if card._cover.height() <= card._cover.width():
                raise RuntimeError(
                    f"DramaCard(rank={rank}) 海报不是竖版："
                    f"{card._cover.width()}x{card._cover.height()}"
                )
            if card._infoWidth() <= 0:
                raise RuntimeError(f"DramaCard(rank={rank}) 信息列宽度为 0")
            cards.append(f"DramaCard(rank={rank})")

        # 已下载页卡片：按剧归纳，海报位是 3:4 竖版（不裁剪）。
        # 这张卡的构造同样只在页面刷新时才走到，必须显式跑一遍。
        from drama_pack.downloaded_page import DownloadedCard

        record = {
            "seriesId": "7683196130645003288", "title": "冒烟测试剧",
            "status": 4, "total": 3, "downloaded": 3,
            "folder": "", "posterFile": "",
        }
        for status, downloaded in ((4, 3), (2, 1), (3, 0)):
            variant = dict(record, status=status, downloaded=downloaded)
            card = DownloadedCard(variant, None)
            card.resize(card.width(), card.height())
            card.show()
            QApplication.processEvents()
            if card._title.width() <= 0:
                raise RuntimeError(
                    f"DownloadedCard(status={status}) 的标题宽度为 0"
                )
            cards.append(f"DownloadedCard(status={status})")

        # 已下载页：聚合视图，必须真实构造并刷新一次，
        # 否则「页面导入得了但一打开就崩」这类问题构建期查不出来。
        if "DownloadedPage" not in created:
            raise RuntimeError("未注册 DownloadedPage")
        page = window._pages.get("DownloadedPage")
        if page is None:
            raise RuntimeError("DownloadedPage 未在侧边栏创建")
        page._refresh()
        QApplication.processEvents()

        # 选集对话框：短剧页 / 排行榜页「下载」按钮的落点，同样是按需构造的
        # （此前整条链路从没被跑过，藏了两个必崩的问题：ScrollArea 父子成环
        # 导致布局无限递归卡死，以及把 QHBoxLayout 传给了 addWidget）。
        from drama_pack.picker import EpisodePickerDialog

        window.resize(1280, 800)
        pickerPack = featureService.packById("drama")
        if pickerPack is None:
            raise RuntimeError("未找到 drama 特性包")
        dialogs = []
        for total in (20, 300):
            drama = dramaApi.Drama(
                seriesId="7683196130645003288", title="冒烟测试剧", cover="",
                episodeCount=str(total), category="榜单",
                vidList=tuple(str(i) for i in range(total)),
            )
            dialog = EpisodePickerDialog(pickerPack, drama, window)
            QApplication.processEvents()
            if len(dialog._episodeButtons) != total:
                raise RuntimeError(
                    f"选集对话框按钮数不符：期望 {total} 实得 {len(dialog._episodeButtons)}"
                )
            dialogs.append(f"EpisodePickerDialog({total}集)")
            dialog.deleteLater()

        print(f"OK  主窗口创建并显示成功，已实例化页面: {created}")
        print(f"OK  卡片构造成功: {cards}")
        print(f"OK  对话框构造成功: {dialogs}")
        print("✓ 启动冒烟检查通过")
        return 0
    except Exception as err:
        traceback.print_exc()
        print(f"\n✗ 启动冒烟检查失败: {type(err).__name__}: {err}")
        return 1
    finally:
        faulthandler.cancel_dump_traceback_later()


if __name__ == "__main__":
    raise SystemExit(main())
