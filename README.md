# DS Agent — 跨境电商 AI 运营指挥中心

面向亚马逊卖家的 AI Agent 自动化系统。8 个 AI Agent 覆盖库存预警、广告日报、利润分析、跟卖监控、竞品发现、Listing 优化、运营日报全场景。

## 架构

```
前端指挥大屏 (GSAP + pywebview桌面)
        │
Agent API (FastAPI + JWT + 16端点)
        │
┌───────┼──────────┐
│       │          │
LLM    引擎       数据源
(6模型) (规则+AI)  (3适配器)
```

## 核心能力

- **8 个 AI Agent**: 库存/广告/利润/跟卖/竞品发现/竞品分析/Listing优化/运营日报
- **多数据源可切换**: 领星 ERP REST API + 卖家精灵 MCP (42工具) + Sorftime MCP (34工具)
- **6 个 LLM Provider**: Claude / OpenAI / DeepSeek / 千问 / GLM / 自定义
- **全量 AI 分析管线**: 规则引擎(毫秒级) → LLM深度分析 → 告警/建议/静默
- **JWT 权限控制**: admin/operator/viewer 三角色 + 多级审批流
- **Prompt 管理**: 16 套模板 YAML 存储 + 前端可视化编辑器
- **RAG 知识库**: 文档上传 → 分段 → 检索 → 拼入 LLM 上下文
- **动态 Mock 数据**: 库存/销量/ACOS/BSR 每次自动波动
- **Tool Calling**: LLM 自主选择工具 → 执行 → 迭代

## 快速启动

```bash
# 安装依赖
pip install -r requirements.txt

# 启动 (Mock 模式, 无需 API Key)
cd src && python main.py

# Docker 一键部署
docker-compose up -d

# 桌面应用
python desktop.py
```

浏览器打开 `http://localhost:8000/dashboard`

默认管理员: `admin` / `admin123`

## 技术栈

| 层级 | 技术 |
|------|------|
| 后端 | Python 3.8+, FastAPI, Pydantic, APScheduler |
| AI/LLM | Anthropic SDK, OpenAI SDK, MCP 协议, Tool Calling |
| 存储 | SQLite, JSON/YAML 文件存储, 快照对比 |
| 前端 | Vanilla JS, GSAP 动画, SSE 流式推送 |
| 部署 | Docker Compose, pywebview 桌面打包 |

## 配置

所有配置项均可从前端修改，即时生效：

- LLM (Provider/Model/API Key)
- 数据源 (URL/Secret Key/开关)
- 告警阈值 (13 项可调)
- 通知渠道 (钉钉/企微 Webhook)
- 监控对象 (ASIN/SKU/关键词列表)
- 调度策略 (轮询间隔/工作时间)
- Prompt 模板 (16 套可编辑)

## 项目结构

```
DSAgent/
├── src/
│   ├── main.py          # FastAPI 入口
│   ├── agents/          # 8 个业务 Agent
│   ├── engine/          # 对比/分析/决策/调度引擎
│   ├── datasource/      # 数据源适配器 + 标准化模型
│   ├── llm/             # LLM Provider 工厂
│   ├── config/          # 配置系统 (YAML + .env)
│   ├── auth/            # JWT 认证 + 权限
│   ├── storage/         # 原始/快照/决策日志存储
│   ├── tools/           # Tool Calling 编排
│   ├── prompts/         # Prompt 管理
│   ├── rag/             # RAG 知识库
│   ├── webhooks/        # Webhook 接收器
│   └── static/          # 前端指挥大屏
├── workflows/           # 5 个 JSON 工作流定义
├── config.yaml          # 用户配置文件
├── docker-compose.yml   # Docker 部署
├── desktop.py           # 桌面应用
└── docs/                # 设计文档
```
