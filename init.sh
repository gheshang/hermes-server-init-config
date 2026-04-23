#!/bin/bash
# ==========================================
# 纯净版 VPS 初始化脚本 v2.0 (交互菜单版)
# 覆盖：更新清理、时区、DNS、BBR、Swap、IPv4优先、
#       基础工具、Docker、SSH加固、防火墙、Fail2Ban、
#       自动安全更新、内核加固、禁用无用服务
# ==========================================

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

if [ "$EUID" -ne 0 ]; then
    echo -e "${RED}错误：请使用 root 用户运行此脚本${NC}"
    exit 1
fi

if [ -f /etc/os-release ]; then
    . /etc/os-release
    OS=$ID
else
    echo -e "${RED}无法检测系统类型${NC}"
    exit 1
fi

# ------------------------------------------
# 第一组：基础环境
# ------------------------------------------

step1_update() {
    echo -e "${YELLOW}[1/14] 系统更新 + 垃圾清理${NC}"

    # 系统更新
    if [[ "$OS" == "ubuntu" || "$OS" == "debian" ]]; then
        apt update -y && apt upgrade -y && apt autoremove --purge -y
    elif [[ "$OS" == "centos" || "$OS" == "rhel" || "$OS" == "almalinux" || "$OS" == "rocky" ]]; then
        dnf upgrade -y && dnf autoremove -y
    else
        echo -e "${RED}不支持的系统，跳过更新${NC}"
        return 1
    fi

    # APT缓存清理
    apt clean 2>/dev/null
    apt autoclean 2>/dev/null

    # systemd日志限100M
    if command -v journalctl &> /dev/null; then
        journalctl --vacuum-size=100M 2>/dev/null
    fi

    # 清理30天以上的压缩日志和7天以上的轮转日志
    find /var/log -name "*.gz" -mtime +30 -delete 2>/dev/null
    find /var/log -name "*.1" -mtime +7 -delete 2>/dev/null
    find /var/log -name "*.old" -mtime +7 -delete 2>/dev/null

    # 截断超过100M的活动日志
    find /var/log -type f -name "*.log" -size +100M -exec truncate -s 0 {} \; 2>/dev/null

    echo -e "${GREEN}✔ 系统更新与垃圾清理完成${NC}"
}

step2_timezone() {
    echo -e "${YELLOW}[2/14] 设置时区为 Asia/Shanghai${NC}"
    timedatectl set-timezone Asia/Shanghai
    echo -e "${GREEN}✔ 时区设置完成${NC}"
}

step3_dns() {
    echo -e "${YELLOW}[3/14] DNS 优化 (自动检测国内/海外)${NC}"

    # 自动检测：尝试访问国内站点，成功则判定为国内
    if curl -s --connect-timeout 3 --max-time 5 http://www.baidu.com > /dev/null 2>&1; then
        echo -e "${CYAN}检测到国内网络环境，使用国内 DNS${NC}"
        DNS_PRIMARY="223.5.5.5"
        DNS_SECONDARY="119.29.29.29"
        DNS_LABEL="国内(阿里+腾讯)"
    else
        echo -e "${CYAN}检测到海外网络环境，使用海外 DNS${NC}"
        DNS_PRIMARY="1.1.1.1"
        DNS_SECONDARY="8.8.8.8"
        DNS_LABEL="海外(Cloudflare+Google)"
    fi

    cp /etc/resolv.conf /etc/resolv.conf.bak 2>/dev/null
    chattr -i /etc/resolv.conf 2>/dev/null
    cat > /etc/resolv.conf << EOF
nameserver $DNS_PRIMARY
nameserver $DNS_SECONDARY
EOF
    chattr +i /etc/resolv.conf 2>/dev/null || true
    echo -e "${GREEN}✔ DNS 设置完成 [$DNS_LABEL] (已锁定防篡改，如需修改请先 chattr -i /etc/resolv.conf)${NC}"
}

# ------------------------------------------
# 第二组：内核调优
# ------------------------------------------

step4_bbr() {
    echo -e "${YELLOW}[4/14] 配置 BBR 网络加速${NC}"
    cat > /etc/sysctl.d/99-bbr.conf << 'EOF'
net.core.default_qdisc=fq
net.ipv4.tcp_congestion_control=bbr
EOF
    sysctl --system > /dev/null 2>&1
    if sysctl net.ipv4.tcp_congestion_control 2>/dev/null | grep -q bbr; then
        echo -e "${GREEN}✔ BBR 已生效${NC}"
    else
        echo -e "${YELLOW}✔ BBR 配置已写入，重启后生效${NC}"
    fi
}

step5_swap() {
    echo -e "${YELLOW}[5/14] 配置 2G 虚拟内存${NC}"
    if [ ! -f /swapfile ]; then
        dd if=/dev/zero of=/swapfile bs=1M count=2048 status=progress
        chmod 600 /swapfile
        mkswap /swapfile > /dev/null
        swapon /swapfile
        if ! grep -q '/swapfile' /etc/fstab; then
            echo '/swapfile none swap sw 0 0' >> /etc/fstab
        fi
        cat > /etc/sysctl.d/99-swappiness.conf << 'EOF'
vm.swappiness=10
EOF
        sysctl --system > /dev/null 2>&1
        echo -e "${GREEN}✔ 2G Swap 配置完成${NC}"
    else
        echo -e "${YELLOW}! 检测到 Swap 已存在，跳过${NC}"
    fi
}

step6_ipv4() {
    echo -e "${YELLOW}[6/14] 设置 IPv4 优先${NC}"
    if [ -f /etc/gai.conf ]; then
        sed -i 's/^#precedence ::ffff:0:0\/96.*/precedence ::ffff:0:0\/96 100/' /etc/gai.conf
        if ! grep -q "^precedence ::ffff:0:0\/96" /etc/gai.conf; then
            echo "precedence ::ffff:0:0/96 100" >> /etc/gai.conf
        fi
        echo -e "${GREEN}✔ IPv4 优先设置完成${NC}"
    else
        echo -e "${YELLOW}! 缺少 /etc/gai.conf，跳过${NC}"
    fi
}

# ------------------------------------------
# 第三组：工具安装
# ------------------------------------------

step7_tools() {
    echo -e "${YELLOW}[7/14] 安装基础工具${NC}"
    if [[ "$OS" == "ubuntu" || "$OS" == "debian" ]]; then
        apt install -y vim curl wget git htop unzip net-tools tar python3-pip
    elif [[ "$OS" == "centos" || "$OS" == "rhel" || "$OS" == "almalinux" || "$OS" == "rocky" ]]; then
        dnf install -y vim curl wget git htop unzip net-tools tar python3-pip
    fi
    echo -e "${GREEN}✔ 基础工具安装完成 (vim curl wget git htop unzip net-tools tar pip3)${NC}"
}

step8_docker() {
    echo -e "${YELLOW}[8/14] 安装 Docker${NC}"
    echo -e "${CYAN}此步骤将使用 Docker 官方脚本安装，是否继续？(y/n)${NC}"
    read -r confirm
    if [[ "$confirm" != "y" && "$confirm" != "Y" ]]; then
        echo -e "${YELLOW}已跳过 Docker 安装${NC}"
        return
    fi
    curl -fsSL https://get.docker.com | sh
    systemctl enable docker
    echo -e "${GREEN}✔ Docker 安装完成${NC}"
}

# ------------------------------------------
# 第四组：安全加固
# ------------------------------------------

step9_ssh() {
    echo -e "${YELLOW}[9/14] SSH 加固${NC}"

    # 检查 authorized_keys 是否存在
    if [ ! -f ~/.ssh/authorized_keys ] || [ ! -s ~/.ssh/authorized_keys ]; then
        echo -e "${RED}⚠ 未检测到 SSH 公钥！禁用密码登录将锁死服务器，跳过此步骤${NC}"
        echo -e "${RED}  请先部署 SSH 公钥到 ~/.ssh/authorized_keys 后再执行${NC}"
        return 1
    fi

    SSH_CONFIG="/etc/ssh/sshd_config"
    cp "$SSH_CONFIG" "${SSH_CONFIG}.bak"

    # 自定义端口
    echo -e "${CYAN}请输入新的 SSH 端口 (直接回车保持22不变):${NC}"
    read -r ssh_port
    if [[ -n "$ssh_port" ]]; then
        # 验证端口范围
        if [[ "$ssh_port" -ge 1 && "$ssh_port" -le 65535 ]] 2>/dev/null; then
            sed -i "s/^#*Port .*/Port $ssh_port/" "$SSH_CONFIG"
            SSH_NEW_PORT="$ssh_port"
            echo -e "${GREEN}  SSH 端口已改为 $ssh_port${NC}"
        else
            echo -e "${RED}  端口无效，保持默认22${NC}"
            SSH_NEW_PORT="22"
        fi
    else
        SSH_NEW_PORT="22"
    fi

    # 禁用root密码登录（保留key登录）
    sed -i 's/^#*PermitRootLogin.*/PermitRootLogin prohibit-password/' "$SSH_CONFIG"

    # 禁用密码认证
    sed -i 's/^#*PasswordAuthentication.*/PasswordAuthentication no/' "$SSH_CONFIG"

    # 禁用空密码
    sed -i 's/^#*PermitEmptyPasswords.*/PermitEmptyPasswords no/' "$SSH_CONFIG"

    # 限制认证尝试
    if ! grep -q "^MaxAuthTries" "$SSH_CONFIG"; then
        echo "MaxAuthTries 3" >> "$SSH_CONFIG"
    else
        sed -i 's/^#*MaxAuthTries.*/MaxAuthTries 3/' "$SSH_CONFIG"
    fi

    # 连接超时
    if ! grep -q "^ClientAliveInterval" "$SSH_CONFIG"; then
        cat >> "$SSH_CONFIG" << 'SSHEOF'
ClientAliveInterval 300
ClientAliveCountMax 2
SSHEOF
    fi

    # 禁用X11转发
    sed -i 's/^#*X11Forwarding.*/X11Forwarding no/' "$SSH_CONFIG"

    # 重启sshd前先放行新端口
    if [[ -n "$SSH_NEW_PORT" && "$SSH_NEW_PORT" != "22" ]]; then
        if command -v ufw &> /dev/null && ufw status | grep -q "active"; then
            ufw allow "$SSH_NEW_PORT"/tcp comment "SSH-new-port" 2>/dev/null
        elif command -v firewall-cmd &> /dev/null; then
            firewall-cmd --permanent --add-port="$SSH_NEW_PORT"/tcp 2>/dev/null
            firewall-cmd --reload 2>/dev/null
        fi
        echo -e "${YELLOW}  已在防火墙放行新端口 $SSH_NEW_PORT${NC}"
    fi

    # 重启 SSH（用当前连接的端口，避免断连）
    systemctl restart sshd 2>/dev/null || systemctl restart ssh 2>/dev/null

    echo -e "${GREEN}✔ SSH 加固完成${NC}"
    if [[ "$SSH_NEW_PORT" != "22" ]]; then
        echo -e "${BOLD}  ⚠ 请使用新端口连接: ssh -p $SSH_NEW_PORT root@服务器IP${NC}"
    fi
}

step10_firewall() {
    echo -e "${YELLOW}[10/14] 配置防火墙${NC}"

    # 获取当前SSH端口（可能已被step9修改）
    CURRENT_SSH_PORT=$(grep -E "^Port " /etc/ssh/sshd_config 2>/dev/null | awk '{print $2}')
    CURRENT_SSH_PORT=${CURRENT_SSH_PORT:-22}

    if [[ "$OS" == "ubuntu" || "$OS" == "debian" ]]; then
        if ! command -v ufw &> /dev/null; then
            apt install -y ufw
        fi
        ufw allow "$CURRENT_SSH_PORT"/tcp comment 'SSH'
        ufw allow 80/tcp comment 'HTTP'
        ufw allow 443/tcp comment 'HTTPS'
        ufw default deny incoming
        ufw default allow outgoing
        echo "y" | ufw enable
        echo -e "${GREEN}✔ UFW 防火墙配置完成 (SSH端口: $CURRENT_SSH_PORT)${NC}"
    elif [[ "$OS" == "centos" || "$OS" == "rhel" || "$OS" == "almalinux" || "$OS" == "rocky" ]]; then
        if ! command -v firewall-cmd &> /dev/null; then
            dnf install -y firewalld
        fi
        systemctl enable --now firewalld
        firewall-cmd --permanent --add-port="$CURRENT_SSH_PORT"/tcp
        firewall-cmd --permanent --add-service=http
        firewall-cmd --permanent --add-service=https
        firewall-cmd --reload
        echo -e "${GREEN}✔ Firewalld 防火墙配置完成 (SSH端口: $CURRENT_SSH_PORT)${NC}"
    fi
}

step11_fail2ban() {
    echo -e "${YELLOW}[11/14] 部署 Fail2Ban 防爆破${NC}"
    if [[ "$OS" == "ubuntu" || "$OS" == "debian" ]]; then
        apt install -y fail2ban
    elif [[ "$OS" == "centos" || "$OS" == "rhel" || "$OS" == "almalinux" || "$OS" == "rocky" ]]; then
        dnf install -y fail2ban
    fi
    systemctl enable --now fail2ban

    # 获取当前SSH端口
    CURRENT_SSH_PORT=$(grep -E "^Port " /etc/ssh/sshd_config 2>/dev/null | awk '{print $2}')
    CURRENT_SSH_PORT=${CURRENT_SSH_PORT:-22}

    cat > /etc/fail2ban/jail.local << F2BEOF
[DEFAULT]
bantime = 86400
findtime = 600
maxretry = 4

[sshd]
enabled = true
port = $CURRENT_SSH_PORT
maxretry = 4
bantime = 86400
findtime = 600
F2BEOF
    systemctl restart fail2ban
    echo -e "${GREEN}✔ Fail2Ban 部署完成 (监控端口: $CURRENT_SSH_PORT)${NC}"
}

step12_auto_update() {
    echo -e "${YELLOW}[12/14] 配置自动安全更新${NC}"
    if [[ "$OS" == "ubuntu" || "$OS" == "debian" ]]; then
        apt install -y unattended-upgrades apt-listchanges

        # 启用自动安全更新
        cat > /etc/apt/apt.conf.d/20auto-upgrades << 'EOF'
APT::Periodic::Update-Package-Lists "1";
APT::Periodic::Unattended-Upgrade "1";
APT::Periodic::Download-Upgradeable-Packages "1";
APT::Periodic::AutocleanInterval "7";
EOF

        # 只自动装安全更新，不自动重启
        cat > /etc/apt/apt.conf.d/50unattended-upgrades << 'EOF'
Unattended-Upgrade::Allowed-Origins {
    "${distro_id}:${distro_codename}-security";
};
Unattended-Upgrade::AutoFixInterruptedDpkg "true";
Unattended-Upgrade::Remove-Unused-Dependencies "true";
Unattended-Upgrade::Automatic-Reboot "false";
EOF

        echo -e "${GREEN}✔ 自动安全更新配置完成 (仅安全补丁，不自动重启)${NC}"
    else
        echo -e "${YELLOW}! 自动安全更新仅支持 Debian/Ubuntu，跳过${NC}"
    fi
}

step13_kernel_hardening() {
    echo -e "${YELLOW}[13/14] 内核安全加固 (sysctl)${NC}"
    cat > /etc/sysctl.d/99-security.conf << 'EOF'
# 反IP欺骗
net.ipv4.conf.all.rp_filter = 1
net.ipv4.conf.default.rp_filter = 1

# 禁用源路由
net.ipv4.conf.all.accept_source_route = 0
net.ipv4.conf.default.accept_source_route = 0

# 禁用ICMP重定向
net.ipv4.conf.all.accept_redirects = 0
net.ipv4.conf.default.accept_redirects = 0
net.ipv4.conf.all.send_redirects = 0
net.ipv4.conf.default.send_redirects = 0

# SYN flood防护
net.ipv4.tcp_syncookies = 1

# 忽略ICMP广播请求
net.ipv4.icmp_echo_ignore_broadcasts = 1

# 忽略伪造ICMP错误
net.ipv4.icmp_ignore_bogus_error_responses = 1

# 内核指针限制
kernel.kptr_restrict = 2
kernel.dmesg_restrict = 1

# 禁用SysRq
kernel.sysrq = 0

# ASLR
kernel.randomize_va_space = 2

# 保护硬链接/软链接
fs.protected_hardlinks = 1
fs.protected_symlinks = 1

# 禁用SUID程序core dump
fs.suid_dumpable = 0
EOF
    sysctl --system > /dev/null 2>&1
    echo -e "${GREEN}✔ 内核安全加固完成${NC}"
    echo -e "${YELLOW}  注意: 如需运行VPN/隧道，请将 net.ipv4.ip_forward 设为 1${NC}"
}

step14_disable_services() {
    echo -e "${YELLOW}[14/14] 禁用无用服务${NC}"

    # 禁用并卸载 snapd
    if command -v snap &> /dev/null; then
        systemctl disable --now snapd 2>/dev/null
        systemctl mask snapd 2>/dev/null
        apt purge -y snapd 2>/dev/null
        rm -rf /snap /var/snap /var/lib/snapd /usr/lib/snapd 2>/dev/null
        echo -e "${GREEN}  ✔ Snap 已卸载${NC}"
    else
        echo -e "${CYAN}  Snap 未安装，跳过${NC}"
    fi

    # 禁用 avahi-daemon (mDNS，VPS不需要)
    if systemctl is-active avahi-daemon &> /dev/null 2>&1; then
        systemctl disable --now avahi-daemon 2>/dev/null
        systemctl mask avahi-daemon 2>/dev/null
        echo -e "${GREEN}  ✔ Avahi-daemon 已禁用${NC}"
    fi

    # 禁用 cloud-init
    if [ -d /etc/cloud ]; then
        touch /etc/cloud/cloud-init.disabled
        echo -e "${GREEN}  ✔ Cloud-init 已禁用${NC}"
    fi

    # 禁用多余TTY (云服务器只需1个终端)
    for i in 2 3 4 5 6; do
        systemctl mask "getty@tty$i" 2>/dev/null
    done
    echo -e "${GREEN}  ✔ 多余TTY(tty2-6)已禁用${NC}"

    echo -e "${GREEN}✔ 无用服务清理完成${NC}"
}

# ------------------------------------------
# 系统状态报告
# ------------------------------------------

show_status() {
    echo ""
    echo -e "${CYAN}======================================${NC}"
    echo -e "${CYAN}       系统状态报告${NC}"
    echo -e "${CYAN}======================================${NC}"
    echo -e "  主机名:   $(hostname)"
    echo -e "  系统:     $PRETTY_NAME"
    echo -e "  内核:     $(uname -r)"
    echo -e "  运行时间: $(uptime -p)"
    echo -e "  CPU:      $(nproc) 核"
    echo -e "  内存:     $(free -h | awk '/^Mem:/{print $2 " 总计, " $3 " 已用, " $4 " 可用"}')"
    echo -e "  Swap:     $(free -h | awk '/^Swap:/{print $2 " 总计, " $3 " 已用"}')"
    echo -e "  磁盘:     $(df -h / | awk 'NR==2{print $2 " 总计, " $3 " 已用, " $4 " 可用 (" $5 ")"}')"
    echo -e "  SSH端口:  $(grep -E '^Port ' /etc/ssh/sshd_config 2>/dev/null | awk '{print $2}' || echo '22')"
    echo ""
    echo -e "${CYAN}  监听端口:${NC}"
    ss -tlnp 2>/dev/null | tail -n +2 | awk '{printf "    %-8s %-20s %s\n", $4, $5, $6}' | head -10
    echo ""
    echo -e "${CYAN}  运行中服务:${NC}"
    systemctl list-units --type=service --state=running --no-pager 2>/dev/null | grep "running" | awk '{printf "    %s\n", $1}' | head -15
    echo -e "${CYAN}======================================${NC}"
    echo ""
}

# ------------------------------------------
# 交互菜单
# ------------------------------------------

show_menu() {
    clear
    echo -e "${CYAN}======================================${NC}"
    echo -e "${CYAN}  VPS 初始化脚本 v2.0  系统: $OS${NC}"
    echo -e "${CYAN}======================================${NC}"
    echo ""
    echo -e "  ${BOLD}── 第一组：基础环境 ──${NC}"
    echo -e "  ${GREEN}1${NC})  系统更新 + 垃圾清理"
    echo -e "  ${GREEN}2${NC})  时区设为 Asia/Shanghai"
    echo -e "  ${GREEN}3${NC})  DNS 优化 (自动检测国内/海外)"
    echo ""
    echo -e "  ${BOLD}── 第二组：内核调优 ──${NC}"
    echo -e "  ${GREEN}4${NC})  开启 BBR 网络加速"
    echo -e "  ${GREEN}5${NC})  配置 2G Swap 虚拟内存"
    echo -e "  ${GREEN}6${NC})  IPv4 优先"
    echo ""
    echo -e "  ${BOLD}── 第三组：工具安装 ──${NC}"
    echo -e "  ${GREEN}7${NC})  安装基础工具 (vim/curl/wget/htop/pip3等)"
    echo -e "  ${GREEN}8${NC})  安装 Docker (需确认)"
    echo ""
    echo -e "  ${BOLD}── 第四组：安全加固 ──${NC}"
    echo -e "  ${GREEN}9${NC})  SSH 加固 (自定义端口/禁密码登录)"
    echo -e "  ${GREEN}10${NC}) 防火墙配置"
    echo -e "  ${GREEN}11${NC}) 部署 Fail2Ban 防爆破"
    echo -e "  ${GREEN}12${NC}) 自动安全更新"
    echo -e "  ${GREEN}13${NC}) 内核安全加固 (sysctl)"
    echo -e "  ${GREEN}14${NC}) 禁用无用服务 (Snap/cloud-init/avahi/多余TTY)"
    echo ""
    echo -e "  ${BOLD}── 其他 ──${NC}"
    echo -e "  ${GREEN}a${NC})  执行全部 (按组顺序)"
    echo -e "  ${GREEN}s${NC})  查看系统状态"
    echo -e "  ${RED}0${NC})  退出"
    echo ""
    echo -e "${CYAN}======================================${NC}"
}

run_step() {
    case $1 in
        1)  step1_update ;;
        2)  step2_timezone ;;
        3)  step3_dns ;;
        4)  step4_bbr ;;
        5)  step5_swap ;;
        6)  step6_ipv4 ;;
        7)  step7_tools ;;
        8)  step8_docker ;;
        9)  step9_ssh ;;
        10) step10_firewall ;;
        11) step11_fail2ban ;;
        12) step12_auto_update ;;
        13) step13_kernel_hardening ;;
        14) step14_disable_services ;;
    esac
    echo ""
    echo -e "${YELLOW}按回车键返回菜单...${NC}"
    read -r
}

run_all() {
    echo -e "${YELLOW}即将按组顺序执行全部 14 项初始化任务${NC}"
    echo -e "${YELLOW}执行顺序：基础环境(1-3) → 内核调优(4-6) → 工具安装(7-8) → 安全加固(9-14)${NC}"
    echo -e "${YELLOW}确认执行？(y/n)${NC}"
    read -r confirm
    if [[ "$confirm" != "y" && "$confirm" != "Y" ]]; then
        echo -e "${RED}已取消${NC}"
        return
    fi

    echo ""
    echo -e "${BOLD}── 第一组：基础环境 ──${NC}"
    for i in 1 2 3; do run_step $i; echo ""; done

    echo -e "${BOLD}── 第二组：内核调优 ──${NC}"
    for i in 4 5 6; do run_step $i; echo ""; done

    echo -e "${BOLD}── 第三组：工具安装 ──${NC}"
    for i in 7 8; do run_step $i; echo ""; done

    echo -e "${BOLD}── 第四组：安全加固 ──${NC}"
    for i in 9 10 11 12 13 14; do run_step $i; echo ""; done

    echo -e "${GREEN}======================================${NC}"
    echo -e "${GREEN} 全部 14 项初始化任务执行完毕！${NC}"
    echo -e "${GREEN}======================================${NC}"
    show_status
}

# 主循环
while true; do
    show_menu
    read -rp "请选择 [1-14/a/s/0]: " choice
    case $choice in
        [1-9]|1[0-4]) run_step "$choice" ;;
        a|A)           run_all ;;
        s|S)           show_status; echo -e "${YELLOW}按回车键返回菜单...${NC}"; read -r ;;
        0|q|Q)         echo -e "${GREEN}再见${NC}"; exit 0 ;;
        *)             echo -e "${RED}无效选择${NC}"; sleep 1 ;;
    esac
done
