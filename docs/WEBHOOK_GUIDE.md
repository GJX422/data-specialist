# 🔄 云之家 Webhook 实时同步方案

## 📋 方案概述

本方案通过云之家Webhook实现数据的实时同步，当有新的审批操作或状态变更时，自动触发对应的同步脚本更新MySQL数据库。

### 工作流程

```
用户在云之家提交审批/状态变更
        ↓
云之家发送Webhook通知
        ↓
本地Webhook服务接收通知
        ↓
根据表单ID调用对应同步脚本
        ↓
同步脚本拉取最新数据并更新MySQL
        ↓
数据实时更新完成
```

## 🚀 实施步骤

### 第一步：部署Webhook服务

#### 1. 上传脚本到服务器

```bash
# 复制webhook服务脚本
cp yunzhijia_webhook_server.py /root/.hermes/scripts/
cp start_webhook_server.sh /root/.hermes/scripts/

# 设置执行权限
chmod +x /root/.hermes/scripts/start_webhook_server.sh
```

#### 2. 安装依赖

```bash
pip install flask
```

#### 3. 启动服务

```bash
# 启动webhook服务
/root/.hermes/scripts/start_webhook_server.sh

# 验证服务运行
curl http://localhost:5000/health
```

### 第二步：配置云之家Webhook

#### 1. 登录云之家开放平台

访问：https://open.yunzhijia.com

#### 2. 进入应用配置

- 选择你的应用
- 点击「事件订阅」或「Webhook配置」

#### 3. 配置回调URL

```
回调URL: http://你的服务器IP:5000/webhook/yunzhijia
```

**注意**：
- 服务器必须有公网IP或使用内网穿透工具（如ngrok）
- 建议使用HTTPS（可配置Nginx反向代理）

#### 4. 选择订阅事件

勾选以下事件：
- ✅ 审批实例创建
- ✅ 审批实例状态变更
- ✅ 审批实例完成

#### 5. 配置签名验证（可选但推荐）

云之家会提供一个签名密钥，用于验证Webhook请求的真实性。

### 第三步：内网穿透（如果没有公网IP）

如果服务器没有公网IP，可以使用ngrok进行内网穿透：

```bash
# 安装ngrok
sudo apt install ngrok

# 启动ngrok
ngrok http 5000
```

ngrok会提供一个公网URL，如：`https://abc123.ngrok.io`

将这个URL配置到云之家Webhook回调地址：`https://abc123.ngrok.io/webhook/yunzhijia`

## 📊 支持的表单类型

### 状态类表单（使用 --status 参数）

| 表单ID | 名称 | 同步策略 |
|--------|------|----------|
| dfaa95cb7d634cccb72a855573ad24dc | 费用报销 | RUNNING,RETURNED |
| 56f7068ebbcd46e4b9a6fbc07db0ab5b | 用款申请 | RUNNING,RETURNED |
| 3ed2af9eaf7d4c8cb6f08346e38044c2 | 付款申请（爱尔康） | RUNNING,RETURNED |
| 00bf561f68c2406ebed5f1ed77c3a74e | 付款申请（爱尔发） | RUNNING,RETURNED |
| cc0a9b200cce442b8b16eb16bbaf3ffa | 出差费用报销 | RUNNING,RETURNED |
| 7013d3cb6c5b465480e229d35ee61c3b | 工会费用报销 | RUNNING,RETURNED |
| 5723a33ec31f4521bfa22cbfc9e0f178 | 采购用款申请 | RUNNING,RETURNED |
| c7c1f226cabd49658b601363cc4d210a | 工作日报 | RUNNING,RETURNED |

### 产线表单（使用 --all 参数）

| 表单ID | 名称 | 同步策略 |
|--------|------|----------|
| fdc0dcc16f254a638e74802a1940150a | 鲜品采收 | 全量同步 |
| 55d3968232f24da08716f1f55b28285c | 爱尔康生产 | 全量同步 |
| 329fb42d677e43a6b0f4a6bee4422488 | 喷雾干燥 | 全量同步 |
| 303167ed8b1c4ece9c126d3a1dfbe572 | 闪蒸干燥粉 | 全量同步 |
| cfda19ec8b904d2baf7d999419a51bb7 | 成品破壁粉 | 全量同步 |

## 🔧 配置说明

### Webhook服务配置

编辑 `yunzhijia_webhook_server.py` 中的配置：

```python
# 同步脚本目录
SCRIPTS_DIR = "/root/.hermes/scripts"

# 日志文件
LOG_FILE = "/root/.hermes/logs/webhook.log"
```

### 表单映射配置

在 `FORM_SCRIPT_MAP` 字典中配置表单ID到同步脚本的映射：

```python
FORM_SCRIPT_MAP = {
    "表单ID": "同步脚本名.py",
    # ...
}
```

## 📝 日志查看

```bash
# 查看实时日志
tail -f /root/.hermes/logs/webhook.log

# 查看最近100行
tail -100 /root/.hermes/logs/webhook.log
```

## 🛠️ 故障排查

### 1. Webhook服务无法启动

```bash
# 检查端口是否被占用
netstat -tlnp | grep 5000

# 检查日志
cat /root/.hermes/logs/webhook.log
```

### 2. 收不到Webhook通知

1. 检查云之家Webhook配置是否正确
2. 检查服务器防火墙是否开放5000端口
3. 检查内网穿透工具是否正常运行

### 3. 同步脚本执行失败

```bash
# 手动测试同步脚本
python3 /root/.hermes/scripts/yunzhijia_sync_expense_reimbursement_mysql.py --status RUNNING,RETURNED

# 检查MySQL连接
mysql -h 183.224.204.51 -P 53306 -u yunzhijia_rw -p
```

## 🔒 安全建议

1. **启用签名验证**：在云之家配置Webhook签名密钥
2. **限制IP访问**：在服务器防火墙只允许云之家IP访问
3. **使用HTTPS**：配置Nginx反向代理，启用SSL证书
4. **日志监控**：定期检查日志，发现异常及时处理

## 📈 性能优化

1. **异步处理**：Webhook接收后立即返回，后台异步执行同步
2. **队列机制**：使用Redis/RabbitMQ队列，避免并发冲突
3. **限流控制**：对同步脚本执行频率进行限制

## 🔄 与现有定时任务的配合

Webhook实时同步和定时任务可以并存：

- **Webhook**：处理实时性要求高的审批状态变更
- **定时任务**：每天4轮全量同步，确保数据完整性

建议：
- 保持现有的定时任务作为数据完整性保障
- Webhook作为实时更新的补充

## 📞 技术支持

如有问题，请查看：
- 日志文件：`/root/.hermes/logs/webhook.log`
- 健康检查：`http://localhost:5000/health`
