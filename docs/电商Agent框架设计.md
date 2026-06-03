# 跨境电商 AI Agent 框架设计

> 参考 `n8n-workflows-main` 架构模式，设计面向亚马逊卖家的 AI Agent 自动化框架

---

## 一、总体架构

```
┌─────────────────────────────────────────────────────────────────────┐
│                         前端交互层                                    │
│   ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────────────┐  │
│   │ 钉钉机器人 │  │ 企微机器人 │  │ Web Chat │  │  运营 Dashboard  │  │
│   └────┬─────┘  └────┬─────┘  └────┬─────┘  └────────┬─────────┘  │
│        │              │             │                  │            │
├────────┼──────────────┼─────────────┼──────────────────┼────────────┤
│        ▼              ▼             ▼                  ▼            │
│  ┌────────────────────────────── API Gateway ────────────────────┐  │
│  │       FastAPI (参考 n8n enhanced_api.py + api_server.py)      │  │
│  │       /chat  /api/v2/*  /agent/*  /workflows/*  /admin/*     │  │
│  └───────────────────────────────────────────────────────────────┘  │
│                                  │                                   │
├──────────────────────────────────┼───────────────────────────────────┤
│                     Agent 编排层 (核心)                              │
│  ┌───────────────────────────────────────────────────────────────┐  │
│  │                  Agent Orchestrator                            │  │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────────────┐ │  │
│  │  │Intent    │→│Task      │→│Agent     │→│Review & Approve  │ │  │
│  │  │Detector  │ │Router    │ │Runner    │ │Gate              │ │  │
│  │  │(参考     │ │(参考     │ │(参考     │ │(参考             │ │  │
│  │  │ai_assist │ │n8n      │ │n8n      │ │user_management   │ │  │
│  │  │ant.py)   │ │workflow │ │workflow │ │.py 人审机制)      │ │  │
│  │  │          │ │JSON路由)│ │JSON执行)│ │                  │ │  │
│  │  └──────────┘ └──────────┘ └──────────┘ └──────────────────┘ │  │
│  └───────────────────────────────────────────────────────────────┘  │
│                                  │                                   │
├──────────────────────────────────┼───────────────────────────────────┤
│                     MCP 工具层 (参考 integration_hub.py)             │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐               │
│  │ 领星 ERP │ │亚马逊     │ │ 广告 API │ │ 通知服务  │               │
│  │ MCP Srv  │ │SP-API    │ │ MCP Srv  │ │ MCP Srv   │               │
│  └────┬─────┘ └────┬─────┘ └────┬─────┘ └────┬─────┘               │
│       │             │             │            │                     │
├───────┼─────────────┼─────────────┼────────────┼─────────────────────┤
│       ▼             ▼             ▼            ▼                     │
│                        数据层                                        │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐               │
│  │PostgreSQL│ │  Redis   │ │ChromaDB  │ │MinIO/S3  │               │
│  │(业务数据)│ │(缓存/队列)│ │(向量库)  │ │(文件存储)│               │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘               │
│                                                                      │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │    Analytics Engine (参考 analytics_engine.py)                │   │
│  │    趋势分析 │ 异常检测 │ 推荐引擎 │ 报表生成                    │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                                                                      │
├──────────────────────────────────────────────────────────────────────┤
│                    监控与运维层                                       │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────────────────┐   │
│  │Prometheus│ │ Grafana  │ │日志(ELK) │ │Audit Trail          │   │
│  │(参考     │ │(看板)    │ │          │ │(参考 community +    │   │
│  │perform.. │ │          │ │          │ │ user_management)    │   │
│  │monitor)  │ │          │ │          │ │                     │   │
│  └──────────┘ └──────────┘ └──────────┘ └──────────────────────┘   │
└──────────────────────────────────────────────────────────────────────┘
```

---

## 二、核心模块设计

### 2.1 Agent 工作流引擎（核心）

> **设计灵感：** n8n 的 workflow JSON 格式 + `src/ai_assistant.py` 的意图识别

```python
# agent_workflow.py — Agent 工作流定义与执行引擎
"""
每个 Agent 工作流 = Trigger → Steps(LLM + Tools) → Output

参考 n8n workflow JSON 格式：
{
  "nodes": [...],       # 流程节点 (trigger, llm, tool, condition, human_review)
  "connections": {...}, # 节点连线
  "settings": {...},    # 超时/重试/权限
  "meta": {...}         # 元数据
}
"""

from enum import Enum
from dataclasses import dataclass, field
from typing import Any, Callable, Optional
import json

class NodeType(Enum):
    TRIGGER = "trigger"           # Cron / Webhook / Manual
    LLM_CALL = "llm_call"         # 调用大模型
    TOOL_CALL = "tool_call"       # 调用 MCP 工具
    CONDITION = "condition"       # 条件判断
    HUMAN_REVIEW = "human_review" # 人审节点 🔴
    NOTIFY = "notify"             # 通知发送
    OUTPUT = "output"             # 结果输出

class RiskLevel(Enum):
    READ_ONLY = 0    # 只读查询
    ANALYSIS = 1     # 分析建议
    LOW_RISK = 2     # 低风险操作（通知）
    HIGH_RISK = 3    # 高风险操作（调整广告/价格）

@dataclass
class WorkflowNode:
    """工作流节点 — 参考 n8n node 格式"""
    id: str
    name: str
    type: NodeType
    config: dict  # 节点配置（prompt/mcp_tool/condition等）
    risk_level: RiskLevel = RiskLevel.READ_ONLY
    retry_count: int = 3
    timeout_ms: int = 30000

@dataclass
class WorkflowDefinition:
    """工作流定义 — 参考 n8n workflow JSON 文件格式"""
    name: str
    description: str
    trigger_type: str  # scheduled / webhook / manual
    trigger_config: dict  # cron表达式 或 webhook path
    nodes: list[WorkflowNode]
    connections: dict[str, list[str]]  # node_id -> [next_node_ids]
    settings: dict = field(default_factory=lambda: {
        "executionTimeout": 3600,
        "retryOnFail": True,
        "retryCount": 3,
        "maxExecutions": 100,
    })
    tags: list[str] = field(default_factory=list)

class WorkflowEngine:
    """
    工作流执行引擎
    参考 n8n 的执行模式 + n8n-workflows-main 的 integration_hub 事件驱动
    """
    def __init__(self):
        self.workflows: dict[str, WorkflowDefinition] = {}
        self.execution_history: list = []

    def register_workflow(self, workflow: WorkflowDefinition):
        """注册工作流"""
        self.workflows[workflow.name] = workflow

    async def execute(self, workflow_name: str, input_data: dict) -> dict:
        """执行工作流"""
        workflow = self.workflows[workflow_name]
        context = {"input": input_data, "results": {}}

        # 拓扑排序 → 顺序执行
        execution_order = self._topological_sort(workflow)
        for node in execution_order:
            try:
                result = await self._execute_node(node, context)
                context["results"][node.id] = result

                # 人审节点 → 暂停等待审批
                if node.type == NodeType.HUMAN_REVIEW:
                    approved = await self._request_approval(result)
                    if not approved:
                        return {"status": "rejected", "reason": "人工审批未通过"}
            except Exception as e:
                if workflow.settings.get("retryOnFail"):
                    for attempt in range(workflow.settings["retryCount"]):
                        result = await self._execute_node(node, context, retry=attempt)
                        if result.get("success"):
                            break
                else:
                    raise

        return {"status": "completed", "results": context["results"]}

    def _topological_sort(self, workflow: WorkflowDefinition) -> list[WorkflowNode]:
        """拓扑排序节点"""
        # ... 实现拓扑排序
        pass

    async def _execute_node(self, node: WorkflowNode, context: dict, retry: int = 0) -> dict:
        """执行单个节点"""
        # ... 按节点类型分发执行
        pass

    async def _request_approval(self, result: dict) -> bool:
        """人审请求"""
        # 发送审批到钉钉/企微 → 等待操作
        pass
```

### 2.2 意图识别器（参考 `src/ai_assistant.py`）

```python
# intent_detector.py — 意图识别 + 工作流匹配
"""
参考 n8n-workflows-main/src/ai_assistant.py 的：
- extract_keywords() → 电商关键词提取
- detect_intent() → 业务意图分类
- search_workflows_intelligent() → 匹配工作流
"""

class IntentDetector:
    """意图识别器 — 将用户自然语言请求匹配到工作流"""

    # 电商关键词库（参考 ai_assistant.py 的 automation_terms）
    ECOM_KEYWORDS = {
        "库存": ["库存", "FBA", "断货", "补货", "仓储", "冗余", "周转"],
        "广告": ["广告", "ACOS", "SP", "SB", "投放", "出价", "预算", "CTR", "CPC"],
        "利润": ["利润", "毛利", "净利", "亏损", "退款", "费用"],
        "Listing": ["Listing", "标题", "五点", "A+", "描述", "主图", "变体"],
        "竞品": ["竞品", "跟卖", "价格战", "BSR", "排名", "关键词排名"],
        "订单": ["订单", "销量", "转化率", "Buy Box", "购物车"],
        "预警": ["预警", "异常", "告警", "提醒", "通知"],
        "报表": ["日报", "周报", "报表", "导出", "汇总"],
    }

    def detect_intent(self, query: str) -> dict:
        """
        意图检测 — 参考 ai_assistant.py detect_intent()
        返回: {"intent": "inventory_alert", "confidence": 0.95, "entities": {...}}
        """
        query_lower = query.lower()
        scores = {}

        for intent, keywords in self.ECOM_KEYWORDS.items():
            scores[intent] = sum(1 for kw in keywords if kw.lower() in query_lower)

        if max(scores.values()) == 0:
            return {"intent": "general_chat", "confidence": 0.0}

        best_intent = max(scores, key=scores.get)
        return {
            "intent": best_intent,
            "confidence": scores[best_intent] / len(self.ECOM_KEYWORDS[best_intent]),
            "matched_keywords": [kw for kw in self.ECOM_KEYWORDS[best_intent] if kw in query_lower]
        }

    def match_workflow(self, intent: str, user_query: str) -> str:
        """匹配最合适的工作流"""
        # 参考 ai_assistant.py search_workflows_intelligent()
        workflow_mapping = {
            "库存": "inventory_alert_workflow",
            "广告": "ad_analysis_workflow",
            "利润": "profit_analysis_workflow",
            "Listing": "listing_query_workflow",
            "竞品": "competitor_monitor_workflow",
            "订单": "order_query_workflow",
            "预警": "alert_workflow",
            "报表": "report_generation_workflow",
        }
        return workflow_mapping.get(intent, "general_chat_workflow")
```

### 2.3 MCP 工具层（参考 `src/integration_hub.py`）

```python
# mcp_layer.py — 多服务集成层
"""
参考 n8n-workflows-main/src/integration_hub.py 的：
- register_integration() → MCP Server 注册
- sync_with_slack/discord() → 通知发送
- export_to_airtable/notion() → 数据导出
- register_webhook() → Webhook 管理
"""

from abc import ABC, abstractmethod

class BaseMCPServer(ABC):
    """MCP Server 基类"""
    def __init__(self, name: str):
        self.name = name
        self.tools: dict[str, Callable] = {}

    def register_tool(self, tool_name: str, tool_func: Callable):
        self.tools[tool_name] = tool_func

    @abstractmethod
    async def list_tools(self) -> list[dict]:
        """列出可用工具"""
        pass

    @abstractmethod
    async def call_tool(self, tool_name: str, params: dict) -> dict:
        """调用工具"""
        pass

# ──── 领星 ERP MCP Server ────
class LingxingMCPServer(BaseMCPServer):
    """领星 ERP MCP Server — 封装所有领星 API"""
    def __init__(self, api_key: str, base_url: str):
        super().__init__("lingxing-erp")
        self.api_key = api_key
        self.base_url = base_url
        self._register_tools()

    def _register_tools(self):
        # 商品管理
        self.register_tool("get_products", self.get_products)          # 商品列表
        self.register_tool("get_listing_detail", self.get_listing)     # Listing 详情
        # 库存管理
        self.register_tool("get_fba_inventory", self.get_fba_inv)     # FBA 库存
        self.register_tool("get_local_inventory", self.get_local_inv) # 本地库存
        # 订单管理
        self.register_tool("get_orders", self.get_orders)             # 订单列表
        self.register_tool("get_order_detail", self.get_order_detail) # 订单详情
        # 财务
        self.register_tool("get_profit_report", self.get_profit)      # 利润报表
        self.register_tool("get_settlement", self.get_settlement)     # 结算报告
        # 广告
        self.register_tool("get_ad_report", self.get_ad_report)       # 广告报表
        self.register_tool("get_ad_campaigns", self.get_ad_campaigns) # 广告活动

    async def list_tools(self) -> list[dict]:
        """返回可用工具列表（MCP 标准格式）"""
        return [
            {
                "name": "get_fba_inventory",
                "description": "查询所有商品的FBA库存，返回MSKU、ASIN、FBA库存量、可售/不可售/预留数量",
                "parameters": {"msku_list": "Optional[list[str]] — 指定MSKU列表，不传则查全部"}
            },
            {
                "name": "get_profit_report",
                "description": "查询利润报表，可按日期、SKU、账号维度汇总",
                "parameters": {
                    "start_date": "date",
                    "end_date": "date",
                    "sku": "Optional[str]",
                    "group_by": "sku|date|account"
                }
            },
            {
                "name": "get_ad_report",
                "description": "查询广告数据报表",
                "parameters": {
                    "start_date": "date",
                    "end_date": "date",
                    "campaign_type": "SP|SB|SD",
                    "metrics": "list[str]"
                }
            },
            # ... 更多工具
        ]
```

### 2.4 告警引擎（参考 `src/analytics_engine.py`）

```python
# alert_engine.py — 多维度预警系统
"""
参考 n8n-workflows-main/src/analytics_engine.py 的：
- get_workflow_analytics() → 多维度数据分析
- analyze_workflow_patterns() → 模式识别
- generate_recommendations() → 自动建议
"""

class AlertEngine:
    """告警引擎 — 多维度监控 + 智能预警"""

    ALERT_RULES = {
        # 库存告警
        "inventory_low": {
            "condition": "days_of_stock < 7",
            "level": "CRITICAL",
            "message": "🔴 {msku} ({asin}) FBA库存仅剩 {stock} 件，可售 {days_of_stock} 天，建议立即补货",
            "channel": ["dingtalk", "wecom"],
            "target": "@运营主管"
        },
        "inventory_high": {
            "condition": "days_of_stock > 90 AND fba_stock > 0",
            "level": "WARNING",
            "message": "🟡 {msku} ({asin}) 库存可售 {days_of_stock} 天，存在冗余风险，建议清货或移除",
        },
        # 广告异常
        "acos_spike": {
            "condition": "current_acos > avg_acos_14d * 1.5 AND current_acos > 30",
            "level": "WARNING",
            "message": "🟡 {campaign_name}: ACOS 从 {avg_acos_14d}% 飙升至 {current_acos}%，建议检查",
        },
        "ad_budget_exhausted": {
            "condition": "budget_utilization > 0.95 AND hour < 18",
            "level": "WARNING",
            "message": "🟡 {campaign_name}: 预算 {spend}/{budget} ({utilization}%)，可能在 {exhausted_hour}:00 前花完",
        },
        # 利润异常
        "profit_margin_drop": {
            "condition": "current_margin < avg_margin_30d * 0.8 AND current_margin < 10",
            "level": "CRITICAL",
            "message": "🔴 {sku}: 利润率从 {avg_margin}% 下降至 {current_margin}%，原因分析：退款率 {refund_rate}% / 广告占比 {ad_ratio}%",
        },
        # 竞品监控
        "price_drop_competitor": {
            "condition": "competitor_price < our_price * 0.85",
            "level": "WARNING",
            "message": "🟡 竞品 {competitor_asin} 降价至 ${competitor_price}（低于我方 {diff_pct}%），可能影响 Buy Box",
        },
        "new_hijacker": {
            "condition": "new_seller_on_listing",
            "level": "CRITICAL",
            "message": "🔴 {asin} Listing 发现新的跟卖者：{seller_name}，价格 ${price}",
        },
    }

    def evaluate_rules(self, data_snapshot: dict) -> list[dict]:
        """评估所有告警规则 → 返回触发的告警列表"""
        triggered = []
        for rule_name, rule in self.ALERT_RULES.items():
            if self._evaluate_condition(rule["condition"], data_snapshot):
                triggered.append({
                    "rule": rule_name,
                    "level": rule["level"],
                    "message": rule["message"].format(**data_snapshot),
                    "channel": rule.get("channel", ["dingtalk"]),
                    "target": rule.get("target")
                })
        return triggered

    def _evaluate_condition(self, condition: str, data: dict) -> bool:
        """安全地评估条件表达式"""
        # 使用简单的表达式评估器，支持 AND/OR/> /</=等
        pass
```

---

## 三、5 个核心 Agent 工作流设计

### 3.1 库存预警 Agent

```
Trigger: Cron 每4小时 / Webhook(领星库存变更)
   │
   ▼
Node 1: [TOOL] 拉取领星ERP FBA库存 + 本地库存
   │
   ▼
Node 2: [TOOL] 拉取近7天/30天日均销量
   │
   ▼
Node 3: [LLM] 分析库存健康度
   │  输入：库存量、日均销量、采购周期、在途库存
   │  输出：每个SKU的库存健康评分
   │
   ▼
Node 4: [CONDITION] 是否需要预警？
   │  条件：days_of_stock < 7 → CRITICAL
   │        days_of_stock < 14 → WARNING
   │        days_of_stock > 90 → 冗余警告
   │
   ├── YES ──► Node 5: [LLM] 生成预警报告
   │              │
   │              ▼
   │           Node 6: [NOTIFY] 推送钉钉/企微
   │              │
   │              ▼
   │           Node 7: [HUMAN_REVIEW] (高风险：自动创建补货计划)
   │
   └── NO  ──► Node 8: [OUTPUT] 记录正常，更新Dashboard
```

### 3.2 广告日报 Agent

```
Trigger: Cron 每天 08:00
   │
   ▼
Node 1: [TOOL] 拉取广告API数据 (SP/SB/SD)
   │  数据：展示量、点击量、花费、销售额、ACOS、CPC
   │
   ▼
Node 2: [TOOL] 拉取前7天/30天数据做对比
   │
   ▼
Node 3: [LLM] 数据汇总 + 异常检测
   │  输入：当日数据 + 对比数据
   │  输出：关键指标变化、异常点、优化建议
   │
   ▼
Node 4: [TOOL] 生成数据图表 (Matplotlib/ECharts)
   │
   ▼
Node 5: [NOTIFY] 推送日报到企微群
   │  格式：📊 广告日报 {date}
   │  ├── SP: spend={x} ACOS={y}% (↑/↓ z%)
   │  ├── SB: spend={x} ROAS={y} (↑/↓ z%)
   │  ├── SD: spend={x} ACOS={y}% (↑/↓ z%)
   │  ├── ⚠️ 异常告警：{campaign} ACOS飙升
   │  └── 💡 建议：{推荐操作}
   │
   ▼
Node 6: [OUTPUT] 存入数据库 + 更新Dashboard
```

### 3.3 利润异常预警 Agent

```
Trigger: Cron 每天 06:00
   │
   ▼
Node 1: [TOOL] 拉取领星ERP利润报表（前一天）
   │
   ▼
Node 2: [TOOL] 拉取广告花费 + 退款数据
   │
   ▼
Node 3: [LLM] 利润异常分析
   │  输入：每个SKU的毛利率 vs 30天均值
   │  异常条件：
   │  ├── 毛利率下降 > 20% vs 30天均值
   │  ├── 退款率 > 10%
   │  ├── 广告费占比 > 30%
   │  └── FBA费用异常增长
   │
   ▼
Node 4: [CONDITION] 发现异常？
   │
   ├── YES ──► Node 5: [LLM] 根因分析
   │              │  结合广告、退款、竞品价格变化
   │              │  输出：异常原因 + 建议措施
   │              │
   │              ▼
   │           Node 6: [NOTIFY] 推送给财务 + 运营
   │
   └── NO  ──► Node 7: [OUTPUT] 正常，记录日志
```

### 3.4 跟卖监控 Agent

```
Trigger: Cron 每2小时
   │
   ▼
Node 1: [TOOL] 扫描核心ASIN的Buy Box卖家列表
   │  数据源：亚马逊SP-API / 第三方监控
   │
   ▼
Node 2: [CONDITION] 卖家数量变化？出现新卖家？
   │
   ├── YES ──► Node 3: [LLM] 分析跟卖风险
   │              │  判断：价格差、卖家评级、是否恶意跟卖
   │              │
   │              ▼
   │           Node 4: [NOTIFY] 🔴 立即推送（高优先级）
   │              │
   │              ▼
   │           Node 5: [HUMAN_REVIEW] 建议：投诉/Test Buy/调价
   │
   └── NO  ──► Node 6: [OUTPUT] 记录快照
```

### 3.5 运营日报 Agent

```
Trigger: Cron 每天 09:00
   │
   ▼
Node 1: [TOOL] 并行拉取：
   │   ├── 订单/销售额（vs 昨天/上周同期）
   │   ├── 广告数据（花费/ACOS/ROAS）
   │   ├── 库存健康度（缺货SKU/冗余SKU）
   │   ├── 利润概览（毛利/净利/退款）
   │   └── 竞品动态（价格变动/BSR变化）
   │
   ▼
Node 2: [LLM] 汇总分析 + 生成日報
   │  格式：
   │  📊 运营日报 — {date}
   │  ━━━━━━━━━━━━━━━━━━━
   │  📈 销量：{total_sales} ({change}% vs 昨日)
   │  💰 利润：{gross_profit} (毛利率 {margin}%)
   │  📢 广告：ACOS {acos}% ({change}%)
   │  📦 库存：{ok_count}SKU正常 / {warn_count}SKU预警 / {oos_count}SKU缺货
   │  ⚠️ 异常：{alerts_summary}
   │
   ▼
Node 3: [TOOL] 导出Excel → 存入MinIO/S3
   │
   ▼
Node 4: [NOTIFY] 推送到管理层群 + 邮件发送Excel
```

---

## 四、Docker 部署架构（参考 ai-stack）

```yaml
# docker-compose.yml — 参考 n8n-workflows-main/ai-stack/docker-compose.yml
version: '3.8'

services:
  # ──── Agent API 核心 ────
  agent-api:
    build: .
    ports: ["8000:8000"]
    environment:
      - DATABASE_URL=postgresql://user:pass@db:5432/dsagent
      - REDIS_URL=redis://redis:6379
      - LINGXING_API_KEY=${LINGXING_API_KEY}
      - AMAZON_SP_API_KEY=${AMAZON_SP_API_KEY}
      - OPENAI_API_KEY=${OPENAI_API_KEY}
      - CLAUDE_API_KEY=${CLAUDE_API_KEY}
    depends_on: [db, redis]
    restart: always

  # ──── n8n 工作流编排（可选）────
  n8n:
    image: n8nio/n8n:latest
    ports: ["5678:5678"]
    environment:
      - N8N_BASIC_AUTH_ACTIVE=true
      - N8N_BASIC_AUTH_USER=${N8N_USER}
      - N8N_BASIC_AUTH_PASSWORD=${N8N_PASSWORD}
    volumes:
      - n8n_data:/home/node/.n8n
      - ./workflows:/backup/workflows
    restart: always

  # ──── PostgreSQL 业务数据库 ────
  db:
    image: postgres:16-alpine
    environment:
      - POSTGRES_USER=dsagent
      - POSTGRES_PASSWORD=${DB_PASSWORD}
      - POSTGRES_DB=dsagent
    volumes:
      - pg_data:/var/lib/postgresql/data
    restart: always

  # ──── Redis 缓存 + 任务队列 ────
  redis:
    image: redis:7-alpine
    volumes:
      - redis_data:/data
    restart: always

  # ──── ChromaDB 向量数据库 (RAG) ────
  chromadb:
    image: chromadb/chroma:latest
    ports: ["8001:8000"]
    volumes:
      - chroma_data:/chroma/chroma
    restart: always

  # ──── Celery Worker 异步任务 ────
  celery-worker:
    build: .
    command: celery -A app.celery worker -l info -Q default,high_priority
    environment:
      - DATABASE_URL=postgresql://user:pass@db:5432/dsagent
      - REDIS_URL=redis://redis:6379
    depends_on: [db, redis]
    restart: always

  # ──── Celery Beat 定时任务 ────
  celery-beat:
    build: .
    command: celery -A app.celery beat -l info
    depends_on: [redis, db]
    restart: always

  # ──── Prometheus 监控 ────
  prometheus:
    image: prom/prometheus:latest
    ports: ["9090:9090"]
    volumes:
      - ./monitoring/prometheus.yml:/etc/prometheus/prometheus.yml
      - prometheus_data:/prometheus
    restart: always

  # ──── Grafana 可视化 ────
  grafana:
    image: grafana/grafana:latest
    ports: ["3000:3000"]
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=${GRAFANA_PASSWORD}
    volumes:
      - grafana_data:/var/lib/grafana
      - ./monitoring/dashboards:/etc/grafana/provisioning/dashboards
    restart: always

volumes:
  pg_data:
  redis_data:
  chroma_data:
  n8n_data:
  prometheus_data:
  grafana_data:
```

---

## 五、项目目录结构

```
DSAgent/
├── docker-compose.yml              # 核心部署文件（参考 ai-stack）
├── requirements.txt
├── Dockerfile
├── .env                            # 环境变量
│
├── src/
│   ├── __init__.py
│   ├── main.py                     # FastAPI 入口（参考 enhanced_api.py + run.py）
│   │
│   ├── agent/                      # Agent 核心
│   │   ├── orchestrator.py         # Agent 编排器
│   │   ├── intent_detector.py      # 意图识别（参考 ai_assistant.py）
│   │   ├── workflow_engine.py      # 工作流执行引擎
│   │   └── prompt_templates.py     # Prompt 模板库
│   │
│   ├── agents/                     # 5 个业务 Agent
│   │   ├── inventory_agent.py      # 库存预警
│   │   ├── ad_report_agent.py      # 广告日报
│   │   ├── profit_agent.py         # 利润分析
│   │   ├── hijack_agent.py         # 跟卖监控
│   │   └── daily_report_agent.py   # 运营日报
│   │
│   ├── mcp/                        # MCP Server 层（参考 integration_hub.py）
│   │   ├── base_server.py          # MCP 基类
│   │   ├── lingxing_server.py      # 领星 ERP MCP
│   │   ├── amazon_sp_server.py     # 亚马逊 SP-API MCP
│   │   ├── ad_api_server.py        # 广告 API MCP
│   │   └── notify_server.py        # 通知服务 MCP
│   │
│   ├── data/                       # 数据层
│   │   ├── models.py               # SQLAlchemy 模型
│   │   ├── database.py             # 数据库连接
│   │   ├── etl.py                  # 数据提取/转换
│   │   └── analytics.py            # 数据分析（参考 analytics_engine.py）
│   │
│   ├── alert/                      # 告警引擎
│   │   ├── engine.py               # 告警规则引擎
│   │   ├── rules.py                # 告警规则配置
│   │   └── dispatcher.py           # 告警分发（钉钉/企微/邮件）
│   │
│   ├── security/                   # 安全模块（参考 user_management.py）
│   │   ├── auth.py                 # 认证
│   │   ├── permissions.py          # 权限控制
│   │   ├── approval.py             # 人审流程
│   │   └── audit.py                # 审计日志
│   │
│   └── monitor/                    # 监控（参考 performance_monitor.py）
│       ├── metrics.py              # 指标采集
│       ├── alerts.py               # 系统告警
│       └── dashboard.py            # 监控看板
│
├── workflows/                      # 工作流定义（JSON 格式，参考 n8n workflows）
│   ├── inventory_alert.json
│   ├── ad_daily_report.json
│   ├── profit_anomaly.json
│   ├── hijack_monitor.json
│   └── daily_report.json
│
├── docs/
│   ├── 跨境电商AI_Agent基础知识提纲.md
│   ├── 电商Agent框架设计.md
│   ├── api_reference.md
│   └── deployment.md
│
├── tests/
│   ├── test_agents/
│   ├── test_mcp/
│   └── test_workflows/
│
└── monitoring/
    ├── prometheus.yml
    └── dashboards/
```

---

## 六、n8n-workflows-main 设计模式复用对照表

| n8n 源码模块 | 核心设计模式 | 在电商 Agent 框架中的复用 |
|-------------|-------------|------------------------|
| `src/ai_assistant.py` | 关键词提取 + 意图识别 + 工作流匹配 | `agent/intent_detector.py` — 电商关键词库 + 意图→工作流映射 |
| `src/integration_hub.py` | 多服务注册 + Webhook 分发 + 通知适配器 | `mcp/` 目录 — MCP Server 注册机制 + Webhook 事件驱动 |
| `src/analytics_engine.py` | 多维度分析 + 模式识别 + 智能推荐 | `data/analytics.py` + `alert/engine.py` — 数据分析 + 告警规则评估 |
| `src/enhanced_api.py` | RESTful API + 搜索过滤 + 缓存优化 | `src/main.py` — FastAPI 路由 + 搜索 + 缓存 |
| `src/community_features.py` | 用户评分 + 统计追踪 + 收藏/订阅 | `security/` — 用户系统 + 审计日志 + 操作追踪 |
| `src/performance_monitor.py` | 指标采集 + 告警 + 历史数据 | `monitor/` — Prometheus 指标 + 系统告警 |
| `src/user_management.py` | 用户注册/登录 + API Key + 角色权限 | `security/auth.py` + `security/permissions.py` |
| `workflows/` (170+ 目录) | JSON 定义的工作流 + Trigger-Node-Connection | `workflows/` — JSON 定义的 Agent 工作流 |
| `ai-stack/docker-compose.yml` | Docker 一体化部署 + n8n + Agent + 模型服务 | `docker-compose.yml` — Agent API + n8n + DB + Redis + 监控 |
| `workflow_db.py` | SQLite 数据库 + 索引搜索 | `data/database.py` — PostgreSQL + SQLAlchemy ORM |
| `api_server.py` | 单一入口 + 路由挂载 + 静态文件 | `src/main.py` — FastAPI app + 多功能路由 |
