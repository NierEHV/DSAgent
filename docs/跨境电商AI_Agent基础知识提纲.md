# 跨境电商 AI Agent 工程师 — 基础知识提纲

> 面向 JD 能力模型，系统化覆盖所有知识点

---

## 第一部分：跨境电商业务基础 ★★★★★

### 1.1 亚马逊卖家核心概念

| 概念 | 说明 | 数据来源 |
|------|------|----------|
| **ASIN** | Amazon Standard Identification Number，亚马逊商品唯一标识 | 亚马逊 API |
| **MSKU** | Merchant SKU，卖家内部商品编码 | ERP / 自定义 |
| **FBA** | Fulfillment by Amazon，亚马逊物流配送 | 亚马逊后台 |
| **FBM** | Fulfillment by Merchant，卖家自发货 | 仓库系统 |
| **Listing** | 商品详情页（标题、五点、描述、A+、图片、Review） | 亚马逊 API / ERP |
| **Buy Box** | 购物车，影响销量的关键因素 | 亚马逊 API |
| **BSR** | Best Sellers Rank，类目销量排名 | 亚马逊 API |
| **跟卖** | 其他卖家在同一个 Listing 上销售 | 监控工具 |

### 1.2 广告体系

| 概念 | 说明 | 关键指标 |
|------|------|----------|
| **SP** (Sponsored Products) | 商品推广广告 | Impressions, Clicks, CTR, CPC |
| **SB** (Sponsored Brands) | 品牌推广广告 | New-to-Brand Orders, Brand Halo |
| **SD** (Sponsored Display) | 展示型推广 | Detail Page Views, Add to Cart |
| **ACOS** | Advertising Cost of Sales = 广告花费/广告销售额 | 目标 < 20%-30% |
| **TACOS** | Total ACOS = 广告花费/总销售额 | 衡量广告对自然流量的拉动 |
| **ROAS** | Return on Ad Spend = 广告销售额/广告花费 | 目标 > 3-5 |

### 1.3 库存管理

| 概念 | 说明 | 预警阈值 |
|------|------|----------|
| **库存周转率** | 销量/平均库存，衡量库存效率 | < 2 次/月 ⚠️ |
| **IPI** (Inventory Performance Index) | 亚马逊库存绩效指标 | < 400 限制仓储 |
| **安全库存** | 防止断货的最低库存量 | 日销量 × 采购周期 × 1.5 |
| **冗余库存** | 超过 90 天销量的库存 | 需清理，产生仓储费 |
| **仓储费** | FBA 月度/长期仓储费 | 365 天以上翻倍 |
| **缺货** | 库存归零 → 丧失 Buy Box + 排名 | 必须预警 |

### 1.4 利润核算

```
毛利 = 销售收入 - 商品成本 - FBA费用 - 广告费 - 佣金
净利润 = 毛利 - 退款 - 仓储费 - 其他费用 - 人员分摊
毛利率 = 毛利 / 销售收入
净利率 = 净利润 / 销售收入

关键数据源：
├── 亚马逊 Settlement Report（结算报告）
├── 领星 ERP 利润报表
├── 广告后台花费报表
├── 采购成本表（ERP/手动）
└── 头程费用分摊
```

### 1.5 竞品监控

| 监控维度 | 数据来源 | 告警条件 |
|------|------|------|
| 价格变动 | Keepa / 自有爬虫 / 亚马逊 API | 降价 > 10% |
| BSR 排名 | 亚马逊 API / 第三方工具 | 突升突降 > 50% |
| 关键词排名 | 第三方工具 (SellerSprite 等) | 跌出前 3 页 |
| 评论数和评分 | 亚马逊 API | 新增差评 |
| 跟卖者数量 | 监控工具 | 新增跟卖 |

---

## 第二部分：AI Agent 开发核心 ★★★★★

### 2.1 LLM 基础

```python
# 核心能力矩阵
┌──────────────┬──────────────────────────────────┐
│ 能力          │ 在电商场景的应用                    │
├──────────────┼──────────────────────────────────┤
│ 文本理解       │ 理解运营提问："ACOS 为什么突然升高"  │
│ 信息抽取       │ 从广告报表中抽取关键指标             │
│ 推理分析       │ 分析利润异常原因（退款率↑ + 广告↑） │
│ 代码生成       │ 生成 SQL 查询 / Python 数据处理脚本  │
│ 结构化输出     │ 输出 JSON 格式的预警报告             │
│ 多轮对话       │ 运营连续追问，层层深入               │
└──────────────┴──────────────────────────────────┘
```

### 2.2 Function Calling / Tool Calling

```python
# 核心概念：让 LLM 像调用函数一样操作外部系统
tools = [
    {
        "name": "query_inventory",
        "description": "查询指定 MSKU 的库存信息",
        "parameters": {
            "msku": "string",
            "warehouse": "string (FBA/FBM/ALL)"
        }
    },
    {
        "name": "query_ad_report",
        "description": "查询广告数据报告",
        "parameters": {
            "start_date": "date",
            "end_date": "date",
            "campaign_type": "SP|SB|SD",
            "metrics": ["impressions", "clicks", "spend", "sales", "acos"]
        }
    },
    {
        "name": "query_profit",
        "description": "查询 SKU/账号 利润数据",
        "parameters": {
            "sku": "string",
            "date_range": "string (7d/30d/90d)",
            "breakdown": "boolean (是否按费用明细拆分)"
        }
    },
    {
        "name": "send_alert",
        "description": "发送预警通知",
        "parameters": {
            "level": "INFO|WARNING|CRITICAL",
            "title": "string",
            "content": "string",
            "channel": "dingtalk|wecom|email"
        }
    }
]

# LLM 自动解析用户意图并选择工具
user: "昨天我的主力 ASIN B0XXX 的广告 ACOS 超过 50% 了，帮我看看怎么回事"
LLM → tool_calls: [
    query_ad_report(asin="B0XXX", days=7, metrics=["acos","spend","sales","clicks","cpc"]),
    query_profit(sku="B0XXX", date_range="7d")
]
```

### 2.3 MCP (Model Context Protocol)

> 参考 n8n-workflows-main 的 IntegrationHub 模式

```python
# MCP 架构：标准化 AI-工具接口协议
┌─────────────┐     MCP Protocol     ┌─────────────────┐
│  AI Agent   │ ◄──────────────────► │  MCP Server      │
│  (Claude/   │   ListTools          │  ├── 领星 ERP     │
│   GPT/Gemini│   CallTool           │  ├── 亚马逊 SP-API│
│   ...)       │   GetResources       │  ├── 广告 API     │
└─────────────┘                      │  ├── 数据库       │
                                      │  └── 通知服务     │
                                      └─────────────────┘

# MCP Server 示例 - 封装领星 ERP API
# mcp_server_lingxing.py
@server.list_tools()
async def list_tools():
    return [
        Tool(name="get_inventory", description="查询领星ERP库存"),
        Tool(name="get_orders", description="查询领星ERP订单"),
        Tool(name="get_finance", description="查询领星ERP财务数据"),
    ]
```

### 2.4 RAG (Retrieval-Augmented Generation)

```
RAG 电商应用场景：
┌──────────────────────────────────────────────┐
│ 知识库类型      │ 内容                      │ 用途         │
├──────────────────────────────────────────────┤
│ 运营 SOP       │ 广告调整步骤、促销流程    │ Agent 执行参考 │
│ 亚马逊政策     │ FBA 规则、广告政策        │ 合规检查      │
│ 历史告警记录   │ 过去的异常和解决方案      │ 问题诊断      │
│ 产品知识库     │ Listing 优化规范、关键词库│ 内容生成      │
│ API 文档       │ 领星/亚马逊接口文档       │ 工具调用参考  │
└──────────────────────────────────────────────┘

# RAG 工作流
用户提问 → Embedding → 向量检索(ChromaDB/Pinecone/Milvus)
         → 相关文档 → Prompt 组装 → LLM 生成 → 返回
```

### 2.5 Agent 工作流

```
单 Agent 模式：
Trigger(Schedule/Webhook/Manual) → Task → LLM → Tool → LLM → Result

多 Agent 编排（参考 n8n 工作流模式）：
┌──────────┐   ┌──────────┐   ┌──────────┐
│ 数据采集  │ → │ 分析诊断  │ → │ 行动执行  │
│ Agent    │   │ Agent    │   │ Agent    │
└──────────┘   └──────────┘   └──────────┘
     │              │              │
  Cron/定时     LLM+Tool      人审节点
  Webhook       +RAG          +权限检查
```

---

## 第三部分：ERP 与 API 对接 ★★★★

### 3.1 领星 ERP 对接

```
对接架构：
┌──────────────┐     REST API      ┌─────────────────┐
│  Agent 系统   │ ◄──────────────► │  领星 ERP        │
│              │  OAuth 2.0       │                  │
│              │                   │  数据模块：       │
│              │                   │  ├── 商品管理     │
│              │                   │  ├── 订单管理     │
│              │                   │  ├── 库存管理     │
│              │                   │  ├── 财务/利润    │
│              │                   │  ├── 广告管理     │
│              │                   │  ├── Listing     │
│              │                   │  └── 报表中心     │
└──────────────┘                   └─────────────────┘

# 关键 API 端点
GET    /api/products              # 商品列表（MSKU, ASIN, SKU）
GET    /api/inventory             # 库存查询（FBA + 本地）
GET    /api/orders                # 订单数据
GET    /api/finance/profit        # 利润数据
GET    /api/advertising/reports   # 广告报表
POST   /api/webhook/subscribe     # 订阅 Webhook（库存变更/订单更新）
```

### 3.2 亚马逊 SP-API (Selling Partner API)

```
认证流程：
1. 注册为亚马逊开发者 → 获取 Developer ID
2. OAuth 2.0 授权 → 卖家授权访问
3. 获取 LWA (Login with Amazon) Token
4. 使用 Token 调用 API

核心 Endpoint：
├── /catalog/items      # 商品信息（标题、描述、属性）
├── /fba/inventory      # FBA 库存
├── /orders             # 订单查询
├── /finances           # 财务/结算
├── /reports            # 报告（业务报告、库存报告）
├── /listings           # Listing 管理
└── /productPricing     # 价格信息
```

### 3.3 Webhook 设计（参考 n8n-workflows-main IntegrationHub）

```python
# Webhook 接收 → 事件分发 → Agent 触发
class WebhookManager:
    """Webhook管理器 - 参考 src/integration_hub.py"""

    def __init__(self):
        self.endpoints: Dict[str, Callable] = {}

    def register(self, event: str, handler: Callable):
        self.endpoints[event] = handler

    async def handle(self, event: str, payload: dict):
        """
        事件分发器
        参考 n8n 的 webhook trigger 模式
        """
        if event in self.endpoints:
            return await self.endpoints[event](payload)

# 使用示例
webhook.register("inventory.low_stock", inventory_alert_agent.run)
webhook.register("order.refund", profit_anomaly_agent.run)
webhook.register("listing.hijacked", hijack_monitor_agent.run)
```

---

## 第四部分：数据处理与存储 ★★★★

### 4.1 数据流架构

```
数据源层 → ETL / CDC → 数据仓库 → 分析层 → 应用层
───────────┬─────────────────────────────────────────────
亚马逊 API  │
领星 ERP    │  → Python/定时任务 → PostgreSQL → BI看板
广告 API    │     (Celery/APScheduler)  + Redis    → 日报
手动 Excel  │                           缓存       → Agent
竞品工具    │                                       → 预警
```

### 4.2 SQL 核心查询

```sql
-- 利润日报核心查询
SELECT
    date,
    SUM(sales_amount) AS revenue,
    SUM(cogs) AS cost,
    SUM(fba_fee) AS fba_fee,
    SUM(ad_spend) AS ad_spend,
    SUM(commission) AS commission,
    SUM(sales_amount - cogs - fba_fee - ad_spend - commission) AS gross_profit,
    ROUND(SUM(sales_amount - cogs - fba_fee - ad_spend - commission) / SUM(sales_amount) * 100, 2) AS margin_pct
FROM finance_daily
WHERE date BETWEEN '2026-05-01' AND '2026-05-31'
GROUP BY date
ORDER BY date DESC;

-- 库存预警查询
SELECT
    msku,
    asin,
    fba_stock,
    daily_sales_7d,
    fba_stock / NULLIF(daily_sales_7d, 0) AS days_of_stock,
    CASE
        WHEN fba_stock / NULLIF(daily_sales_7d, 0) < 7 THEN 'CRITICAL'
        WHEN fba_stock / NULLIF(daily_sales_7d, 0) < 14 THEN 'WARNING'
        ELSE 'OK'
    END AS alert_level
FROM inventory_snapshot
WHERE daily_sales_7d > 0
ORDER BY days_of_stock ASC;

-- 广告异常检测
WITH ad_metrics AS (
    SELECT
        asin, campaign_name,
        AVG(acos_7d) AS avg_acos,
        STDDEV(acos_7d) AS std_acos,
        LAST_VALUE(acos_7d) OVER (PARTITION BY asin ORDER BY date) AS latest_acos
    FROM ad_daily
    WHERE date >= CURRENT_DATE - INTERVAL '14 days'
    GROUP BY asin, campaign_name
)
SELECT *, latest_acos - avg_acos AS deviation
FROM ad_metrics
WHERE latest_acos > avg_acos + 2 * std_acos;  -- 2 sigma 异常
```

### 4.3 定时任务

```python
# 使用 APScheduler（参考 n8n 的 Cron trigger）
from apscheduler.schedulers.asyncio import AsyncIOScheduler

scheduler = AsyncIOScheduler()

# 广告日报 — 每天早上 8 点
scheduler.add_job(ad_daily_report, 'cron', hour=8, minute=0)

# 库存预警 — 每 4 小时
scheduler.add_job(inventory_alert, 'interval', hours=4)

# 利润核算 — 每天凌晨 2 点
scheduler.add_job(profit_calc, 'cron', hour=2, minute=0)

# 竞品监控 — 每 6 小时
scheduler.add_job(competitor_monitor, 'interval', hours=6)
```

---

## 第五部分：安全与权限 ★★★★

### 5.1 Agent 操作分级

```
参考 n8n-workflows-main 的 User Management 模式

Level 0 — 只读查询（无需审批）
├── 查询库存数量
├── 查看广告报表
├── 查询利润数据
└── 查看 Listing 信息

Level 1 — 分析建议（无需审批，仅生成报告）
├── 生成日报/周报
├── 库存预警分析
├── 竞品数据对比
└── 广告优化建议

Level 2 — 低风险操作（通知 + 日志）
├── 发送预警通知
├── 更新数据看板
├── 导出 Excel 报表
└── 修改配置参数

Level 3 — 高风险操作（必须人审）🔴
├── 调整广告出价/预算
├── 修改 Listing 内容
├── 发起促销活动
├── 创建 FBA 发货计划
└── 批量修改价格
```

### 5.2 人审机制

```
人审流程（参考 n8n 的 Manual trigger + Wait node）：

Agent 建议操作 → 生成审批单 → 推送到钉钉/企微
                              ↓
                    运营人员审核（通过/驳回/修改）
                              ↓
                    通过 → 自动执行 + 日志记录
                    驳回 → 记录原因 + AI 学习
                    修改 → 按修改后参数执行
```

### 5.3 审计日志设计

```sql
-- 参考 n8n-workflows-main analytics_engine + performance_monitor
CREATE TABLE agent_audit_log (
    id SERIAL PRIMARY KEY,
    agent_name VARCHAR(100),
    user_query TEXT,
    tool_calls JSONB,
    action VARCHAR(50),         -- READ/WRITE/ALERT/EXECUTE
    risk_level INT,             -- 0-3
    approval_status VARCHAR(20),-- PENDING/APPROVED/REJECTED
    approved_by VARCHAR(50),
    result JSONB,
    error TEXT,
    duration_ms INT,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_audit_agent_time ON agent_audit_log(agent_name, created_at);
CREATE INDEX idx_audit_approval ON agent_audit_log(approval_status);
```

---

## 第六部分：部署与运维 ★★★

### 6.1 部署架构（参考 ai-stack/docker-compose.yml）

```yaml
# 参考 n8n-workflows-main 的 Docker Compose 部署模式
services:
  agent-api:        # FastAPI — Agent 核心 API
  n8n:              # n8n — 工作流编排（可选）
  db-postgres:      # PostgreSQL — 业务数据
  redis:            # Redis — 缓存 + 任务队列
  chromadb:         # ChromaDB — 向量数据库 (RAG)
  celery-worker:    # Celery — 异步任务
  celery-beat:      # Celery Beat — 定时任务调度
  prometheus:       # 监控指标收集
  grafana:          # 可视化看板
```

### 6.2 监控告警（参考 performance_monitor.py）

```python
# 监控指标
METRICS = {
    "agent_response_time_ms": "Agent 响应时间",
    "tool_call_success_rate": "工具调用成功率",
    "api_latency_ms": "API 延迟",
    "alert_queue_size": "预警队列长度",
    "approval_pending_count": "待审批数",
    "error_rate_5m": "5分钟内错误率",
}

# 告警规则
ALERTS = {
    "agent_timeout": "agent_response_time_ms > 30000",
    "high_error_rate": "error_rate_5m > 0.05",
    "api_down": "tool_call_success_rate < 0.95",
    "queue_full": "alert_queue_size > 100",
}
```

---

## 第七部分：学习路线图

```
Phase 1（2周）: 电商业务基础
├── 亚马逊卖家后台操作熟悉
├── 10 个核心概念掌握（ASIN/FBA/ACOS/IPI 等）
└── 领星 ERP 各个模块操作一遍

Phase 2（2周）: LLM/Agent 基础
├── OpenAI/Claude API 调用 + Function Calling
├── MCP 协议理解和 Server 开发
├── RAG 基础（Embedding + 向量检索）
└── n8n/Dify 低代码 Agent 搭建

Phase 3（2周）: API 对接实战
├── 领星 ERP API 对接（至少 5 个模块）
├── 亚马逊 SP-API 认证和基础调用
├── Webhook 接收和处理
└── 数据库设计 + SQL 查询

Phase 4（2周）: 项目实战
├── 库存预警 Agent（端到端）
├── 广告日报 Agent（端到端）
├── 权限 + 人审 + 日志（端到端）
└── Docker 部署 + 监控
```

---

## 附：n8n-workflows-main 项目中可复用的设计模式

| n8n 模块 | 电商 Agent 对应 | 复用思路 |
|----------|----------------|---------|
| `ai_assistant.py` | Agent 对话入口 | 意图识别 + 关键词抽取 + 工作流匹配 |
| `integration_hub.py` | MCP Server 层 | 多服务注册 + Webhook 分发 + 通知发送 |
| `analytics_engine.py` | 数据分析引擎 | 趋势分析 + 异常检测 + 自动推荐 |
| `community_features.py` | 用户权限模块 | 用户管理 + 评分/反馈 + 收藏 |
| `performance_monitor.py` | 系统监控 | 指标采集 + 告警 + 历史数据 |
| `enhanced_api.py` | REST API 层 | 搜索 + 过滤 + 分页 + 缓存 |
| `workflow JSON 模式` | Agent 工作流定义 | Trigger → Node → Connection 流水线 |
| `ai-stack/docker-compose` | 部署架构 | n8n + Agent + 模型服务一体化 |
