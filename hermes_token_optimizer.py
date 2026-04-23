#!/usr/bin/env python3
"""
Hermes Agent Token 优化脚本（上河一号定制版）
基于知乎文章《Hermes Agent 成本优化大揭秘》+ SegmentFault 转述 + 官方文档
10 大优化项可选执行，覆盖四层成本优化体系
"""

import subprocess, os, stat

CONFIG_PATH = os.path.expanduser("~/.hermes/config.yaml")
ENV_PATH = os.path.expanduser("~/.hermes/.env")


def run(cmd_args):
    try:
        r = subprocess.run(cmd_args, capture_output=True, text=True, timeout=30)
        return r.stdout.strip()
    except Exception as e:
        return f"[错误] {e}"


def ask(prompt, default="y"):
    r = input(f"{prompt} [{'Y/n' if default == 'y' else 'y/N'}] ").strip().lower()
    if not r:
        return default == "y"
    return r in ("y", "yes", "是")


def ask_int(prompt, default, min_val=1, max_val=999999):
    r = input(f"{prompt} [默认:{default}]: ").strip()
    if not r:
        return default
    try:
        v = int(r)
        if min_val <= v <= max_val:
            return v
        print(f"  范围 {min_val}-{max_val}，用默认值 {default}")
        return default
    except ValueError:
        print(f"  输入无效，用默认值 {default}")
        return default


def ask_float(prompt, default, min_val=0.0, max_val=1.0):
    r = input(f"{prompt} [默认:{default}]: ").strip()
    if not r:
        return default
    try:
        v = float(r)
        if min_val <= v <= max_val:
            return v
        return default
    except ValueError:
        print(f"  输入无效，用默认值 {default}")
        return default


def ask_str(prompt, default=""):
    r = input(f"{prompt} [{f'默认:{default}' if default else '回车跳过'}]: ").strip()
    return r if r else default


def write_env(pairs):
    """将键值对写入 .env，保留注释和空行，去重，权限 0600"""
    lines = []
    existing_keys = {}
    if os.path.exists(ENV_PATH):
        with open(ENV_PATH, "r") as f:
            for i, line in enumerate(f):
                lines.append(line.rstrip("\n"))
                stripped = line.strip()
                if stripped and not stripped.startswith("#") and "=" in stripped:
                    k, _, _ = stripped.partition("=")
                    existing_keys[k.strip()] = i

    # 更新已有 key 或追加新 key
    for k, v in pairs:
        if k in existing_keys:
            lines[existing_keys[k]] = f"{k}={v}"
        else:
            lines.append(f"{k}={v}")

    with open(ENV_PATH, "w") as f:
        f.write("\n".join(lines) + "\n")
    os.chmod(ENV_PATH, stat.S_IRUSR | stat.S_IWUSR)


# ========== 第一层：密钥池策略 ==========

def opt1_credential_pool():
    """密钥池策略"""
    print("\n--- 1. 密钥池策略 (credential_pool_strategies) ---")
    print("避免单密钥耗尽导致任务中断，浪费已建立的 context。")
    print("least_used = 均衡使用多个密钥，每个密钥发挥最大价值。")
    print("fill_first = 用完一个再用下一个（默认，不均衡）")
    print("round_robin = 循环轮询")
    if not ask("是否配置？"):
        return
    provider = ask_str("配置哪个 provider 的密钥池策略？", "zai")
    strategy = ask_str("策略 (least_used/round_robin/fill_first)", "least_used")
    run(["hermes", "config", "set", f"credential_pool_strategies.{provider}", strategy])
    print(f"  ✓ credential_pool_strategies.{provider} = {strategy}")

    # 引导添加密钥到池
    print("\n  密钥池需要多个 API key 才能生效。现在添加？")
    if not ask("添加密钥到 .env？"):
        print("  提示：稍后用 hermes auth add 添加，hermes auth list 查看状态")
        return

    keys_added = []
    while True:
        env_var = ask_str(f"  密钥环境变量名（如 GLM_API_KEY, ZAI_API_KEY_{len(keys_added)+1}）", "")
        if not env_var:
            break
        key_val = input(f"  输入 {env_var} 的值: ").strip()
        if not key_val:
            print("  值为空，跳过")
            continue
        keys_added.append((env_var, key_val))
        another = input("  继续添加下一个密钥？(y/n) [n]: ").strip().lower()
        if another not in ("y", "yes"):
            break

    # 统一 base_url
    base_url = ask_str("  统一 base_url（回车跳过）", "")
    if base_url:
        keys_added.append((f"{provider.upper()}_BASE_URL", base_url))

    # 写入 .env
    if keys_added:
        write_env(keys_added)
        print(f"  ✓ 已写入 {len([k for k in keys_added if 'BASE_URL' not in k[0]])} 个密钥到 .env")
        print("  提示：运行 hermes auth add 将密钥 seed 到池中")


# ========== 第二层：Context 压缩 ==========

def opt2_context_length():
    """设置 model.context_length"""
    print("\n--- 2. 上下文窗口长度 (model.context_length) ---")
    print("Hermes 默认不设 context_length，压缩算法无法精准计算触发时机。")
    print("GLM-5 = 200000, Claude = 200000, GPT-4o = 128000")
    if not ask("是否设置？"):
        return
    val = ask_int("输入 context_length（tokens数）", 200000, 1000, 10000000)
    run(["hermes", "config", "set", "model.context_length", str(val)])
    print(f"  ✓ model.context_length = {val}")


def opt3_max_tokens():
    """设置 model.max_tokens"""
    print("\n--- 3. 最大输出 tokens (model.max_tokens) ---")
    print("不设 max_tokens，模型输出可能被截断，浪费已花的输入 token。")
    print("GLM-5 = 131072, Claude = 16384, GPT-4o = 16384")
    if not ask("是否设置？"):
        return
    val = ask_int("输入 max_tokens", 131072, 256, 10000000)
    run(["hermes", "config", "set", "model.max_tokens", str(val)])
    print(f"  ✓ model.max_tokens = {val}")


def opt4_compression_threshold():
    """调整 compression.threshold"""
    print("\n--- 4. 压缩触发阈值 (compression.threshold) ---")
    print("默认 0.5 = 上下文用到 50% 就开始压缩，太早。")
    print("0.75 更稳（用到 75% 才压，留 25% 缓冲做压缩）。")
    print("不建议超 0.85，缓冲区不够压缩质量反而差。")
    if not ask("是否调整？"):
        return
    val = ask_float("输入 threshold (0.3~0.85)", 0.75, 0.2, 0.95)
    run(["hermes", "config", "set", "compression.threshold", str(val)])
    print(f"  ✓ compression.threshold = {val}")


def opt5_compression_target_ratio():
    """调整 compression.target_ratio"""
    print("\n--- 5. 压缩保留比例 (compression.target_ratio) ---")
    print("压缩后保留原上下文的多少比例。默认 0.1 = 只留 10%。")
    print("0.25 = 保留 25%，细节丢失更少，代价是省 token 效果略降。")
    if not ask("是否调整？"):
        return
    val = ask_float("输入 target_ratio (0.05~0.5)", 0.25, 0.05, 0.6)
    run(["hermes", "config", "set", "compression.target_ratio", str(val)])
    print(f"  ✓ compression.target_ratio = {val}")


def opt6_protect_last_n():
    """调整 compression.protect_last_n"""
    print("\n--- 6. 保护最近消息数 (compression.protect_last_n) ---")
    print("压缩时跳过最近 N 条消息。默认 20 太少，调到 30-40。")
    print("复杂任务（代码调试、多文件编辑）推荐 30-40。")
    if not ask("是否调整？"):
        return
    val = ask_int("输入 protect_last_n", 30, 5, 100)
    run(["hermes", "config", "set", "compression.protect_last_n", str(val)])
    print(f"  ✓ compression.protect_last_n = {val}")


def opt7_compression_summary_model():
    """设置 compression.summary_model"""
    print("\n--- 7. 压缩总结模型 (compression.summary_model) ---")
    print("用便宜模型做压缩总结，主模型只处理精简后的内容。")
    print("空白 = 用主模型（贵），设一个 flash 模型 = 省 10 倍。")
    print("例如：glm-4-flash, gemini-3-flash, claude-haiku-4-5")
    if not ask("是否配置？"):
        return
    provider = ask_str("provider（auto/zai/custom 等）", "auto")
    model = ask_str("model（如 glm-4-flash）", "glm-4-flash")
    run(["hermes", "config", "set", "compression.summary_provider", provider])
    run(["hermes", "config", "set", "compression.summary_model", model])
    env_pairs = []
    if provider == "custom":
        base_url = ask_str("base_url（custom 必填）", "")
        if not base_url:
            print("  custom 厂商必须填 base_url，跳过")
            return
        run(["hermes", "config", "set", "compression.summary_base_url", base_url])
        api_key = input("  输入 compression summary model 的 API key（回车跳过）: ").strip()
        if api_key:
            env_var = "AUX_COMPRESSION_API_KEY"
            env_pairs.append((env_var, api_key))
            run(["hermes", "config", "set", "auxiliary.compression.api_key_env", env_var])
    if env_pairs:
        write_env(env_pairs)
        print(f"  ✓ API key 已写入 .env")
    print(f"  ✓ compression.summary_provider = {provider}")
    print(f"  ✓ compression.summary_model = {model}")


# ========== 第三层：Auxiliary 模型 ==========

def opt8_auxiliary_models():
    """配置副驾模型"""
    print("\n--- 8. 副驾模型 (auxiliary) ---")
    print("不同任务用不同成本的模型，省 60-90%。")
    print("重任务（需理解力）：vision, web_extract, flush_memories")
    print("轻任务（纯分类/搜索）：compression, session_search, approval, skills_hub, mcp")
    print("每个副驾需配：provider + model + base_url + api_key（custom 厂商必须全填）")
    tasks = ["vision", "web_extract", "compression", "session_search",
             "approval", "skills_hub", "mcp", "flush_memories"]
    print(f"  可配任务：{', '.join(tasks)}")
    if not ask("是否配置？"):
        return

    while True:
        task = ask_str("配置哪个任务？（回车退出）", "")
        if not task:
            break
        if task not in tasks:
            print(f"  未知任务 {task}，可选：{', '.join(tasks)}")
            continue
        provider = ask_str("provider（auto/custom/zai 等）", "custom")
        model = ask_str("model", "")
        if not model:
            print("  model 不能为空，跳过此任务")
            continue
        base_url = ""
        if provider == "custom":
            base_url = ask_str("base_url（custom 必填）", "")
            if not base_url:
                print("  custom 厂商必须填 base_url，跳过此任务")
                continue
        timeout = ask_int("timeout（秒）", 30, 5, 600)
        run(["hermes", "config", "set", f"auxiliary.{task}.provider", provider])
        run(["hermes", "config", "set", f"auxiliary.{task}.model", model])
        if base_url:
            run(["hermes", "config", "set", f"auxiliary.{task}.base_url", base_url])
        run(["hermes", "config", "set", f"auxiliary.{task}.timeout", str(timeout)])

        # API key 写入 .env
        env_pairs = []
        if provider == "custom":
            api_key = input(f"  输入 auxiliary.{task} 的 API key（回车跳过）: ").strip()
            if api_key:
                env_var = f"AUX_{task.upper()}_API_KEY"
                env_pairs.append((env_var, api_key))
                run(["hermes", "config", "set", f"auxiliary.{task}.api_key_env", env_var])
        if env_pairs:
            write_env(env_pairs)
            print(f"  ✓ API key 已写入 .env（变量名 {env_var}）")

        print(f"  ✓ auxiliary.{task} 已配置")

        another = input("  继续配置下一个副驾？(y/n) [n]: ").strip().lower()
        if another not in ("y", "yes"):
            break


# ========== 第四层：Smart Model Routing ==========

def opt9_smart_routing():
    """智能模型路由 — 说明"""
    print("\n--- 9. 智能模型路由 (提示) ---")
    print("知乎文章提到的 smart_model_routing 在 Hermes v0.10.0 中尚不支持。")
    print("Hermes 当前的等效方案是 auxiliary 副驾模型系统（选项 8）。")
    print("将轻任务（compression/session_search/approval/skills_hub/mcp）")
    print("配置为便宜模型，效果等同于智能路由。")
    print("如果你还没配副驾，建议选 8 配置。")


# ========== 压缩开关 ==========

def opt10_enable_compression():
    """确认 compression.enabled"""
    print("\n--- 10. 压缩开关 (compression.enabled) ---")
    print("必须为 true，上面 4-7 项才生效。")
    if not ask("是否确保开启？"):
        return
    run(["hermes", "config", "set", "compression.enabled", "true"])
    print("  ✓ compression.enabled = true")


# ========== 主菜单 ==========

OPT_MAP = {
    "1": ("密钥池策略 (credential_pool_strategies)", opt1_credential_pool),
    "2": ("上下文窗口长度 (context_length)", opt2_context_length),
    "3": ("最大输出 tokens (max_tokens)", opt3_max_tokens),
    "4": ("压缩触发阈值 (threshold)", opt4_compression_threshold),
    "5": ("压缩保留比例 (target_ratio)", opt5_compression_target_ratio),
    "6": ("保护最近消息数 (protect_last_n)", opt6_protect_last_n),
    "7": ("压缩总结模型 (summary_model)", opt7_compression_summary_model),
    "8": ("副驾模型 (auxiliary)", opt8_auxiliary_models),
    "9": ("智能模型路由 (smart_model_routing)", opt9_smart_routing),
    "10": ("压缩开关 (compression.enabled)", opt10_enable_compression),
}

VALID_KEYS = set(OPT_MAP.keys())

print("=" * 56)
print("Hermes Token 优化（上河一号定制版）")
print("四层成本优化体系，10 大项可选")
print("=" * 56)

print("\n第一层：密钥池策略 — 避免单点耗尽")
print("  1. 密钥池策略 (credential_pool_strategies)")

print("\n第二层：Context 压缩 — 省钱的黑魔法")
print("  2. 上下文窗口长度 (context_length)")
print("  3. 最大输出 tokens (max_tokens)")
print("  4. 压缩触发阈值 (threshold)")
print("  5. 压缩保留比例 (target_ratio)")
print("  6. 保护最近消息数 (protect_last_n)")
print("  7. 压缩总结模型 (summary_model)")
print("  10. 压缩开关 (compression.enabled)")

print("\n第三层：Auxiliary 模型 — 任务分级定价")
print("  8. 副驾模型 (auxiliary)")

print("\n第四层：Smart Model Routing — 自动降级")
print("  9. 智能模型路由 (smart_model_routing)")

print("\n  0. 全部优化")
print("  a. 全部跳过（退出）")

selection = input("\n选哪些（多选用逗号分隔，如 4,5,6,7）[默认:0]: ").strip().lower()

if selection == "a":
    print("退出。")
    exit(0)

if selection in ("", "0"):
    chosen = list(OPT_MAP.keys())
else:
    chosen = [k.strip() for k in selection.split(",") if k.strip() in VALID_KEYS]

if not chosen:
    print("无有效选择，退出。")
    exit(0)

for k in chosen:
    entry = OPT_MAP[k]
    name, fn = entry
    fn()

print("\n" + "=" * 56)
print("优化完成。")
print("⚠ 修改配置后需要重启网关才能生效：/restart")
print("📊 验证：hermes auth list / hermes usage / hermes insights")
print("=" * 56)
