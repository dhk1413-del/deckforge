# config/ —— provider 对接配置（预置完成，key 由用户填写）

三件事已经**预置好**，你只需要做第四件。

## 1. 你要做的：填 key（两条路任选）

**路线 A（推荐，界面里填）**：启动后进「设置 → 模型与密钥」，三家生图 + DeepSeek 各一个输入框，填完点「连通性测试」。
**路线 B（命令行）**：`cp config/.env.example .env`，填 `DASHSCOPE_API_KEY` / `DEEPSEEK_API_KEY`。

## 2. 已预置的内容

- 三家的 `base_url`、模型 ID、分辨率档位映射、默认模型/档位、轮换优先级（`providers.yaml`）
- 已实测的价格（阿里 qwen-image 系）
- 文案梳理 5 个环节统一指向 DeepSeek（`text-models.yaml`）
- 每次生成记录 `provider / model / size / 单价 / 耗时`（D19 模型可见）

## 3. 填完 key 先自测（不依赖本应用，现在就能验）

```bash
# 阿里百炼
curl -s -o /dev/null -w "%{http_code}\n" --noproxy '*' \
  -H "Authorization: Bearer $DASHSCOPE_API_KEY" https://dashscope.aliyuncs.com/api/v1/models

# DeepSeek（顺便确认账号当前可用模型名，勿硬编码）
curl -s --noproxy '*' -H "Authorization: Bearer $DEEPSEEK_API_KEY" \
  https://api.deepseek.com/models
```

## 4. 三个环境事实（踩过的坑，别重复踩）

- 本机 **Clash 代理**：调国内 API 必须**绕过代理**（`proxies={}` 或 `--noproxy '*'`），否则请求被绕飞。
- **OpenAI / Google Gemini / xAI 直连不通**（实测 000 超时）→ 生图只能走上面三家。
- `npx`/`npm` 若报 `EACCES`：`~/.npm` 有历史 root 属主文件，**加 `--cache /tmp/npm-cache-slidecraft`**，不要 sudo。

## 5. 实现阶段的待办（写在 spec §20）

- 阿里异步任务的**确切请求/响应结构**：按官方文档核对后落实现
