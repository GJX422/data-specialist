# 📊 数据专员 (Data Specialist)

云之家/金蝶数据同步智能策略 - 工作日报/周报/月报数据源

## 📋 项目简介

本项目是一套完整的数据同步和报表生成系统，用于自动化处理云之家和金蝶系统的数据，生成工作日报、周报、月报等业务报表。

### 核心特性

- 🔄 **智能同步策略**：状态类表采用"近30天新建 + 所有审批中/待提交记录"的智能同步
- 📈 **多维度报表**：产供销存日报/周报/月报、工作日报综合分析、数据健康看板
- ⏰ **定时任务**：每日4轮自动同步，定时生成并推送报表
- 🔒 **安全设计**：MySQL读写权限分离，凭证加密存储

## 🗂️ 目录结构

```
data-specialist/
├── sync-scripts/                    # 同步脚本
│   ├── core/                       # 核心同步脚本（9个状态类表）
│   │   ├── yunzhijia_sync_expense_reimbursement_mysql.py    # 费用报销
│   │   ├── yunzhijia_sync_payment_request_mysql.py          # 用款申请
│   │   ├── yunzhijia_sync_payment_application_mysql.py      # 付款申请（爱尔康）
│   │   ├── yunzhijia_sync_payment_application_aierfa_mysql.py # 付款申请（爱尔发）
│   │   ├── yunzhijia_sync_business_expense_mysql.py         # 出差费用报销
│   │   ├── yunzhijia_sync_union_expense_reimbursement_mysql.py # 工会费用报销
│   │   ├── yunzhijia_sync_purchase_payment_mysql.py         # 采购用款申请
│   │   ├── yunzhijia_sync_daily_report_mysql.py             # 工作日报
│   │   └── yunzhijia_sync_leave_mysql.py                    # 请假记录
│   ├── orchestrator/               # 编排器
│   │   └── yunzhijia_sync_all_mysql.py                      # 主编排器（两趟查询）
│   └── production/                 # 产线同步脚本
│       ├── yunzhijia_sync_fresh_product_mysql.py            # 鲜品采收
│       ├── yunzhijia_sync_aiercon_production_mysql.py       # 爱尔康生产
│       ├── yunzhijia_sync_spray_drying_summary_mysql.py     # 喷雾干燥
│       ├── yunzhijia_sync_drying_powder_output_mysql.py     # 闪蒸干燥粉
│       └── yunzhijia_sync_flash_drying_powder_mysql.py      # 成品破壁粉
├── report-scripts/                 # 报表生成脚本
│   ├── gen_daily_report.py         # 产供销存日报
│   ├── gen_health_dashboard.py     # 数据健康看板
│   └── gen_gm_cockpit.py           # 驾驶舱
├── config/                         # 配置文件
│   └── config.example.json        # 配置示例
├── docs/                           # 文档
│   ├── ARCHITECTURE.md            # 架构设计
│   ├── SYNC_STRATEGY.md           # 同步策略详解
│   └── API_REFERENCE.md           # API参考
├── requirements.txt                # Python依赖
└── README.md                       # 本文件
```

## 🚀 快速开始

### 环境要求

- Python 3.8+
- MySQL 5.7+
- 云之家/金蝶API访问权限

### 安装依赖

```bash
# 克隆仓库
git clone https://github.com/GJX422/data-specialist.git
cd data-specialist

# 安装依赖
pip install -r requirements.txt
```

### 配置

1. 复制配置示例文件：

```bash
cp config/config.example.json config/config.json
```

2. 编辑 `config/config.json`，填写以下信息：

```json
{
  "mysql": {
    "host": "183.224.204.51",
    "port": 53306,
    "user": "yunzhijia_rw",
    "password": "your_password",
    "database": "yunzhijia"
  },
  "yunzhijia": {
    "app_id": "501014689",
    "secret": "your_secret"
  },
  "kingdee": {
    "app_id": "your_app_id",
    "app_secret": "your_app_secret"
  }
}
```

3. 配置云之家Cookie（首次需要登录获取）：

```bash
python3 scripts/yunzhijia_auto_login_http.py
```

## 📊 核心功能

### 1. 智能同步策略

本项目的核心创新是**智能同步策略**，解决了传统"近N天"同步方式的遗漏问题。

#### 问题背景

传统的 `--days N` 同步方式只获取最近N天新建的记录，但会遗漏：
- 审批中的老记录（可能持续数周）
- 待提交的草稿记录

#### 解决方案

对状态类表采用**两趟查询**策略：

**第1趟**：获取近30天新建记录
```bash
python3 yunzhijia_sync_all_mysql.py --start 2026-05-28 --end 2026-06-27
```

**第2趟**：获取所有审批中/待提交记录
```bash
python3 yunzhijia_sync_expense_reimbursement_mysql.py --status RUNNING,RETURNED
```

#### 状态值映射

| 状态 | rawValue | 说明 |
|------|----------|------|
| 审批中 | `RUNNING` | 正在审批流程中 |
| 已完成 | `FINISH` | 审批通过并完成 |
| 待提交 | `RETURNED` | 被退回，待重新提交 |
| 已废弃 | `ABANDON` | 已取消或废弃 |

### 2. 产线同步

7条产线均有独立的全量同步cron任务，每天执行4轮：

| 产线 | 脚本 | 说明 |
|------|------|------|
| 鲜品采收 | `yunzhijia_sync_fresh_product_mysql.py` | 明细表（421条） |
| 爱尔康生产 | `yunzhijia_sync_aiercon_production_mysql.py` | 生产明细表 |
| 喷雾干燥 | `yunzhijia_sync_spray_drying_summary_mysql.py` | 生产明细表 |
| 闪蒸干燥粉 | `yunzhijia_sync_drying_powder_output_mysql.py` | 产出明细 |
| 成品破壁粉 | `yunzhijia_sync_flash_drying_powder_mysql.py` | 产出明细 |

**重要**：生产记录常为补录，`制单日期` ≠ `生产日期`。查询生产产出必须用`生产日期`。

### 3. 报表生成

#### 产供销存日报 (`gen_daily_report.py`)

每日自动生成，包含：
- 生产产出（7条产线）
- 销售订单
- 采购入库
- 库存状态
- 决策建议

#### 数据健康看板 (`gen_health_dashboard.py`)

实时监控数据源健康状态：
- 🟢 绿灯：数据正常
- 🔴 红灯：数据异常/缺失
- 🟡 黄灯：数据待确认

部署地址：https://www.htmlcode.fun/s/data-health-board

#### 驾驶舱 (`gen_gm_cockpit.py`)

管理层驾驶舱，5个Tab页，展示关键业务指标。

### 4. 定时任务

所有定时任务通过Hermes Agent的cron系统管理：

| 任务 | 频率 | 说明 |
|------|------|------|
| 数据同步 | 每日4轮 (02:30/09:00/13:00/18:00) | 云之家→金蝶→产线 |
| 产线全量同步 | 每日4轮 | 7条产线独立同步 |
| 产供销存日报 | 每日 05:00 | 生成并推送IMA |
| 工作日报分析 | 每日 05:30 | LLM分析7大维度 |
| 数据健康看板 | 每日 04:00 | 更新看板数据 |

## 🔧 使用指南

### 手动同步

```bash
# 同步所有状态类表（智能两趟查询）
python3 sync-scripts/orchestrator/yunzhijia_sync_all_mysql.py --days 30

# 同步单个表（指定日期范围）
python3 sync-scripts/core/yunzhijia_sync_expense_reimbursement_mysql.py \
  --start 2026-06-01 --end 2026-06-30

# 同步审批中记录
python3 sync-scripts/core/yunzhijia_sync_expense_reimbursement_mysql.py \
  --status RUNNING,RETURNED

# 同步产线数据（全量）
python3 sync-scripts/production/yunzhijia_sync_fresh_product_mysql.py --all
```

### 生成报表

```bash
# 生成产供销存日报
python3 report-scripts/gen_daily_report.py

# 生成数据健康看板
python3 report-scripts/gen_health_dashboard.py

# 生成驾驶舱
python3 report-scripts/gen_gm_cockpit.py
```

## 📝 文档

详细文档请参阅 [docs/](docs/) 目录：

- [架构设计](docs/ARCHITECTURE.md) - 系统架构和数据流
- [同步策略详解](docs/SYNC_STRATEGY.md) - 智能同步策略的技术细节
- [API参考](docs/API_REFERENCE.md) - 云之家/金蝶API使用说明

## 🔒 安全注意事项

1. **凭证安全**：不要将 `config/config.json` 提交到Git
2. **数据库权限**：
   - `finebi_ro`：只读用户，用于FineBI
   - `yunzhijia_rw`：读写用户，用于同步脚本
3. **Cookie管理**：云之家Cookie有效期约24小时，需定期刷新

## 📄 许可证

本项目采用 MIT 许可证

## 📞 联系方式

- 项目链接：https://github.com/GJX422/data-specialist
- Issues：https://github.com/GJX422/data-specialist/issues
