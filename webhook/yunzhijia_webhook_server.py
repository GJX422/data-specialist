#!/usr/bin/env python3
"""
云之家 Webhook 接收服务
功能：接收云之家审批状态变更通知，触发对应的同步脚本
"""

from flask import Flask, request, jsonify
import subprocess
import json
import logging
from datetime import datetime

app = Flask(__name__)

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/root/.hermes/logs/webhook.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# 表单FORM_CODE_ID → 同步脚本映射
FORM_SCRIPT_MAP = {
    "dfaa95cb7d634cccb72a855573ad24dc": "yunzhijia_sync_expense_reimbursement_mysql.py",
    "56f7068ebbcd46e4b9a6fbc07db0ab5b": "yunzhijia_sync_payment_request_mysql.py",
    "3ed2af9eaf7d4c8cb6f08346e38044c2": "yunzhijia_sync_payment_application_mysql.py",
    "00bf561f68c2406ebed5f1ed77c3a74e": "yunzhijia_sync_payment_application_aierfa_mysql.py",
    "cc0a9b200cce442b8b16eb16bbaf3ffa": "yunzhijia_sync_business_expense_mysql.py",
    "7013d3cb6c5b465480e229d35ee61c3b": "yunzhijia_sync_union_expense_reimbursement_mysql.py",
    "5723a33ec31f4521bfa22cbfc9e0f178": "yunzhijia_sync_purchase_payment_mysql.py",
    "c7c1f226cabd49658b601363cc4d210a": "yunzhijia_sync_daily_report_mysql.py",
    # 产线表单
    "fdc0dcc16f254a638e74802a1940150a": "yunzhijia_sync_fresh_product_mysql.py",
    "55d3968232f24da08716f1f55b28285c": "yunzhijia_sync_aiercon_production_mysql.py",
    "329fb42d677e43a6b0f4a6bee4422488": "yunzhijia_sync_spray_drying_summary_mysql.py",
    "303167ed8b1c4ece9c126d3a1dfbe572": "yunzhijia_sync_drying_powder_output_mysql.py",
    "cfda19ec8b904d2baf7d999419a51bb7": "yunzhijia_sync_flash_drying_powder_mysql.py",
}

# 同步脚本目录
SCRIPTS_DIR = "/root/.hermes/scripts"

@app.route('/webhook/yunzhijia', methods=['POST'])
def handle_webhook():
    """处理云之家Webhook回调"""
    try:
        # 获取请求数据
        data = request.get_json(force=True)
        logger.info(f"收到Webhook: {json.dumps(data, ensure_ascii=False)[:500]}")
        
        # 验证签名（如果云之家配置了签名验证）
        # TODO: 添加签名验证逻辑
        
        # 解析事件类型
        event_type = data.get('eventType', '')
        form_code_id = data.get('formCodeId', '')
        instance_id = data.get('instanceId', '')
        status = data.get('status', '')
        
        logger.info(f"事件类型: {event_type}, 表单: {form_code_id}, 实例: {instance_id}, 状态: {status}")
        
        # 根据表单ID找到对应的同步脚本
        script_name = FORM_SCRIPT_MAP.get(form_code_id)
        if not script_name:
            logger.warning(f"未知的表单ID: {form_code_id}")
            return jsonify({"success": True, "message": "Unknown form, ignored"})
        
        # 构建同步命令
        # 对于状态类表单，使用--status参数同步该状态的所有记录
        # 对于产线表单，使用--all参数全量同步
        if form_code_id in ["fdc0dcc16f254a638e74802a1940150a",  # 鲜品
                           "55d3968232f24da08716f1f55b28285c",  # 爱尔康
                           "329fb42d677e43a6b0f4a6bee4422488",  # 喷雾
                           "303167ed8b1c4ece9c126d3a1dfbe572",  # 闪蒸
                           "cfda19ec8b904d2baf7d999419a51bb7"]: # 成品
            # 产线表单：全量同步
            cmd = ["python3", f"{SCRIPTS_DIR}/{script_name}", "--all"]
        else:
            # 状态类表单：同步所有活跃状态
            cmd = ["python3", f"{SCRIPTS_DIR}/{script_name}", "--status", "RUNNING,RETURNED"]
        
        logger.info(f"执行同步命令: {' '.join(cmd)}")
        
        # 执行同步脚本
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=120  # 2分钟超时
        )
        
        if result.returncode == 0:
            logger.info(f"同步成功: {script_name}")
            return jsonify({"success": True, "message": "Sync completed"})
        else:
            logger.error(f"同步失败: {result.stderr[:500]}")
            return jsonify({"success": False, "error": result.stderr[:500]})
            
    except subprocess.TimeoutExpired:
        logger.error(f"同步超时: {script_name}")
        return jsonify({"success": False, "error": "Sync timeout"})
    except Exception as e:
        logger.error(f"处理Webhook异常: {str(e)}")
        return jsonify({"success": False, "error": str(e)})

@app.route('/health', methods=['GET'])
def health_check():
    """健康检查"""
    return jsonify({"status": "healthy", "timestamp": datetime.now().isoformat()})

if __name__ == '__main__':
    # 启动服务
    # 绑定0.0.0.0监听所有接口，端口5000
    app.run(host='0.0.0.0', port=5000, debug=False)
