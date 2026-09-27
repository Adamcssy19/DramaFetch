"""构建前冒烟检查：所有特性包必须能被真实导入、页面能真实注册。

为什么需要这个脚本
------------------
特性包的页面是「延迟导入」的：`pack.pages()` 里才 `from .parse_page import ParsePage`。
这带来两个后果：
  1. `python -m py_compile` 只检查语法、不执行导入，查不出错误的 import 名；
  2. Nuitka 编译期也不会执行这些导入。

于是形如 `from PySide6.QtCore import N`（`N` 只是本项目 `QT_TRANSLATE_NOOP` 的
别名，并非 PySide6 的导出名）这样的错误，可以一路通过编译、打进安装包，
直到用户启动应用时才 ImportError 崩溃 —— 装机即打不开。

本脚本把这一步提前到构建之前，复刻 `FeatureService.register()` 的调用路径：
  导入每个包的全部模块 → 实例化 Pack 类 → 调 pages() / 读 parsers。

用法：
  uv run python scripts/check_imports.py
退出码非 0 表示存在导入/注册错误，构建应当中止。
"""

from __future__ import annotations

import importlib
import sys
import traceback
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
FEATURES_DIR = REPO / "features"


def _packDirs() -> list[Path]:
    if not FEATURES_DIR.is_dir():
        return []
    return sorted(
        d for d in FEATURES_DIR.iterdir()
        if d.is_dir() and not d.name.startswith(".") and (d / "manifest.toml").is_file()
    )


def _modulesOf(packDir: Path) -> list[str]:
    return [
        f"{packDir.name}.{py.stem}"
        for py in sorted(packDir.glob("*.py"))
        if py.name != "__init__.py"
    ]


def _packClass(packDir: Path):
    """按 manifest 的 entry/class 取出 Pack 类。"""
    from app.models.pack import PackManifest

    manifest = PackManifest.fromDir(packDir)
    if manifest is None:
        raise RuntimeError("manifest 无法解析")
    entry = manifest.entryPath or Path("pack.py")
    module = importlib.import_module(f"{packDir.name}.{Path(entry).stem}")
    return getattr(module, manifest.className)


def main() -> int:
    for path in (str(REPO), str(FEATURES_DIR)):
        if path not in sys.path:
            sys.path.insert(0, path)

    failures: list[tuple[str, str]] = []

    for packDir in _packDirs():
        for module in _modulesOf(packDir):
            try:
                importlib.import_module(module)
            except Exception as err:
                failures.append((module, f"{type(err).__name__}: {err}"))
                traceback.print_exc()

        try:
            from app.models.pack import PackServices

            packClass = _packClass(packDir)
            # pages() / parsers 不依赖真实服务，用占位即可
            pack = packClass(PackServices(coroutineRunner=None, speedMeter=None))
            pages = pack.pages()
            parsers = list(pack.parsers or [])
        except Exception as err:
            failures.append((f"{packDir.name} 注册", f"{type(err).__name__}: {err}"))
            traceback.print_exc()
            continue

        print(f"OK  {packDir.name:16s} pages={[p.__name__ for p in pages]} "
              f"parsers={[p.__name__ for p in parsers]}")

    print()
    if failures:
        print(f"✗ 冒烟检查失败 {len(failures)} 项：")
        for name, msg in failures:
            print(f"  - {name}: {msg}")
        return 1

    print("✓ 冒烟检查通过")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
