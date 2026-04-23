import json
import sys
import datetime

def generate_log(task_data):
    try:
        data = json.loads(task_data)
        task_name = data.get('task_name', '未命名任务')
        status = data.get('status', '未知状态')
        start_time_str = data.get('start_time', '')
        end_time_str = data.get('end_time', '')
        key_outputs = data.get('key_outputs', [])
        summary = data.get('summary', '')

        if start_time_str and end_time_str:
            try:
                start_time = datetime.datetime.fromisoformat(start_time_str)
                end_time = datetime.datetime.fromisoformat(end_time_str)
                duration = (end_time - start_time).total_seconds()
                time_info = f" (耗时: {duration:.2f}秒)"
            except ValueError:
                time_info = ""
        else:
            time_info = ""

        log_parts = [
            f"**任务日志: {task_name}** ({status})",
            f"- **开始时间**: {start_time_str}" if start_time_str else "",
            f"- **结束时间**: {end_time_str}{time_info}" if end_time_str else "",
            "- **关键输出**:",
        ]
        
        if key_outputs:
            for i, output in enumerate(key_outputs):
                log_parts.append(f"  {i+1}. {output}")
        else:
            log_parts.append("  (无明显输出)")

        if summary:
            log_parts.append(f"- **摘要**: {summary}")

        print("\n".join(filter(None, log_parts)))

    except json.JSONDecodeError:
        print("**错误: 无法解析任务数据。**")
    except Exception as e:
        print(f"**错误: 生成日志时发生未知错误: {e}**")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        generate_log(sys.argv[1])
    else:
        print("**错误: 请提供任务数据 (JSON 字符串)。**")
