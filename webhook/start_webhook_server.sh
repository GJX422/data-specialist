#!/bin/bash
# 云之家Webhook服务启动脚本

# 设置工作目录
cd /root/.hermes/scripts

# 检查是否已运行
if pgrep -f "yunzhijia_webhook_server.py" > /dev/null; then
    echo "⚠️ Webhook服务已在运行"
    exit 1
fi

# 启动服务（后台运行）
nohup python3 yunzhijia_webhook_server.py > /root/.hermes/logs/webhook.log 2>&1 &

# 获取PID
PID=$!
echo "✅ Webhook服务已启动，PID: $PID"
echo "📝 日志文件: /root/.hermes/logs/webhook.log"
echo "🔗 健康检查: http://localhost:5000/health"
