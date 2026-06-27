#!/usr/bin/env python3
"""
云之家数据同步脚本 - 同步所有业务表到 MySQL
用法：python3 yunzhijia_sync_all_mysql.py --days 1
"""
import sys
import os
sys.path.insert(0, os.path.expanduser('~/.hermes/scripts'))

import json
from pathlib import Path

# 同步所有独立业务表
SYNC_SCRIPTS = [
    "yunzhijia_sync_aiercon_production_mysql.py",
    "yunzhijia_sync_flash_drying_powder_mysql.py",
    "yunzhijia_sync_wall_breaking_powder_mysql.py",
    "yunzhijia_sync_finished_wall_breaking_powder_mysql.py",
    "yunzhijia_sync_fresh_product_mysql.py",
    "yunzhijia_sync_haematococcus_receipt_mysql.py",
    "yunzhijia_sync_spray_drying_summary_mysql.py",
    "yunzhijia_sync_raw_material_sales_mysql.py",
    "yunzhijia_sync_daily_report_mysql.py",
    "yunzhijia_sync_expense_reimbursement_mysql.py",
    "yunzhijia_sync_payment_request_mysql.py",
    "yunzhijia_sync_purchase_payment_mysql.py",
    "yunzhijia_sync_business_expense_mysql.py",
    "yunzhijia_sync_union_expense_reimbursement_mysql.py",
    "yunzhijia_sync_raw_material_inventory_mysql.py",
    "yunzhijia_sync_budget_mysql.py",
    "yunzhijia_sync_budget_changes_mysql.py",
    "yunzhijia_sync_payment_application_mysql.py",
    "yunzhijia_sync_payment_application_aierfa_mysql.py",
]

SCRIPTS_DIR = os.path.expanduser('~/.hermes/scripts')

if __name__ == "__main__":
    import argparse
    import subprocess
    parser = argparse.ArgumentParser(description="云之家数据同步到 MySQL")
    parser.add_argument("--all", action="store_true", help="同步所有数据")
    parser.add_argument("--days", type=int, default=1, help="同步最近 N 天")
    parser.add_argument("--date", type=str, help="同步指定日期 YYYY-MM-DD")
    args = parser.parse_args()
    
    total_ok = 0
    total_fail = 0
    
    for script_name in SYNC_SCRIPTS:
        script_path = os.path.join(SCRIPTS_DIR, script_name)
        if not os.path.exists(script_path):
            print(f"⚠️ 脚本不存在: {script_name}")
            continue
        
        print(f"\n{'='*50}")
        print(f"执行: {script_name}")
        print(f"{'='*50}")
        
        try:
            cmd = ["python3", script_path]
            # 状态类表: 两趟查询(近30天新建 + 所有审批中/待提交)
            STATUS_BASED_SCRIPTS = [
                "yunzhijia_sync_business_expense_mysql.py",
                "yunzhijia_sync_payment_application_mysql.py",
                "yunzhijia_sync_payment_application_aierfa_mysql.py",
                "yunzhijia_sync_expense_reimbursement_mysql.py",
                "yunzhijia_sync_payment_request_mysql.py",
                "yunzhijia_sync_purchase_payment_mysql.py",
                "yunzhijia_sync_union_expense_reimbursement_mysql.py",
                "yunzhijia_sync_daily_report_mysql.py",
                "yunzhijia_sync_material_contract_review_mysql.py",
            ]
            # 这些表不支持--status参数，仍用--all
            ALWAYS_ALL_SCRIPTS = [
                "yunzhijia_sync_raw_material_sales_mysql.py",
                "yunzhijia_sync_raw_material_outbound_mysql.py",
                "yunzhijia_sync_raw_material_invoice_mysql.py",
            ]
            if args.all:
                cmd.append("--all")
            elif script_name in STATUS_BASED_SCRIPTS:
                # 两趟查询: 近30天新建 + 所有审批中/待提交
                from datetime import datetime, timedelta
                # 趟1: 近30天新建的记录
                _end = datetime.now()
                _start = _end - timedelta(days=30)
                cmd.extend(["--start", _start.strftime("%Y-%m-%d"), "--end", _end.strftime("%Y-%m-%d")])
                print(f"  趋1: 近30天新建 ({_start.strftime('%Y-%m-%d')} ~ {_end.strftime('%Y-%m-%d')})")
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
                if result.returncode == 0:
                    print(f"  ✅ 趋1完成")
                else:
                    print(f"  ❌ 趟1失败: {result.stderr[:200] if result.stderr else ''}")
                # 趟2: 所有审批中/待提交记录
                cmd2 = ["python3", script_path, "--status", "RUNNING,RETURNED"]
                print(f"  趋2: 所有审批中/待提交记录")
                result2 = subprocess.run(cmd2, capture_output=True, text=True, timeout=300)
                if result2.returncode == 0:
                    print(f"  ✅ 趋2完成")
                else:
                    print(f"  ❌ 趋2失败: {result2.stderr[:200] if result2.stderr else ''}")
                # 跳过后面的统一执行
                continue
            elif script_name in ALWAYS_ALL_SCRIPTS:
                cmd.append("--all")
            elif args.date:
                cmd.extend(["--date", args.date])
            elif args.days:
                # 子脚本不支持 --days，转换为 --start --end
                from datetime import datetime, timedelta
                _end = datetime.now()
                _start = _end - timedelta(days=args.days)
                cmd.extend(["--start", _start.strftime("%Y-%m-%d"), "--end", _end.strftime("%Y-%m-%d")])
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            if result.returncode == 0:
                print(f"✅ {script_name} 完成")
                total_ok += 1
            else:
                print(f"❌ {script_name} 失败 (exit={result.returncode})")
                print(result.stderr[:500] if result.stderr else "(无错误输出)")
                total_fail += 1
            # 最后几行输出
            stdout_lines = result.stdout.strip().split('\n')
            if stdout_lines:
                for line in stdout_lines[-5:]:
                    print(f"  {line}")
        except subprocess.TimeoutExpired:
            print(f"⏰ {script_name} 超时")
            total_fail += 1
        except Exception as e:
            print(f"❌ {script_name} 异常: {e}")
            total_fail += 1
    
    print(f"\n{'='*50}")
    print(f"业务表同步汇总: ✅ {total_ok} 成功, ❌ {total_fail} 失败")
    print(f"{'='*50}")
