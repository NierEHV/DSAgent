"""
Mock 数据层 — 逼真的亚马逊卖家模拟数据
所有 MCP Server 共享的底层数据，保证数据一致性
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional

# ──────────────────────────────────────────────
# 基础配置
# ──────────────────────────────────────────────
TODAY = datetime.now().strftime("%Y-%m-%d")
YESTERDAY = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")

# ──────────────────────────────────────────────
# 产品目录
# ──────────────────────────────────────────────
PRODUCTS = [
    {
        "msku": "SKU-BT001-BLK",
        "asin": "B09XYZ0001",
        "name": "Bluetooth 5.3 Wireless Earbuds - Black",
        "name_cn": "蓝牙5.3无线耳机-黑色",
        "brand": "SoundPro",
        "category": "Electronics > Headphones",
        "price": 29.99,
        "cost": 12.50,
        "weight_lbs": 0.15,
        "dimensions": "4.5x2.2x1.8 in",
        "created_at": "2024-03-15",
        "status": "active",
    },
    {
        "msku": "SKU-BT001-WHT",
        "asin": "B09XYZ0002",
        "name": "Bluetooth 5.3 Wireless Earbuds - White",
        "name_cn": "蓝牙5.3无线耳机-白色",
        "brand": "SoundPro",
        "category": "Electronics > Headphones",
        "price": 29.99,
        "cost": 12.50,
        "weight_lbs": 0.15,
        "dimensions": "4.5x2.2x1.8 in",
        "created_at": "2024-03-15",
        "status": "active",
    },
    {
        "msku": "SKU-SPK001",
        "asin": "B08ABC1234",
        "name": "Portable Bluetooth Speaker IPX7 Waterproof",
        "name_cn": "便携蓝牙音箱 IPX7防水",
        "brand": "SoundPro",
        "category": "Electronics > Speakers",
        "price": 39.99,
        "cost": 18.00,
        "weight_lbs": 1.2,
        "dimensions": "7.5x3.0x3.0 in",
        "created_at": "2024-01-10",
        "status": "active",
    },
    {
        "msku": "SKU-CHG001",
        "asin": "B07DEF5678",
        "name": "USB-C Fast Charger 65W GaN",
        "name_cn": "USB-C 65W GaN 快充头",
        "brand": "PowerUp",
        "category": "Electronics > Accessories > Chargers",
        "price": 24.99,
        "cost": 9.80,
        "weight_lbs": 0.25,
        "dimensions": "2.1x2.1x1.1 in",
        "created_at": "2024-06-20",
        "status": "active",
    },
    {
        "msku": "SKU-CHG002",
        "asin": "B07DEF5679",
        "name": "USB-C to Lightning Cable 6ft 3-Pack",
        "name_cn": "USB-C转Lightning线 6英尺 3条装",
        "brand": "PowerUp",
        "category": "Electronics > Accessories > Cables",
        "price": 14.99,
        "cost": 4.20,
        "weight_lbs": 0.30,
        "dimensions": "6.0x4.0x1.0 in",
        "created_at": "2024-06-20",
        "status": "active",
    },
    {
        "msku": "SKU-LMP001",
        "asin": "B05GHI9012",
        "name": "Smart LED Desk Lamp with Wireless Charger",
        "name_cn": "智能LED台灯带无线充电",
        "brand": "BrightLife",
        "category": "Home & Kitchen > Lighting",
        "price": 49.99,
        "cost": 22.00,
        "weight_lbs": 2.8,
        "dimensions": "16.0x6.0x6.0 in",
        "created_at": "2024-02-01",
        "status": "active",
    },
    {
        "msku": "SKU-BTL001",
        "asin": "B06JKL3456",
        "name": "Stainless Steel Water Bottle 32oz",
        "name_cn": "不锈钢保温水壶 32oz",
        "brand": "EcoVessel",
        "category": "Sports & Outdoors > Water Bottles",
        "price": 22.99,
        "cost": 7.50,
        "weight_lbs": 0.85,
        "dimensions": "10.5x3.5x3.5 in",
        "created_at": "2024-04-10",
        "status": "active",
    },
    {
        "msku": "SKU-BTL002",
        "asin": "B06JKL3457",
        "name": "Stainless Steel Water Bottle 32oz - Sport Cap",
        "name_cn": "不锈钢保温水壶 32oz - 运动盖",
        "brand": "EcoVessel",
        "category": "Sports & Outdoors > Water Bottles",
        "price": 24.99,
        "cost": 8.00,
        "weight_lbs": 0.88,
        "dimensions": "10.8x3.5x3.5 in",
        "created_at": "2024-04-10",
        "status": "active",
    },
]

# ──────────────────────────────────────────────
# FBA 库存数据（重点：有些缺货、有些冗余）
# ──────────────────────────────────────────────
FBA_INVENTORY = [
    {
        "msku": "SKU-BT001-BLK",
        "asin": "B09XYZ0001",
        "fnsku": "X001ABC123",
        "total_qty": 45,
        "available_qty": 38,
        "inbound_qty": 200,
        "reserved_qty": 7,
        "unfulfillable_qty": 0,
        "condition": "New",
        "warehouse": "ONT8",
    },
    {
        "msku": "SKU-BT001-WHT",
        "asin": "B09XYZ0002",
        "fnsku": "X001ABC124",
        "total_qty": 12,   # ⚠️ 低库存!
        "available_qty": 10,
        "inbound_qty": 0,
        "reserved_qty": 2,
        "unfulfillable_qty": 0,
        "condition": "New",
        "warehouse": "ONT8",
    },
    {
        "msku": "SKU-SPK001",
        "asin": "B08ABC1234",
        "fnsku": "X002DEF456",
        "total_qty": 520,  # ⚠️ 冗余库存!
        "available_qty": 510,
        "inbound_qty": 0,
        "reserved_qty": 10,
        "unfulfillable_qty": 0,
        "condition": "New",
        "warehouse": "FTW1",
    },
    {
        "msku": "SKU-CHG001",
        "asin": "B07DEF5678",
        "fnsku": "X003GHI789",
        "total_qty": 3,    # 🔴 即将断货!
        "available_qty": 2,
        "inbound_qty": 500,
        "reserved_qty": 1,
        "unfulfillable_qty": 0,
        "condition": "New",
        "warehouse": "ONT8",
    },
    {
        "msku": "SKU-CHG002",
        "asin": "B07DEF5679",
        "fnsku": "X003GHI790",
        "total_qty": 180,
        "available_qty": 170,
        "inbound_qty": 0,
        "reserved_qty": 10,
        "unfulfillable_qty": 0,
        "condition": "New",
        "warehouse": "ONT8",
    },
    {
        "msku": "SKU-LMP001",
        "asin": "B05GHI9012",
        "fnsku": "X004JKL012",
        "total_qty": 85,
        "available_qty": 80,
        "inbound_qty": 100,
        "reserved_qty": 5,
        "unfulfillable_qty": 0,
        "condition": "New",
        "warehouse": "ONT8",
    },
    {
        "msku": "SKU-BTL001",
        "asin": "B06JKL3456",
        "fnsku": "X005MNO345",
        "total_qty": 210,
        "available_qty": 200,
        "inbound_qty": 0,
        "reserved_qty": 10,
        "unfulfillable_qty": 0,
        "condition": "New",
        "warehouse": "FTW1",
    },
    {
        "msku": "SKU-BTL002",
        "asin": "B06JKL3457",
        "fnsku": "X005MNO346",
        "total_qty": 6,    # 🔴 即将断货!
        "available_qty": 5,
        "inbound_qty": 0,
        "reserved_qty": 1,
        "unfulfillable_qty": 0,
        "condition": "New",
        "warehouse": "FTW1",
    },
]

# ──────────────────────────────────────────────
# 近7天/30天日均销量
# ──────────────────────────────────────────────
SALES_DATA = [
    {"msku": "SKU-BT001-BLK", "asin": "B09XYZ0001", "daily_avg_7d": 12.0, "daily_avg_30d": 10.5, "trend": "up", "change_pct": 14.3},
    {"msku": "SKU-BT001-WHT", "asin": "B09XYZ0002", "daily_avg_7d": 8.5,  "daily_avg_30d": 9.2,  "trend": "down", "change_pct": -7.6},
    {"msku": "SKU-SPK001",  "asin": "B08ABC1234", "daily_avg_7d": 4.0,  "daily_avg_30d": 5.5,  "trend": "down", "change_pct": -27.3},
    {"msku": "SKU-CHG001",  "asin": "B07DEF5678", "daily_avg_7d": 18.0, "daily_avg_30d": 15.0, "trend": "up", "change_pct": 20.0},
    {"msku": "SKU-CHG002",  "asin": "B07DEF5679", "daily_avg_7d": 25.0, "daily_avg_30d": 22.0, "trend": "up", "change_pct": 13.6},
    {"msku": "SKU-LMP001",  "asin": "B05GHI9012", "daily_avg_7d": 3.0,  "daily_avg_30d": 3.5,  "trend": "down", "change_pct": -14.3},
    {"msku": "SKU-BTL001",  "asin": "B06JKL3456", "daily_avg_7d": 6.0,  "daily_avg_30d": 5.0,  "trend": "up", "change_pct": 20.0},
    {"msku": "SKU-BTL002",  "asin": "B06JKL3457", "daily_avg_7d": 7.5,  "daily_avg_30d": 6.8,  "trend": "up", "change_pct": 10.3},
]

# ──────────────────────────────────────────────
# 在途库存（FBA 发货计划）
# ──────────────────────────────────────────────
INBOUND_SHIPMENTS = [
    {
        "shipment_id": "FBA16ABC123",
        "msku": "SKU-BT001-BLK",
        "asin": "B09XYZ0001",
        "qty": 200,
        "status": "IN_TRANSIT",
        "estimated_arrival": (datetime.now() + timedelta(days=5)).strftime("%Y-%m-%d"),
        "warehouse": "ONT8",
    },
    {
        "shipment_id": "FBA16DEF456",
        "msku": "SKU-CHG001",
        "asin": "B07DEF5678",
        "qty": 500,
        "status": "CHECKED_IN",
        "estimated_arrival": (datetime.now() + timedelta(days=2)).strftime("%Y-%m-%d"),
        "warehouse": "ONT8",
    },
    {
        "shipment_id": "FBA16GHI789",
        "msku": "SKU-LMP001",
        "asin": "B05GHI9012",
        "qty": 100,
        "status": "WORKING",
        "estimated_arrival": (datetime.now() + timedelta(days=8)).strftime("%Y-%m-%d"),
        "warehouse": "ONT8",
    },
]

# ──────────────────────────────────────────────
# 广告数据
# ──────────────────────────────────────────────
AD_CAMPAIGNS = [
    {
        "campaign_id": "SP-AUTO-BT",
        "campaign_name": "SP-Auto-Earbuds",
        "type": "SP",
        "targeting": "auto",
        "budget": 50.00,
        "bid": 0.45,
        "status": "active",
        "asin_target": "B09XYZ0001",
    },
    {
        "campaign_id": "SP-MAN-BT-KW",
        "campaign_name": "SP-Manual-Earbuds-KW",
        "type": "SP",
        "targeting": "manual",
        "budget": 80.00,
        "bid": 0.55,
        "status": "active",
        "asin_target": "B09XYZ0001",
    },
    {
        "campaign_id": "SP-AUTO-CHG",
        "campaign_name": "SP-Auto-Charger",
        "type": "SP",
        "targeting": "auto",
        "budget": 40.00,
        "bid": 0.35,
        "status": "active",
        "asin_target": "B07DEF5678",
    },
    {
        "campaign_id": "SP-AUTO-SPK",
        "campaign_name": "SP-Auto-Speaker",
        "type": "SP",
        "targeting": "auto",
        "budget": 60.00,
        "bid": 0.50,
        "status": "active",
        "asin_target": "B08ABC1234",
    },
]

AD_PERFORMANCE_TODAY = [
    {
        "campaign_id": "SP-AUTO-BT",
        "impressions": 4520,
        "clicks": 156,
        "spend": 45.30,
        "sales": 269.91,       # 6笔订单
        "orders": 6,
        "acos": 16.78,          # ✅ 健康
        "cpc": 0.29,
        "ctr": 3.45,
        "roas": 5.96,
    },
    {
        "campaign_id": "SP-MAN-BT-KW",
        "impressions": 3250,
        "clicks": 98,
        "spend": 53.90,
        "sales": 149.95,        # 5笔订单
        "orders": 5,
        "acos": 35.95,          # 🔴 ACOS 偏高!
        "cpc": 0.55,
        "ctr": 3.02,
        "roas": 2.78,
    },
    {
        "campaign_id": "SP-AUTO-CHG",
        "impressions": 6800,
        "clicks": 245,
        "spend": 39.80,         # ⚠️ 预算即将耗尽
        "sales": 249.90,
        "orders": 10,
        "acos": 15.93,
        "cpc": 0.16,
        "ctr": 3.60,
        "roas": 6.28,
    },
    {
        "campaign_id": "SP-AUTO-SPK",
        "impressions": 2100,
        "clicks": 45,
        "spend": 22.50,
        "sales": 79.98,
        "orders": 2,
        "acos": 28.13,
        "cpc": 0.50,
        "ctr": 2.14,
        "roas": 3.55,
    },
]

AD_PERFORMANCE_14D_AVG = [
    {"campaign_id": "SP-AUTO-BT",   "avg_acos": 18.2, "avg_cpc": 0.32, "avg_ctr": 3.2, "avg_roas": 5.5},
    {"campaign_id": "SP-MAN-BT-KW",  "avg_acos": 24.5, "avg_cpc": 0.48, "avg_ctr": 3.1, "avg_roas": 4.1},
    {"campaign_id": "SP-AUTO-CHG",   "avg_acos": 14.8, "avg_cpc": 0.18, "avg_ctr": 3.8, "avg_roas": 6.8},
    {"campaign_id": "SP-AUTO-SPK",   "avg_acos": 25.0, "avg_cpc": 0.47, "avg_ctr": 2.5, "avg_roas": 4.0},
]

# ──────────────────────────────────────────────
# 利润数据
# ──────────────────────────────────────────────
PROFIT_DATA = [
    {
        "msku": "SKU-BT001-BLK",
        "asin": "B09XYZ0001",
        "date": YESTERDAY,
        "sales_qty": 11,
        "revenue": 329.89,
        "refund_qty": 0,
        "refund_amount": 0.0,
        "refund_rate": 0.0,
        "ad_spend": 45.30,
        "ad_ratio": 13.7,
        "fba_fees": 55.00,
        "referral_fee": 49.48,
        "cogs": 137.50,
        "gross_profit": 42.61,
        "gross_margin": 12.9,  # ⚠️ 利润偏低
        "net_profit": 42.61,
    },
    {
        "msku": "SKU-CHG001",
        "asin": "B07DEF5678",
        "date": YESTERDAY,
        "sales_qty": 20,
        "revenue": 499.80,
        "refund_qty": 1,
        "refund_amount": 24.99,
        "refund_rate": 5.0,
        "ad_spend": 39.80,
        "ad_ratio": 8.0,
        "fba_fees": 60.00,
        "referral_fee": 74.97,
        "cogs": 196.00,
        "gross_profit": 128.04,
        "gross_margin": 25.6,  # ✅ 正常
        "net_profit": 128.04,
    },
    {
        "msku": "SKU-SPK001",
        "asin": "B08ABC1234",
        "date": YESTERDAY,
        "sales_qty": 3,
        "revenue": 119.97,
        "refund_qty": 1,
        "refund_amount": 39.99,
        "refund_rate": 33.3,   # 🔴 退款率极高!
        "ad_spend": 22.50,
        "ad_ratio": 18.8,
        "fba_fees": 18.00,
        "referral_fee": 18.00,
        "cogs": 54.00,
        "gross_profit": -11.53,
        "gross_margin": -9.6,  # 🔴 严重亏损!
        "net_profit": -11.53,
    },
    {
        "msku": "SKU-BT001-WHT",
        "asin": "B09XYZ0002",
        "date": YESTERDAY,
        "sales_qty": 9,
        "revenue": 269.91,
        "refund_qty": 0,
        "refund_amount": 0.0,
        "refund_rate": 0.0,
        "ad_spend": 53.90,
        "ad_ratio": 20.0,
        "fba_fees": 45.00,
        "referral_fee": 40.49,
        "cogs": 112.50,
        "gross_profit": 18.02,
        "gross_margin": 6.7,   # 🔴 极低利润率!
        "net_profit": 18.02,
    },
]

# ──────────────────────────────────────────────
# 竞品/跟卖数据
# ──────────────────────────────────────────────
COMPETITOR_DATA = [
    {
        "asin": "B09XYZ0001",
        "buy_box_owner": "self",
        "buy_box_price": 29.99,
        "seller_count": 3,
        "sellers": [
            {"name": "SoundPro Official", "price": 29.99, "is_self": True, "rating": 4.8, "fulfillment": "FBA"},
            {"name": "DealMax", "price": 27.99, "is_self": False, "rating": 4.2, "fulfillment": "FBM"},
            {"name": "ValueShop", "price": 26.50, "is_self": False, "rating": 3.9, "fulfillment": "FBM"},
        ],
        "bsr": 1240,
        "bsr_change_7d": +85,
    },
    {
        "asin": "B07DEF5678",
        "buy_box_owner": "self",
        "buy_box_price": 24.99,
        "seller_count": 5,  # ⚠️ 卖家较多
        "sellers": [
            {"name": "PowerUp Official", "price": 24.99, "is_self": True, "rating": 4.9, "fulfillment": "FBA"},
            {"name": "QuickCharge", "price": 22.99, "is_self": False, "rating": 4.5, "fulfillment": "FBA"},
            {"name": "GadgetKing", "price": 21.49, "is_self": False, "rating": 4.0, "fulfillment": "FBM"},
            {"name": "ElectroDeals", "price": 19.99, "is_self": False, "rating": 3.5, "fulfillment": "FBM"},
            {"name": "NewSeller_X", "price": 18.50, "is_self": False, "rating": 2.1, "fulfillment": "FBM"},  # 🆕 可疑新卖家!
        ],
        "bsr": 320,
        "bsr_change_7d": -45,  # BSR 上升（变差）
    },
    {
        "asin": "B08ABC1234",
        "buy_box_owner": "FastShip",  # 🔴 Buy Box 丢失!
        "buy_box_price": 36.99,
        "seller_count": 4,
        "sellers": [
            {"name": "FastShip", "price": 36.99, "is_self": False, "rating": 4.6, "fulfillment": "FBA"},
            {"name": "SoundPro Official", "price": 39.99, "is_self": True, "rating": 4.8, "fulfillment": "FBA"},
            {"name": "AudioMart", "price": 38.50, "is_self": False, "rating": 4.3, "fulfillment": "FBA"},
            {"name": "BudgetAudio", "price": 34.99, "is_self": False, "rating": 3.8, "fulfillment": "FBM"},
        ],
        "bsr": 8900,
        "bsr_change_7d": +1200,  # 🔴 BSR 大幅下滑
    },
]

# ──────────────────────────────────────────────
# 运营日报汇总
# ──────────────────────────────────────────────
DAILY_SUMMARY = {
    "date": YESTERDAY,
    "total_sales": 1219.57,
    "total_sales_change_pct": 8.3,
    "total_orders": 45,
    "total_units": 52,
    "avg_order_value": 27.10,
    "gross_profit": 177.14,
    "gross_margin": 14.5,
    "total_ad_spend": 161.50,
    "total_ad_sales": 749.74,
    "overall_acos": 21.5,
    "refund_rate": 3.8,
    "buy_box_ownership": 0.75,
    "inventory_health": {
        "ok": 4,
        "warning": 2,
        "critical": 2,
    },
}
