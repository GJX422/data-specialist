# 数据专员 (Data Specialist)

云之家/金蝶数据同步智能策略 - 工作日报/周报/月报数据源

## 📋 项目简介

本项目包含云之家和金蝶系统的数据同步脚本，用于自动生成工作日报、周报、月报等报表。

## 🗂️ 目录结构

```
├── sync-scripts/           # 同步脚本
│   ├── core/              # 核心同步脚本
│   ├── production/        # 产线同步脚本
│   └── orchestrator/      # 编排器
├── report-scripts/        # 报表生成脚本
├── config/                # 配置文件
└── docs/                  # 文档
```

## 🚀 快速开始

### 环境要求
- Python 3.8+
- MySQL 5.7+
- 云之家/金蝶API访问权限

### 安装依赖
```bash
pip install -r requirements.txt
```

### 配置
1. 复制 `config/config.example.json` 为 `config/config.json`
2. 填写数据库和API凭证

## 📊 核心功能

### 1. 智能同步策略
- **状态类表**：近30天新建 + 所有审批中/待提交记录
- **产线表**：每日4轮全量同步
- **金蝶表**：每日增量同步

### 2. 报表生成
- 产供销存日报/周报/月报
- 工作日报综合分析
- 数据健康看板

### 3. 定时任务
- 每日4轮数据同步
- 自动生成并推送报表到IMA知识库

## 📝 文档

详见 [docs/](docs/) 目录

## 📄 许可证

MIT License
