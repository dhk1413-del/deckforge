# SlideCraft v0.1.0

自托管的「输入内容 → 一整套风格统一 PPT」工作台，**首个公开版本**。

## 这个版本能做什么

- **文档生成**：上传 Markdown / TXT / DOCX / PDF / PPTX，或直接粘贴文本 → 梳理页面 → 按选定风格逐页出图 → 导出整套 PPT。
- **PPT 美化**：拿参考图重做每一页，可按需转成可编辑版。
- **图片转可编辑**：把整页图转成以文字/形状为原生对象的 PPTX。
- **讲稿备注**：为每一页生成备注。
- **两条导出路线**：图片版 PPTX（整页图铺底）与**原生可编辑** PPTX（文本/形状/图表都是 PowerPoint 原生对象）。
- **零密钥也能跑**：不填任何模型 key，全流程走本地兜底渲染，成本 **0**，流程与导出都走得通。
- **零依赖单文件版**：`slidecraft-standalone.html` 双击即可离线使用，数据存在浏览器里。

## 安装（源码）

需要 Python 3.12 与 Node.js 22（≥22.12）；处理 PPTX 另需 LibreOffice。

```bash
git clone https://github.com/dhk1413-del/slidecraft.git
cd slidecraft
npm --prefix web install
npm --prefix web run build
bash server/start-lan.sh
```

打开 <http://127.0.0.1:8641>。服务默认只监听本机、无登录鉴权，只在可信网络里用。
Windows 与 macOS 均支持；也可以把 [README 的安装要求](https://github.com/dhk1413-del/slidecraft#安装)交给 AI 助手代装。

## 升级

首个版本，无需迁移。若你此前用的是 **DeckForge** 源码：`DECKFORGE_*` 环境变量、`data/` 目录与数据库文件名
**保持不变**，直接替换代码、重启后端即可，已有项目与草稿都还在。

## 名称说明

项目现名 **SlideCraft**。为了让已有数据和部署配置不作废，内部标识（环境变量名、数据库/运行文件名、
浏览器存储键）沿用原名，属于**刻意保留**，不是遗漏。

## 密钥安全

模型 API key 只存在于你本机的 `.env` 或界面设置页（存本地数据库），**本仓库与本次发布不含任何密钥**。
仓库自带 `pre-commit` / `pre-push` 门禁与 `tools/check_no_secrets.py`，默认拦住 key 的提交与推送。

## 已知问题

- 内部回归 `server/tests/test_m5.py::test_interruption_is_terminal_and_reentrant` 有一处断言失败
  （`resume_step` 期望 5、实际 6），**在打本标签之前就存在**，不影响零密钥主流程，尚未修复。
  其余 16 项离线检查与前端构建通过。

## 许可证

**AGPL-3.0**（见 `LICENSE`）。注意依赖 PyMuPDF 本身即 AGPL-3.0 / 商业双授权，因此本项目的许可证选择与
依赖义务是一致的。第三方依赖的许可清单见
[README「许可证」](https://github.com/dhk1413-del/slidecraft#许可证)。

---

安装与常见问题见 [README](https://github.com/dhk1413-del/slidecraft) 与
[使用说明](https://github.com/dhk1413-del/slidecraft/blob/main/docs/使用说明.md)。
