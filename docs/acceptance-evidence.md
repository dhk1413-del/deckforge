# M7 实际验收输出

日期：2026-10-09。以下四条命令实际退出码均为 0。verify-fast 使用外部临时 DECKFORGE_DATA；M5/M6/M7 另由各自测试创建临时目录。没有线上/浏览器实测。

门禁中的 ResourceWarning 为实际输出，未隐藏；构建计时出现负数为工具原始输出，照录，不作性能结论。门禁保持 15 项检查 + M5 4 个 + M6 3 个；T7 另跑 2 个，不冒充已有门禁项。

## make lint

退出码：`0`。完整输出（含真实尾部）：

```text
.venv/bin/python -m compileall -q server tools && npm --prefix web run typecheck

> deckforge-web@0.1.0 typecheck
> tsc --noEmit -p tsconfig.json
```

## DECKFORGE_DATA=$(mktemp -d) make verify-fast

退出码：`0`。完整输出（含真实尾部）：

```text
  ✅ test_beautify_v2       通过 15 项，失败 0 项
  ✅ test_page_import       通过 21 项，失败 0 项
  ✅ test_source_pages      通过 12 项，失败 0 项
  ✅ test_db_update         通过 8 项，失败 0 项
  ✅ test_editppt_engine    通过 47 项，失败 0 项
  ✅ test_editppt_validation_race 通过 6 项，失败 0 项
  ✅ test_vision_layout     通过 15 项，失败 0 项
  ✅ test_native_status     通过 12 项，失败 0 项
  ✅ test_native_render     通过 23 项，失败 0 项
  ✅ test_vision_parse      通过 22 项，失败 0 项
  ✅ test_dashscope_image   通过 12 项，失败 0 项
  ✅ test_image_retry       通过 22 项，失败 0 项
  ✅ test_slide_notes       通过 29 项，失败 0 项
  ✅ test_style_builder     68 项检查：68 通过 / 0 失败
  ✅ web build              ✓ built in 944ms

15 项检查：15 通过 / 0 失败
.../path/to/deckforge/server/app/stylepacks.py:45: ResourceWarning: unclosed file <_io.TextIOWrapper name='/path/to/deckforge/style-packs/layouts/cards_4.md' mode='r' encoding='utf-8'>
  return io.open(path, encoding="utf-8").read() if os.path.exists(path) else ""
ResourceWarning: Enable tracemalloc to get the object allocation traceback
/path/to/deckforge/server/app/stylepacks.py:45: ResourceWarning: unclosed file <_io.TextIOWrapper name='/path/to/deckforge/style-packs/styles/tech-deepblue/style.md' mode='r' encoding='utf-8'>
  return io.open(path, encoding="utf-8").read() if os.path.exists(path) else ""
ResourceWarning: Enable tracemalloc to get the object allocation traceback
/path/to/deckforge/server/app/stylepacks.py:45: ResourceWarning: unclosed file <_io.TextIOWrapper name='/path/to/deckforge/style-packs/styles/tech-deepblue/prompt.md' mode='r' encoding='utf-8'>
  return io.open(path, encoding="utf-8").read() if os.path.exists(path) else ""
ResourceWarning: Enable tracemalloc to get the object allocation traceback
.
----------------------------------------------------------------------
Ran 4 tests in 0.193s

OK
/path/to/deckforge/server/app/stylepacks.py:45: ResourceWarning: unclosed file <_io.TextIOWrapper name='/path/to/deckforge/style-packs/styles/tech-deepblue/style.md' mode='r' encoding='utf-8'>
  return io.open(path, encoding="utf-8").read() if os.path.exists(path) else ""
ResourceWarning: Enable tracemalloc to get the object allocation traceback
/path/to/deckforge/server/app/stylepacks.py:45: ResourceWarning: unclosed file <_io.TextIOWrapper name='/path/to/deckforge/style-packs/styles/tech-deepblue/prompt.md' mode='r' encoding='utf-8'>
  return io.open(path, encoding="utf-8").read() if os.path.exists(path) else ""
ResourceWarning: Enable tracemalloc to get the object allocation traceback
...
----------------------------------------------------------------------
Ran 3 tests in 0.159s

OK
```

## npm --prefix web run build

退出码：`0`。完整输出（含真实尾部）：

```text

> deckforge-web@0.1.0 build
> tsc --noEmit -p tsconfig.json && vite build

vite v7.3.6 building client environment for production...
transforming...
✓ 66 modules transformed.
rendering chunks...
computing gzip size...
dist/index.html                   0.42 kB │ gzip:   0.31 kB
dist/assets/index-BeE_VjRi.css   35.39 kB │ gzip:   7.66 kB
dist/assets/index-DVNnwfqE.js   435.38 kB │ gzip: 131.67 kB
✓ built in -599ms
```

## .venv/bin/python -m server.tests.test_m7

退出码：`0`。完整输出（含真实尾部）：

```text
..
----------------------------------------------------------------------
Ran 2 tests in 0.013s

OK
```
