#!/usr/bin/env python3
"""
云之家请假数据同步脚本
功能：同步请假数据到 MySQL 数据库
"""

import json
import urllib.request
from datetime import datetime, timezone, timedelta
import mysql.connector


def parse_timestamp(value):
    """解析时间戳字段"""
    if not value:
        return None
    # 如果是时间戳（毫秒），转换为日期时间
    try:
        ts = int(value)
        if ts > 1000000000000:  # 毫秒时间戳
            cst = timezone(timedelta(hours=8))
            dt = datetime.fromtimestamp(ts / 1000, tz=cst)
            return dt.strftime('%Y-%m-%d %H:%M:%S')
        return value
    except:
        return value


def clean_value(col):
    """清理字段值"""
    if not col:
        return ''
    return col.get('value', '')


# ============ 配置 ============
from pathlib import Path

SECRETS_FILE = Path.home() / ".hermes" / "secrets" / "yunzhijia.json"
API_BASE = "https://www.yunzhijia.com"

# MySQL 配置
MYSQL_CONFIG = {
    'host': '127.0.0.1',
    'port': 53306,
    'user': 'tencentbi',
    'password': 'Alphy@2026!FineBI_Mysql',
    'database': 'yunzhijia'
}

# 请假表单配置
LEAVE_FORM = {
    'formCodeId': 'b3f2a8abf343459d945dad1f28a82380',
    'viewId': '6a014d5fafd20e2f6b41c9ad'
}

# MySQL 表结构
CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS `云之家_请假` (
    `序号` INT AUTO_INCREMENT PRIMARY KEY,
    `流水号` VARCHAR(50) UNIQUE,
    `标题` VARCHAR(500),
    `申请人` VARCHAR(50),
    `所属部门` VARCHAR(100),
    `请假类型` VARCHAR(50),
    `开始时间` DATETIME,
    `结束时间` DATETIME,
    `请假天数` DECIMAL(5,2),
    `请假时长` DECIMAL(5,2),
    `请假事由` TEXT,
    `流程状态` VARCHAR(20),
    `云之家ID` VARCHAR(100),
    `同步时间` DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX `idx_申请人` (`申请人`),
    INDEX `idx_所属部门` (`所属部门`),
    INDEX `idx_开始时间` (`开始时间`),
    INDEX `idx_流程状态` (`流程状态`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
"""

# 列名列表
COLUMNS = ['流水号', '标题', '申请人', '所属部门', '请假类型', '开始时间', '结束时间', '请假天数', '请假时长', '请假事由', '流程状态', '云之家ID']


def load_secrets():
    """加载密钥配置"""
    with open(SECRETS_FILE) as f:
        return json.load(f)


def init_database():
    """初始化数据库表"""
    conn = mysql.connector.connect(**MYSQL_CONFIG)
    cursor = conn.cursor()
    cursor.execute(CREATE_TABLE_SQL)
    conn.commit()
    cursor.close()
    conn.close()
    print("✅ 请假表已创建/已存在")


def fetch_leave_records(cookie, days=30):
    """从云之家API获取请假记录"""
    cst = timezone(timedelta(hours=8))
    today = datetime.now(cst)
    start_dt = today - timedelta(days=days)
    end_dt = today.replace(hour=23, minute=59, second=59)
    start_ts = int(start_dt.timestamp() * 1000)
    end_ts = int(end_dt.timestamp() * 1000)

    headers = {
        'Content-Type': 'application/json;charset=UTF-8',
        'x-requested-bizid': 'light-cloud',
        'x-yzj-lang': 'zh-CN',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Cookie': cookie
    }

    data = {
        'pageSize': 100,
        'formCodeId': LEAVE_FORM['formCodeId'],
        'pageNumber': 1,
        'searchItems': [],
        'resultItems': [
            {'sum': False, 'title': '流水号', 'type': 'serialNumWidget', 'codeId': '_S_SERIAL', 'details': [], 'parentCodeId': None},
            {'sum': False, 'title': '标题', 'type': 'textWidget', 'codeId': '_S_TITLE', 'details': [], 'parentCodeId': None},
            {'sum': False, 'title': '申请人', 'type': 'personSelectWidget', 'codeId': '_S_APPLY', 'details': [], 'parentCodeId': None},
            {'sum': False, 'title': '所属部门', 'type': 'departmentSelectWidget', 'codeId': '_S_DEPT', 'details': [], 'parentCodeId': None},
            {'sum': False, 'title': '申请日期', 'type': 'dateWidget', 'codeId': '_S_DATE', 'details': [], 'parentCodeId': None},
            {'sum': False, 'title': '请假人', 'type': 'personSelectWidget', 'codeId': '_S_INT_LEAVE_APPLIER', 'details': [], 'parentCodeId': ''},
            {
                'sum': False,
                'title': '请假信息',
                'type': 'detailedWidget',
                'codeId': '_S_INT_LEAVE_DETAILED',
                'details': [
                    {'sum': True, 'title': '请假总天数', 'type': 'numberWidget', 'codeId': '_S_INT_LEAVE_DAYS', 'details': None, 'parentCodeId': '_S_INT_LEAVE_DETAILED'},
                    {'sum': True, 'title': '请假总时长', 'type': 'numberWidget', 'codeId': '_S_INT_LEAVE_HOURS', 'details': None, 'parentCodeId': '_S_INT_LEAVE_DETAILED'},
                    {'sum': False, 'title': '请假类型', 'type': 'radioWidget', 'codeId': '_S_INT_LEAVE_TYPE', 'details': None, 'parentCodeId': '_S_INT_LEAVE_DETAILED'},
                    {'sum': False, 'title': '开始时间-结束时间', 'type': 'dateRangeWidget', 'codeId': '_S_INT_LEAVE_TIME', 'details': None, 'parentCodeId': '_S_INT_LEAVE_DETAILED'},
                ],
                'parentCodeId': ''
            },
            {'sum': False, 'title': '请假事由', 'type': 'textAreaWidget', 'codeId': '_S_INT_LEAVE_REASON', 'details': [], 'parentCodeId': ''},
            {'sum': False, 'title': '流程状态', 'type': 'radioWidget', 'codeId': '_S_STATUS', 'details': [], 'parentCodeId': ''},
        ],
        'sorts': [{'codeId': '_S_DATE', 'sortType': 'desc'}],
        'terminalType': 1,
        'groupIds': [],
        'viewId': LEAVE_FORM['viewId'],
        'language': 'zh-CN'
    }

    req = urllib.request.Request(
        f"{API_BASE}/api/lightcloud/datalist/instance/search2Gen",
        data=json.dumps(data).encode('utf-8'),
        headers=headers
    )

    records = []
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read().decode('utf-8'))
            if result.get('success') and result.get('data') and result['data'].get('dataList'):
                for item in result['data']['dataList']:
                    cols = {c['codeId']: c for c in item['colList']}
                    
                    # 解析子表数据
                    detailed = cols.get('_S_INT_LEAVE_DETAILED', {})
                    details = detailed.get('details', []) if isinstance(detailed, dict) else []
                    detail_map = {d['codeId']: d for d in details}
                    
                    # 解析时间范围
                    leave_time_raw = detail_map.get('_S_INT_LEAVE_TIME', {}).get('rawValue', '')
                    start_time = ''
                    end_time = ''
                    if leave_time_raw and isinstance(leave_time_raw, list) and len(leave_time_raw) > 0:
                        time_range = leave_time_raw[0]
                        if isinstance(time_range, list) and len(time_range) >= 2:
                            start_ts = time_range[0]
                            end_ts = time_range[1]
                            start_time = parse_timestamp(start_ts)
                            end_time = parse_timestamp(end_ts)
                    
                    # 解析请假类型（可能是JSON数组格式）
                    leave_type = clean_value(detail_map.get('_S_INT_LEAVE_TYPE'))
                    if leave_type.startswith('["') and leave_type.endswith('"]'):
                        leave_type = leave_type[2:-2]
                    
                    record = {
                        '流水号': clean_value(cols.get('_S_SERIAL')),
                        '标题': clean_value(cols.get('_S_TITLE')),
                        '申请人': clean_value(cols.get('_S_APPLY')),
                        '所属部门': clean_value(cols.get('_S_DEPT')),
                        '请假类型': leave_type,
                        '开始时间': start_time,
                        '结束时间': end_time,
                        '请假天数': detail_map.get('_S_INT_LEAVE_DAYS', {}).get('value', ''),
                        '请假时长': detail_map.get('_S_INT_LEAVE_HOURS', {}).get('value', ''),
                        '请假事由': clean_value(cols.get('_S_INT_LEAVE_REASON')),
                        '流程状态': clean_value(cols.get('_S_STATUS')),
                        '云之家ID': item.get('formInstId', '')
                    }
                    records.append(record)
    except Exception as e:
        print(f"❌ 获取请假数据失败: {e}")
    
    return records


def sync_to_mysql(records):
    """同步请假数据到MySQL（已有则更新）"""
    if not records:
        print("⚠️ 没有请假数据需要同步")
        return 0

    conn = mysql.connector.connect(**MYSQL_CONFIG)
    cursor = conn.cursor()

    inserted = 0
    updated = 0
    for record in records:
        # 检查是否已存在
        cursor.execute("SELECT 序号 FROM `云之家_请假` WHERE 流水号 = %s", (record['流水号'],))
        exists = cursor.fetchone()

        values = (
            record['流水号'], record['标题'], record['申请人'], record['所属部门'],
            record['请假类型'], record['开始时间'], record['结束时间'],
            record.get('请假天数', '') or None, record.get('请假时长', '') or None,
            record['请假事由'], record['流程状态'], record['云之家ID']
        )

        try:
            if exists:
                # 已存在：用新数据更新（解决首次同步数据不全的问题）
                cursor.execute(f"""
                    UPDATE `云之家_请假`
                    SET `标题`=%s, `申请人`=%s, `所属部门`=%s, `请假类型`=%s,
                        `开始时间`=%s, `结束时间`=%s, `请假天数`=%s, `请假时长`=%s,
                        `请假事由`=%s, `流程状态`=%s, `云之家ID`=%s
                    WHERE `流水号`=%s
                """, (record['标题'], record['申请人'], record['所属部门'],
                      record['请假类型'], record['开始时间'], record['结束时间'],
                      record.get('请假天数', '') or None, record.get('请假时长', '') or None,
                      record['请假事由'], record['流程状态'], record['云之家ID'],
                      record['流水号']))
                updated += 1
            else:
                # 新记录：插入
                cursor.execute(f"""
                    INSERT INTO `云之家_请假` ({', '.join(COLUMNS)})
                    VALUES ({', '.join(['%s'] * len(COLUMNS))})
                """, values)
                inserted += 1
        except Exception as e:
            print(f"❌ 同步失败: {record['流水号']} - {e}")

    conn.commit()
    cursor.close()
    conn.close()
    return inserted, updated


def main(days=30):
    print(f"=== 同步请假数据 (最近 {days} 天) ===")
    
    # 加载Cookie
    secrets = load_secrets()
    cookie = secrets.get('yunzhijia', {}).get('cookie', '')
    if not cookie:
        print("❌ 未找到Cookie，请先运行登录脚本")
        return

    # 初始化数据库
    init_database()

    # 获取请假数据
    print("📥 正在从云之家获取请假数据...")
    records = fetch_leave_records(cookie, days)
    print(f"   获取到 {len(records)} 条请假记录")

    # 同步到MySQL
    print("💾 正在同步到MySQL...")
    inserted, updated = sync_to_mysql(records)
    print(f"✅ 同步完成，新增 {inserted} 条，更新 {updated} 条")


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='同步请假数据到MySQL')
    parser.add_argument('--days', type=int, default=30, help='同步最近N天的数据 (默认30天)')
    args = parser.parse_args()
    main(args.days)
