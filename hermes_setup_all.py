#!/usr/bin/env python3
"""
Hermes Agent 全量配置脚本（上河一号定制版）
整合《Hermes 进阶指南》上下两篇
9 大功能可选配置：副驾模型 / 搜索后端 / 记忆系统 / Profile 分身 / Skill 进化 / 子 Agent 并发 / Cron 定时 / Token 监控 / 生态工具
"""

import subprocess, os, stat, shlex

ENV_PATH = os.path.expanduser("~/.hermes/.env")


def run(cmd_args, background=False):
    """安全执行命令，列表传参防注入"""
    print(f"  执行: {' '.join(cmd_args)}")
    if background:
        subprocess.Popen(
            cmd_args,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        print(f"  ✓ 后台启动")
        return True
    r = subprocess.run(cmd_args, capture_output=True, text=True)
    if r.returncode != 0:
        print(f"  ⚠ 失败: {r.stderr.strip() or r.stdout.strip()}")
    else:
        print(f"  ✓ 成功")
    return r.returncode == 0


def ask(prompt, default=""):
    val = input(f"  {prompt} [{'默认:' + default if default else '无'}]: ").strip()
    return val if val else default


def ask_int(prompt, default, min_val=None, max_val=None):
    raw = ask(prompt, str(default))
    try:
        val = int(raw)
        if min_val is not None and val < min_val:
            print(f"  ⚠ 值不能小于 {min_val}，回退默认 {default}")
            return default
        if max_val is not None and val > max_val:
            print(f"  ⚠ 值不能大于 {max_val}，回退默认 {default}")
            return default
        return val
    except ValueError:
        print(f"  ⚠ 非数字输入，回退默认 {default}")
        return default


def ask_yn(prompt, default="n"):
    val = ask(prompt, default)
    return val.lower() in ("y", "yes")


def write_env(key, value):
    """写入 .env，精确匹配 key= 替换，权限 0600"""
    if not value:
        return
    lines = []
    found = False
    if os.path.exists(ENV_PATH):
        with open(ENV_PATH, "r") as f:
            lines = f.readlines()
    new_lines = []
    for line in lines:
        stripped = line.strip()
        parts = stripped.split("=", 1)
        if parts[0] == key:
            new_lines.append(f"{key}={value}\n")
            found = True
        else:
            new_lines.append(line)
    if not found:
        new_lines.append(f"{key}={value}\n")
    with open(ENV_PATH, "w") as f:
        f.writelines(new_lines)
    os.chmod(ENV_PATH, stat.S_IRUSR | stat.S_IWUSR)
    print(f"  ✓ {key} 已写入 ~/.hermes/.env (权限 0600)")


def set_auxiliary(task, provider, model, base_url="", api_key_env=None):
    """配置单个 auxiliary 任务，API Key 写 .env 而非 config.yaml"""
    run(["hermes", "config", "set", f"auxiliary.{task}.provider", provider])
    run(["hermes", "config", "set", f"auxiliary.{task}.model", model])
    if base_url:
        run(["hermes", "config", "set", f"auxiliary.{task}.base_url", base_url])
    if api_key_env and isinstance(api_key_env, dict) and api_key_env.get("value"):
        write_env(api_key_env["name"], api_key_env["value"])


def validate_name(name):
    """校验 profile 名：非空、无空格、只含字母数字连字符下划线"""
    if not name:
        print("  ⚠ 名称不能为空")
        return False
    if " " in name:
        print("  ⚠ 名称不能含空格")
        return False
    if not name.replace("-", "").replace("_", "").isalnum():
        print("  ⚠ 名称只能含字母、数字、连字符、下划线")
        return False
    return True


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
print("=" * 52)
print("  Hermes 全量配置（上河一号定制版）")
print("  9 大功能，逐项确认，不想配的直接跳过")
print("=" * 52)

FEATURES = [
    ("1", "副驾模型 (auxiliary)", "成本降 60%-70%，延迟快一倍"),
    ("2", "搜索后端", "让它能联网查东西"),
    ("3", "记忆系统", "内置记忆参数 + 可选外部 Provider"),
    ("4", "Profile 分身", "一台机器养多个独立人格/记忆的分身"),
    ("5", "Skill 自主进化", "Agent 从对话中自动沉淀新技能"),
    ("6", "子 Agent 并发", "派多路 agent 同时干活"),
    ("7", "Cron 定时任务", "让 agent 定时自己跑任务"),
    ("8", "Token 监控与压缩", "装工具看花在哪、压掉冗余"),
    ("9", "生态工具", "批量装 skill、装文档处理工具"),
]

VALID_KEYS = {str(i) for i in range(1, 10)}

print("\n  可配置功能：")
for num, name, desc in FEATURES:
    print(f"    {num}. {name} — {desc}")

print(f"\n    0. 全部配置")
print(f"    a. 全部跳过（退出）")

choice = ask("\n  选哪些（多选用逗号分隔，如 1,3,5）", "0")

if choice == "a":
    print("  退出。")
    raise SystemExit(0)

if choice == "0":
    selected = VALID_KEYS
else:
    selected = {c.strip() for c in choice.split(",") if c.strip() in VALID_KEYS}

if not selected:
    print("  无有效选择，退出。")
    raise SystemExit(0)

print(f"\n  将配置: {', '.join(sorted(selected, key=int))}")


# ━━━ 1. 副驾模型 ━━━
if "1" in selected:
    print("\n┏━ 1. 副驾模型（auxiliary）")
    print("┃ 不配 = 所有副驾走主模型 = 用瑞士军刀削铅笔")
    print("┃ 配好 = 成本降 60%-70%，延迟快一倍")
    print("┗" + "━" * 50)

    print("\n  副驾分两类：")
    print("    重任务（需理解力）：vision, web_extract, flush_memories")
    print("    轻任务（纯分类/搜索）：compression, session_search, approval, skills_hub, mcp")

    print("\n  --- 重任务模型 ---")
    heavy_provider = ask("重任务模型厂商 (如 gemini/openrouter/anthropic/custom)", "custom")
    heavy_model = ask("重任务模型名 (如 gemini-2.5-flash)", "gemini-2.5-flash")
    heavy_base_url = ask("Base URL (custom 必填，其他留空)", "")
    heavy_api_key = ask("API Key (custom 必填，其他留空，将写入.env而非config)", "")

    print("\n  --- 轻任务模型 ---")
    light_provider = ask("轻任务模型厂商", "custom")
    light_model = ask("轻任务模型名 (如 gemini-2.5-flash-lite)", "gemini-2.5-flash-lite")
    light_base_url = ask("Base URL (custom 必填，其他留空)", "")
    light_api_key = ask("API Key (custom 必填，其他留空，将写入.env而非config)", "")

    HEAVY = ["vision", "web_extract", "flush_memories"]
    LIGHT = ["compression", "session_search", "approval", "skills_hub", "mcp"]

    print("\n  正在写入配置...")
    heavy_key_env = {"name": "AUX_HEAVY_API_KEY", "value": heavy_api_key} if heavy_api_key else None
    light_key_env = {"name": "AUX_LIGHT_API_KEY", "value": light_api_key} if light_api_key else None

    for task in HEAVY:
        set_auxiliary(task, heavy_provider, heavy_model, heavy_base_url, heavy_key_env)
    for task in LIGHT:
        set_auxiliary(task, light_provider, light_model, light_base_url, light_key_env)


# ━━━ 2. 搜索后端 ━━━
if "2" in selected:
    print("\n┏━ 2. 搜索后端")
    print("┃ 默认是聋的，需要配搜索才能联网")
    print("┗" + "━" * 50)

    print("\n  可选后端：")
    print("    1. tavily — 专为 AI 设计，结构化结果，月 1000 次免费")
    print("    2. duckduckgo — 零成本兜底，不需 API key")
    print("    3. 跳过，稍后手动配")

    search_choice = ask("选哪个 (1/2/3)", "2")
    if search_choice == "1":
        tavily_key = ask("Tavily API Key (去 tavily.com 注册拿)", "")
        if tavily_key:
            write_env("TAVILY_API_KEY", tavily_key)
        run(["hermes", "config", "set", "web.backend", "tavily"])
        run(["hermes", "config", "set", "web.fallback_backend", "duckduckgo"])
    elif search_choice == "2":
        run(["hermes", "config", "set", "web.backend", "duckduckgo"])
    else:
        print("  跳过搜索配置。")


# ━━━ 3. 记忆系统 ━━━
if "3" in selected:
    print("\n┏━ 3. 记忆系统")
    print("┃ 三层：内置记忆(默认开) → 外部Provider(可选) → Session Search(默认开)")
    print("┗" + "━" * 50)

    print("\n  内置记忆参数（当前默认值一般够用，重度使用可调）：")
    mem_limit = ask_int("memory_char_limit (MEMORY.md 上限字符)", 2200, min_val=100)
    user_limit = ask_int("user_char_limit (USER.md 上限字符)", 1375, min_val=100)
    nudge = ask_int("nudge_interval (每N轮提醒存记忆)", 10, min_val=1)
    flush = ask_int("flush_min_turns (至少N轮才触发退出刷新)", 6, min_val=1)

    run(["hermes", "config", "set", "memory.memory_enabled", "true"])
    run(["hermes", "config", "set", "memory.user_profile_enabled", "true"])
    run(["hermes", "config", "set", "memory.memory_char_limit", str(mem_limit)])
    run(["hermes", "config", "set", "memory.user_char_limit", str(user_limit)])
    run(["hermes", "config", "set", "memory.nudge_interval", str(nudge)])
    run(["hermes", "config", "set", "memory.flush_min_turns", str(flush)])

    print("\n  外部 Memory Provider（可选，建议先跑两周再决定）：")
    print("  支持: honcho, mem0, hindsight 等")
    if ask_yn("是否现在配外部记忆？(y/n)", "n"):
        print("  运行: hermes memory setup （交互式向导）")
        run(["hermes", "memory", "setup"])


# ━━━ 4. Profile 分身 ━━━
if "4" in selected:
    print("\n┏━ 4. Profile 分身")
    print("┃ 每个分身独立记忆/人格/配置，互不干扰")
    print("┗" + "━" * 50)

    if not ask_yn("是否创建新 Profile？(y/n)", "n"):
        print("  跳过。")
    else:
        profile_name = ask("Profile 名称 (如 work/life/coder)", "work")
        if not validate_name(profile_name):
            print("  ⚠ 名称不合法，跳过 Profile 创建。")
        else:
            use_clone = ask_yn("从当前配置克隆？(推荐 y，否则空白分身需重新配)", "y")
            cmd = ["hermes", "profile", "create", profile_name]
            if use_clone:
                cmd.append("--clone")
            run(cmd)

            if ask_yn("是否设为默认 Profile？(y/n)", "n"):
                run(["hermes", "profile", "use", profile_name])

    print("  管理命令：")
    print("    hermes profile list          — 查看所有分身")
    print("    hermes -p <name> chat        — 临时切换")
    print("    hermes profile use <name>    — 粘性切换为默认")
    print("    hermes profile delete <name> — 删除")


# ━━━ 5. Skill 自主进化 ━━━
if "5" in selected:
    print("\n┏━ 5. Skill 自主进化")
    print("┃ Agent 在对话中自动沉淀可复用经验为新 skill")
    print("┗" + "━" * 50)

    if not ask_yn("启用 Skill 自主进化？(y/n)", "y"):
        run(["hermes", "config", "set", "creation_nudge_interval", "0"])
        print("  已关闭自主进化（interval=0）。")
    else:
        interval = ask_int(
            "creation_nudge_interval（每N次工具调用触发一次审查，0=关闭）",
            15, min_val=0, max_val=100
        )
        run(["hermes", "config", "set", "creation_nudge_interval", str(interval)])

        if interval > 0:
            print("  进化机制：")
            print("    工具调用达阈值 → 后台 fork review agent")
            print("    → 审查对话有无非平凡经验 → update/create/nothing")
            print("    → 结果打印 Skill created: xxx，不打断你")

    print("  手动装 skill：")
    print("    hermes skills install wondelai/skills      — 380+ 跨平台 skill")
    print("    hermes skills install <owner/repo>         — 从 GitHub 装")


# ━━━ 6. 子 Agent 并发 ━━━
if "6" in selected:
    print("\n┏━ 6. 子 Agent 并发")
    print("┃ 派多路 agent 同时干活，结果合并返回")
    print("┗" + "━" * 50)

    print("  两种模式：")
    print("    同 session 子 agent — 共享上下文，适合同一话题多路查询")
    print("    Profile 隔离模式     — 独立记忆，适合互不相关的任务")
    print()
    print("  Hermes 内置 delegate_task 工具，无需额外配置。")
    print("  用法：直接告诉 Hermes ——")
    print('    "帮我派3路agent，一个查GitHub、一个查X、一个查Reddit"')
    print()
    print("  建议：2-3 个并发最稳，子 agent 不继承上下文，指令要一次塞够。")

    if ask_yn("是否配置默认并发上限？(y/n)", "n"):
        max_concurrent = ask_int("最大并发子 agent 数", 3, min_val=1, max_val=10)
        run(["hermes", "config", "set", "delegation.max_concurrent_children", str(max_concurrent)])


# ━━━ 7. Cron 定时任务 ━━━
if "7" in selected:
    print("\n┏━ 7. Cron 定时任务")
    print("┃ 让 agent 定时自己干活，如每天早8点总结新闻")
    print("┗" + "━" * 50)

    print("  前置条件：hermes gateway 必须在跑，cron 才会按时触发")
    print()
    if ask_yn("现在启动 hermes gateway？(y/n)", "n"):
        if ask_yn("是否后台启动？(y/n)", "y"):
            run(["hermes", "gateway"], background=True)
        else:
            run(["hermes", "gateway"])

    if ask_yn("是否创建一个示例 Cron 任务？(y/n)", "n"):
        print("  示例：每天早8点总结AI新闻")
        schedule = ask("Cron 表达式或自然语言（如 '0 8 * * *' 或 '每天早上8点'）", "0 8 * * *")
        prompt_text = ask("任务指令", "总结昨天AI圈最重要的3条新闻")
        target = ask("结果推送到哪（如 telegram/discord/local，留空=仅保存）", "local")
        safe_schedule = shlex.quote(schedule)
        safe_prompt = shlex.quote(prompt_text)
        target_flag = f"--deliver {shlex.quote(target)}" if target else ""
        print("  建议直接跟 Hermes 说：")
        print(f'    "{schedule} {prompt_text}"')
        print("  或手动创建：")
        print(f"    hermes cron create --schedule {safe_schedule} --prompt {safe_prompt} {target_flag}")

    print("  管理命令：")
    print("    hermes cron list    — 查看所有定时任务")
    print("    hermes cron pause   — 暂停")
    print("    hermes cron resume  — 恢复")
    print("    hermes cron remove  — 删除")


# ━━━ 8. Token 监控与压缩 ━━━
if "8" in selected:
    print("\n┏━ 8. Token 监控与压缩")
    print("┃ 看钱花在哪、压掉冗余开销")
    print("┗" + "━" * 50)

    print("\n  --- Token 监控 ---")
    print("  可选工具：")
    print("    1. tokscale        — 一条命令看全局 token 消耗")
    print("    2. hermes-dashboard — 社区做的 token 面板，按组件拆解")
    print("    3. hermes dashboard — 官方 Web Dashboard")
    print("    4. 跳过")

    monitor = ask("选哪个 (1/2/3/4)", "4")
    if monitor == "1":
        if ask_yn("安装 tokscale？(需要 pip)(y/n)", "y"):
            run(["pip", "install", "tokscale"])
            print("  使用：tokscale --hermes")
    elif monitor == "2":
        if ask_yn("安装 hermes-dashboard？(需要 pip)(y/n)", "y"):
            run(["pip", "install", "hermes-dashboard"])
            print("  使用：hermes-dashboard")
    elif monitor == "3":
        print("  启动：hermes dashboard")
        if ask_yn("现在启动？(y/n)", "n"):
            run(["hermes", "dashboard"])

    print("\n  --- Token 压缩 ---")
    print("  RTK (Rust Token Killer)：把终端命令 token 消耗压掉 80-90%")
    if ask_yn("安装 RTK？(需要 cargo)(y/n)", "n"):
        run(["cargo", "install", "rtk"])
        if ask_yn("启用 RTK？(y/n)", "y"):
            run(["hermes", "config", "set", "terminal.compressor", "rtk"])
        print("  如不启用，RTK 安装后可手动开启")

    print("\n  --- 上下文压缩（选了第1项副驾的可复查）---")
    if ask_yn("是否调整上下文压缩参数？(y/n)", "n"):
        threshold_pct = ask_int(
            "compression.threshold（上下文占用%达多少触发压缩，如75=75%）",
            75, min_val=10, max_val=95
        )
        target_ratio_pct = ask_int(
            "compression.target_ratio（压缩后保留原内容%，如25=保留25%）",
            25, min_val=10, max_val=90
        )
        protect_n = ask_int(
            "compression.protect_last_n（保护最近N条消息不参与压缩）",
            30, min_val=5, max_val=100
        )
        run(["hermes", "config", "set", "compression.threshold", str(threshold_pct / 100)])
        run(["hermes", "config", "set", "compression.target_ratio", str(target_ratio_pct / 100)])
        run(["hermes", "config", "set", "compression.protect_last_n", str(protect_n)])
        print(f"  ✓ threshold={threshold_pct/100}, target_ratio={target_ratio_pct/100}, protect_last_n={protect_n}")

        if ask_yn("是否配置压缩总结模型（用便宜模型做总结，省10倍）?(y/n)", "n"):
            summary_provider = ask("summary provider（auto/zai/custom 等）", "auto")
            summary_model = ask("summary model（如 glm-4-flash）", "glm-4-flash")
            run(["hermes", "config", "set", "compression.summary_provider", summary_provider])
            run(["hermes", "config", "set", "compression.summary_model", summary_model])
            if summary_provider == "custom":
                summary_base_url = ask("summary base_url（custom 必填）", "")
                if summary_base_url:
                    run(["hermes", "config", "set", "compression.summary_base_url", summary_base_url])
                summary_api_key = ask("summary API key（写入.env）", "")
                if summary_api_key:
                    write_env("AUX_COMPRESSION_API_KEY", summary_api_key)
                    run(["hermes", "config", "set", "auxiliary.compression.api_key_env", "AUX_COMPRESSION_API_KEY"])


# ━━━ 9. 生态工具 ━━━
if "9" in selected:
    print("\n┏━ 9. 生态工具")
    print("┃ 批量装 skill、装文档处理工具")
    print("┗" + "━" * 50)

    print("\n  --- Skill 库 ---")
    print("  可选源：")
    print("    1. wondelai/skills       — 380+ 跨平台 skill")
    print("    2. awesome-agent-skills  — 1000+ skills 社区合集")
    print("    3. 两个都装")
    print("    4. 跳过")

    skill_choice = ask("选哪个 (1/2/3/4)", "4")
    if skill_choice in ("1", "3"):
        if ask_yn("安装 wondelai/skills？(y/n)", "y"):
            run(["hermes", "skills", "install", "wondelai/skills"])
    if skill_choice in ("2", "3"):
        if ask_yn("安装 awesome-agent-skills？(y/n)", "y"):
            run(["hermes", "skills", "install", "awesome-agent-skills"])

    print("\n  --- 文档处理工具 ---")
    print("  Pandoc：万能格式转换（PDF/DOCX/HTML/EPUB → Markdown）")
    if ask_yn("安装 Pandoc？(y/n)", "n"):
        run(["sudo", "apt-get", "install", "-y", "pandoc"])

    print("  Marker：PDF 转 Markdown 效果优于 Pandoc（需 pip）")
    if ask_yn("安装 Marker？(y/n)", "n"):
        run(["pip", "install", "marker-pdf"])

    print("\n  生态导航：")
    print("    awesome-hermes-agent:  https://github.com/awesome-hermes-agent")
    print("    生态地图:             https://hermes-ecosystem.vercel.app")


# ━━━ 完成 ━━━
print("\n" + "=" * 52)
print("  配置完成。验证：")
print("    hermes config              — 查看当前配置")
print("    hermes profile list        — 查看分身")
print("    hermes cron list           — 查看定时任务")
print("    hermes skills list         — 查看已装 skill")
print("=" * 52)
