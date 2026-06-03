# DS Agent v3.0 — AI 运营指挥中心设计文档

> 状态: 设计完成，待实现  
> 日期: 2026-06-02  
> 基于: v2.0 积木式架构重构

---

## 一、产品定位

从 "AI 聊天助手" 升级为 **"AI 运营指挥中心"**：

> AI 在后台持续监控数据 → 全量分析每一项指标 → 有异常告警、有机会建议、正常则静默记录 → 用户拍板决策

核心变化：
- ~~对话式交互~~ → 监控大屏 + 告警决策
- ~~手动触发~~ → 定时自动轮询 + 变动检测
- ~~Mock 假数据~~ → 多数据源可切换（卖家精灵 / Sorftime / 领星 ERP）
- ~~写死 Claude~~ → LLM 可配置（Claude / GPT / DeepSeek / 千问 / GLM / 自定义）

---

## 二、架构总览

```
┌─────────────────────────────────────────────────────────┐
│                    前端指挥大屏                           │
│  监控卡片 │ 告警列表 │ 决策按钮 │ 竞品地图 │ 决策日志      │
└────────────────────────┬────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────┐
│                    Agent API (FastAPI)                   │
│                                                         │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌────────────┐ │
│  │ 配置系统   │ │ 分析管线   │ │ 决策引擎   │ │ 调度器      │ │
│  └────┬─────┘ └────┬─────┘ └────┬─────┘ └─────┬──────┘ │
│       │             │             │              │       │
│  ┌────▼─────────────▼─────────────▼──────────────▼────┐ │
│  │                  7 个 Agent                         │ │
│  │  库存 │ 广告 │ 利润 │ 跟卖 │ 竞品发现 │ 竞品分析 │ 日报 │ │
│  └────────────────────────────────────────────────────┘ │
└────────────────────────┬────────────────────────────────┘
                         │
          ┌──────────────┼──────────────┐
          ▼              ▼              ▼
    卖家精灵 MCP     Sorftime MCP    领星 ERP
    (42工具)         (34+工具)       (REST API)
```

---

## 三、配置系统

### 3.1 LLM 配置

支持的主流 LLM Provider：

| Provider | 模型示例 | 调用方式 |
|----------|---------|---------|
| claude | claude-sonnet-4-6 | Anthropic SDK |
| openai | gpt-4o | OpenAI SDK |
| deepseek | deepseek-chat | OpenAI 兼容 URL |
| qwen | qwen-max | OpenAI 兼容 URL |
| glm | glm-4 | OpenAI 兼容 URL |
| custom | 用户自填 | OpenAI 兼容 URL |

配置示例：

```yaml
# config.yaml
llm:
  provider: deepseek
  model: deepseek-chat
  api_key: ${DEEPSEEK_KEY}
  base_url: https://api.deepseek.com/v1
  max_tokens: 4096
  temperature: 0.3
```

### 3.2 数据源配置

支持三种协议类型的多数据源：

```yaml
datasources:
  - name: sellersprite
    type: mcp_sse
    url: https://mcp.sellersprite.com/sse
    secret_key: ${SELLERSPRITE_KEY}
    enabled: true
    tools: 42
    
  - name: sorftime
    type: mcp_http
    url: https://mcp.sorftime.com
    auth_key: ${SORFTIME_KEY}
    enabled: false
    tools: 34
    
  - name: lingxing
    type: rest_api
    base_url: https://api.lingxing.com
    api_key: ${LINGXING_KEY}
    enabled: true
```

### 3.3 数据路由

不同 Agent 优先使用哪个数据源：

```yaml
routing:
  inventory:    [lingxing, sellersprite]
  sales:        [lingxing, sellersprite, sorftime]
  advertising:  [lingxing, sellersprite]
  competitor:   [sellersprite, sorftime]
  keyword:      [sellersprite, sorftime]
  market:       [sellersprite, sorftime]
  review:       [sellersprite, sorftime]
  profit:       [lingxing]
  product:      [sellersprite, sorftime, lingxing]
```

### 3.4 调度配置

```yaml
scheduler:
  interval_minutes: 5
  auto_approve_low_risk: true

alert:
  channels:
    - type: dingtalk
      webhook: ${DINGTALK_WEBHOOK}
    - type: wecom
      webhook: ${WECOM_WEBHOOK}
```

---

## 四、数据标准化体系

### 4.1 三层架构

```
Agent 层        → 只认标准化模型 (InventorySnapshot, AdMetrics...)
标准化模型层    → 统一定义字段、类型、单位
适配器层        → 字段映射 + 单位换算 + 缺失补全 + 溯源标记
```

### 4.2 核心标准化模型

```python
@dataclass
class ProductInfo:
    sku: str; asin: str; name: str; brand: str
    price: float; cost: float; category: str; status: str

@dataclass
class InventorySnapshot:
    sku: str; asin: str; product_name: str
    fba_stock: int; reserved_stock: int; inbound_stock: int
    daily_sales: float; days_of_stock: float; warehouse: str
    provenance: DataProvenance

@dataclass
class AdMetrics:
    campaign_id: str; campaign_name: str; ad_type: str
    spend: float; sales: float; impressions: int; clicks: int
    acos: float; roas: float; cpc: float
    budget: float; budget_used_pct: float
    provenance: DataProvenance

@dataclass
class CompetitorSnapshot:
    asin: str; buy_box_owner: str; buy_box_price: float
    our_price: float; seller_count: int
    new_sellers: list; bsr: int; bsr_change: int
    provenance: DataProvenance
```

### 4.3 数据溯源

每条标准化数据都携带 `DataProvenance`：

```python
@dataclass
class DataProvenance:
    source: str            # sellersprite / sorftime / lingxing
    source_type: str       # mcp_sse / mcp_http / rest_api
    platform: str          # amazon_us / amazon_jp / walmart
    marketplace: str       # ATVPDKIKX0DER
    fetched_at: str        # ISO8601
    query_duration_ms: int
    is_fresh: bool
```

### 4.4 适配器示例

```python
class SellerSpriteAdapter(BaseAdapter):
    def to_inventory(self, raw: dict) -> InventorySnapshot:
        return InventorySnapshot(
            sku=raw.get("seller_sku", ""),
            asin=raw["asin"],
            fba_stock=raw.get("fba_stock", 0),
            daily_sales=round(raw.get("sales_30d", 0) / 30, 1),
            provenance=DataProvenance(source="sellersprite", ...)
        )

class LingxingAdapter(BaseAdapter):
    def to_inventory(self, raw: dict) -> InventorySnapshot:
        return InventorySnapshot(
            sku=raw["msku"],
            asin=raw["item_asin"],
            fba_stock=raw["available_qty"],
            daily_sales=raw.get("daily_avg_7d", 0),
            provenance=DataProvenance(source="lingxing", ...)
        )
```

---

## 五、数据存储策略

### 5.1 两层存储

```
原始数据层 (按来源分库)
├── lingxing/2026-06-02T06:00.json       ← 原始 JSON
├── sellersprite/2026-06-02T06:00.json   ← 原始 JSON
└── sorftime/2026-06-02T06:00.json       ← 原始 JSON
  保留 7 天，用于审计对账

标准化快照层 (合并)
├── inventory/2026-06-02T06:00.parquet   ← 所有来源合并
├── advertising/2026-06-02T06:00.parquet
└── competitor/2026-06-02T06:00.parquet
  保留 90 天，Agent 读这里做对比
```

### 5.2 降级策略（生产环境）

```
第一数据源挂了
  → 尝试第二数据源
  → 第二也挂了
  → 停止。不使用 Mock 数据。
  → 前端卡片标记 ⚠️ 离线
  → 推送告警：数据源断开
  → 保留最后一份快照，标记 is_fresh=False
```

**Mock 数据仅在 `MOCK_MODE=true` 开发模式下启用。生产环境不参与降级。**

---

## 六、全量 AI 分析管线

### 6.1 三道工序

```
数据流入
  │
  ▼
第一道：规则引擎（硬筛子，毫秒级）
  ├── 明显异常 → 标记，进入 AI 分析
  ├── 明显正常 → 跳过 AI，直接写日志
  └── 不明显的 → 进入 AI 分析
  │
  ▼
第二道：AI 深度分析（LLM，秒级）
  分析: 变动原因 / 市场关联 / 未来预测 / 优化机会
  │
  ▼
第三道：分类输出
  ├── 🔴 告警 → 推给用户，带决策按钮
  ├── 🟡 建议 → 推给用户，为可选优化
  └── 🟢 正常 → 写日志，更新面板，用户无感知
```

### 6.2 核心代码结构

```python
class AnalysisPipeline:
    async def process(self, snapshot: Snapshot, previous: Snapshot) -> AnalysisResult:
        # 1. 规则预筛
        rule_alerts = self.rule_engine.evaluate(snapshot, previous)
        rule_normal = self.rule_engine.identify_normal(snapshot, previous)
        
        # 2. 找出需要 AI 分析的
        needs_ai = [item for item in snapshot.items 
                    if item.id not in rule_normal.ids]
        
        if not needs_ai:
            self.log.info(f"一切正常, {len(snapshot.items)}项")
            return AnalysisResult(status="normal")
        
        # 3. AI 逐项分析
        llm_result = await self.llm.analyze(
            prompt="full_analysis",
            context={
                "current": needs_ai,
                "previous": previous.match(needs_ai),
                "market_context": await self.get_market_context(),
            }
        )
        
        # 4. 分类
        alerts = [i for i in llm_result.items if i.severity in ("critical","warning")]
        suggestions = [i for i in llm_result.items if i.has_optimization]
        normal = [i for i in llm_result.items if i.severity == "normal"]
        
        self.log_analysis(alerts, suggestions, normal)
        return AnalysisResult(alerts=alerts, suggestions=suggestions)
```

### 6.3 用户看到的效果

```
🔴 2 条告警 (需要决策)
├── SKU-CHG001 库存仅剩0.1天 → [批准补货] [忽略]
└── B08ABC Buy Box被抢 → [调价] [投诉] [忽略]

🟡 3 条优化建议 (可选)
├── SP-Manual ACOS飙升 → 建议降出价 [采纳] [忽略]
├── SKU-BT001 销量周增14% → 建议追加预算 [采纳] [忽略]
└── B07DEF 竞品降价28%但BSR未受影响 → 建议观察 [采纳] [忽略]

📋 已记录: 6项正常
```

---

## 七、变动追踪 & 告警系统

### 7.1 数据变动记录

```python
@dataclass
class DataChange:
    platform: str          # amazon_us
    asin: str; sku: str
    product_name: str
    data_source: str       # lingxing
    field: str             # fba_stock
    previous_value: any    # 15
    current_value: any     # 2
    change_pct: float      # -86.7%
    change_direction: str  # down
    previous_snapshot_at: str
    detected_at: str

@dataclass
class Alert:
    id: str
    rule: str; severity: str
    changes: list[DataChange]
    llm_provider: str; llm_model: str
    suggestion: str; suggestion_reason: str
    decision: str         # pending / approved / rejected / auto_executed
    decided_by: str; decided_at: str
```

### 7.2 前端展示

```
告警详情
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📍 Amazon US | 📡 领星 ERP | 🕐 06:00:00 | ⏱ 234ms

商品: SKU-CHG001 / B07DEF5678
     USB-C Fast Charger 65W GaN

变动明细:
┌──────────┬────────┬────────┬────────┬──────┐
│ 指标      │ 上次    │ 本次    │ 变动    │ 趋势  │
├──────────┼────────┼────────┼────────┼──────┤
│ FBA库存   │ 15件   │ 2件    │ -86.7% │ 🔻   │
│ 可售天数  │ 1.5天  │ 0.1天  │ -93.3% │ 🔻   │
│ 日均销量  │ 10.0   │ 18.0   │ +80%   │ 🔺   │
└──────────┴────────┴────────┴────────┴──────┘

🤖 AI 分析 (DeepSeek-Chat):
  销量暴增80%导致库存加速消耗。在途500件预计2天后入库，
  但当前仅剩2件，存在断货风险。
  建议: 立即创建补货计划 500件

[✅ 批准补货] [✗ 忽略]
```

---

## 八、竞品自动发现 & 追踪

### 8.1 四条发现路径

```
1. 关键词维度
   我的核心关键词 → keyword_research Top20 → 发现竞品 ASIN

2. 类目维度
   我的类目 → market_research Top100 → BSR相邻 → 发现竞品

3. 流量维度
   我的 ASIN → traffic_listing 关联流量 → 发现间接竞品

4. 自然发现
   Listing关联 → competitor_lookup → 发现竞品
```

### 8.2 竞品分析

```python
class CompetitorAnalysisAgent:
    async def analyze(self, competitor_asin: str) -> CompetitorReport:
        history = await self.tracker.get_history(competitor_asin, days=30)
        changes = self.diff_engine.analyze_trends(history)
        analysis = await self.llm.analyze(
            prompt="competitor_strategy",
            context={
                "competitor": competitor_asin,
                "history": history,
                "changes": changes,
                "our_data": await self.get_our_data(),
            }
        )
        return CompetitorReport(
            asin=competitor_asin,
            strategy_inference=analysis.strategy,
            threat_level=analysis.threat_level,
            recommendations=analysis.recommendations,
        )
```

### 8.3 AI 分析内容

对竞品的行为做三个维度的分析：

| 分析维度 | 内容 |
|---------|------|
| 策略推断 | 降价/冲评/站外引流/清库存？ |
| 威胁评估 | 高危/中危/低危 + 理由 |
| 对策建议 | 跟进/观望/差异化/避开 |

---

## 九、Agent 列表

| Agent | 触发方式 | 数据源 | 分析内容 |
|-------|---------|--------|---------|
| 库存预警 | 定时 / 变动检测 | 领星 > 卖家精灵 | FBA库存健康度、补货建议 |
| 广告日报 | 定时 | 领星 > 卖家精灵 | ACOS异常、预算检测、关键词优化 |
| 利润分析 | 定时 | 领星 | 毛利率波动、退款率、广告占比 |
| 跟卖监控 | 定时 | 卖家精灵 > Sorftime | Buy Box、新卖家、价格异常 |
| 竞品发现 | 定时 / 手动 | 卖家精灵 > Sorftime | 自动发现新竞品 |
| 竞品分析 | 发现后触发 | 卖家精灵 > Sorftime | 策略推断、威胁评估、对策 |
| 运营日报 | 定时 | 全部 | 全店核心指标汇总 |

---

## 十、前端指挥大屏

```
┌──────────────────────────────────────────────────────────┐
│  DS Agent 指挥中心                      下次刷新 4:32 🔄 │
├─────────┬─────────┬─────────┬─────────┬──────────────────┤
│ 📦 库存  │ 📢 广告  │ 💰 利润  │ 🔍 跟卖  │ 🎯 竞品          │
│ 8 SKU  │ 4 活动   │ 4 SKU  │ 3 ASIN  │ 12 竞品 (2新)    │
│ 🔴5 🟢3│ 🟡1 🟢3│ 🔴2 🟡1│ 🔴2 🟢1│ 3 高威胁          │
├─────────┴─────────┴─────────┴─────────┴──────────────────┤
│ ⚠️ 告警中心 (3条未处理)                       [全部批准]   │
│ ┌──────────────────────────────────────────────────────┐ │
│ │ 🔴 14:32 SKU-CHG001 库存仅剩0.1天 → [批准补货][忽略]  │ │
│ │ 🔴 14:30 B08ABC Buy Box被抢 → [调价][投诉][忽略]      │ │
│ │ 🟡 14:28 SP-Manual ACOS飙升 → [降出价][忽略]         │ │
│ └──────────────────────────────────────────────────────┘ │
│                                                        │
│ 💡 优化建议 (2条)                                       │
│ ├── SKU-BT001 销量周增14% → 建议追加广告预算 [采纳]      │
│ └── CHG001 竞品降价28% → 建议观察3天暂不跟进 [采纳]      │
│                                                        │
│ 📋 决策日志                                             │
│ 14:35 ✅ 已批准补货 / 14:32 ✅ 已批准调价                │
└──────────────────────────────────────────────────────────┘
```

卡片状态：
- 正常：绿色边框，显示 ✅ 正常监控中
- 数据源离线：黄色边框，显示 ⚠️ 离线 + 上次刷新时间 + [重试]
- 有异常：红色脉冲边框，数字跳动动画

---

## 十一、决策引擎

### 11.1 决策分级

| 风险等级 | 操作类型 | 处理方式 |
|---------|---------|---------|
| READ_ONLY | 只读查询 | 自动执行 |
| LOW_RISK | 发通知、记录日志 | 自动执行 |
| ANALYSIS | 生成建议 | 弹出给用户确认 |
| HIGH_RISK | 调价、投诉、补货 | 必须用户手动批准 |

### 11.2 决策记录

```python
@dataclass
class DecisionRecord:
    alert_id: str
    decision: str          # approved / rejected / auto_executed / pending
    decided_by: str
    decided_at: str
    action_taken: str      # 实际操作内容
    action_result: str     # 执行结果
    note: str              # 用户备注
```

---

## 十二、项目文件结构

```
DSAgent/
├── config.yaml                    # 用户配置文件
├── .env                           # 密钥
├── docker-compose.yml
├── Dockerfile
├── requirements.txt
│
├── src/
│   ├── main.py                    # FastAPI 入口
│   │
│   ├── config/                    # 🆕 配置系统
│   │   ├── settings.py            # 全局配置加载
│   │   ├── llm_config.py          # LLM Provider 注册
│   │   └── datasource_config.py   # 数据源注册
│   │
│   ├── datasource/                # 🆕 数据源抽象层
│   │   ├── base.py                # 抽象基类 + 标准化模型
│   │   ├── models.py              # 所有标准化数据模型
│   │   ├── mcp_client.py          # 通用 MCP 协议客户端
│   │   ├── adapter_sellersprite.py
│   │   ├── adapter_sorftime.py
│   │   ├── adapter_lingxing.py
│   │   ├── router.py              # 数据路由 + 降级
│   │   └── registry.py            # 数据源注册中心
│   │
│   ├── llm/                       # 🆕 LLM 抽象层
│   │   ├── base.py                # 抽象基类
│   │   ├── providers/
│   │   │   ├── claude.py
│   │   │   ├── openai_compat.py   # OpenAI / DeepSeek / Qwen / GLM / Custom
│   │   └── factory.py
│   │
│   ├── engine/                    # 🆕 引擎层
│   │   ├── diff_engine.py         # 数据快照对比
│   │   ├── analysis_pipeline.py   # 全量分析管线
│   │   ├── decision_engine.py     # 决策记录
│   │   └── scheduler.py           # 定时轮询
│   │
│   ├── agents/                    # 改造: 接数据源 + 分析管线
│   │   ├── inventory_agent.py
│   │   ├── ad_report_agent.py
│   │   ├── profit_agent.py
│   │   ├── hijack_agent.py
│   │   ├── competitor_discovery_agent.py   # 🆕
│   │   ├── competitor_analysis_agent.py    # 🆕
│   │   └── daily_report_agent.py
│   │
│   ├── storage/                   # 🆕 数据存储
│   │   ├── raw_store.py           # 原始数据 (按源分)
│   │   ├── snapshot_store.py      # 快照 (合并)
│   │   └── decision_log.py        # 决策日志
│   │
│   ├── mcp/                       # 保留 v2.0
│   │   ├── base_server.py
│   │   ├── client.py
│   │   ├── mock_data.py
│   │   └── ...
│   │
│   ├── alert/                     # 保留 v2.0
│   │   └── engine.py
│   │
│   └── static/
│       └── index.html             # 指挥大屏
│
├── workflows/                     # 工作流 JSON
├── docs/
│   └── DS_Agent_v3.0_Design.md    # 本文档
└── tests/
```

---

## 十三、实施计划

| 阶段 | 内容 | 文件 |
|------|------|------|
| 1 | 配置系统 | `config/` |
| 2 | LLM 抽象层 | `llm/` |
| 3 | 数据源抽象 + 3个适配器 | `datasource/` |
| 4 | 存储层 | `storage/` |
| 5 | 对比引擎 + 分析管线 + 决策引擎 | `engine/` |
| 6 | 调度器 | `engine/scheduler.py` |
| 7 | 改造 5 个 + 新增 2 个 Agent | `agents/` |
| 8 | 前端指挥大屏 | `static/index.html` |
| 9 | 端到端联调 + API 更新 | `main.py` |

---

## 十四、关键设计决策记录

| 决策 | 结论 | 理由 |
|------|------|------|
| 降级是否用 Mock | 生产环境不用 | 假数据做决策比没数据更危险 |
| 数据源离线时 | 保留最后快照 + 标记过期 + 推告警 | 不丢历史，但也不误导 |
| 原始数据是否分源存 | 是，分源存原始，合并存快照 | 审计可追溯，Agent 读合并 |
| AI 分析范围 | 全量分析，正常静默 | 不放过任何异常和机会 |
| LLM 适配方式 | OpenAI 兼容协议统一 | 一视同仁，加新 Provider 零代码 |
| 竞品发现 | 4 条路径并行自动发现 | 关键词 + 类目 + 流量 + 关联 |
