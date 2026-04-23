#!/bin/bash
# ==========================================
# 纯净版 VPS 初始化脚本 (交互菜单版)
# 实现：更新、时区、DNS、BBR、Swap、IPv4优先、防火墙、防爆破
# ==========================================

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
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
# 功能函数
# ------------------------------------------

step1_update() {
    echo -e "${YELLOW}[1/8] 正在更新系统组件并清理...${NC}"
    if [[ "$OS" == "ubuntu" || "$OS" == "debian" ]]; then
        apt update -y && apt upgrade -y && apt autoremove -y
    elif [[ "$OS" == "centos" || "$OS" == "rhel" || "$OS" == "almalinux" || "$OS" == "rocky" ]]; then
        dnf upgrade -y && dnf autoremove -y
    else
        echo -e "${RED}不支持的系统，跳过更新${NC}"
        return 1
    fi
    echo -e "${GREEN}✔ 系统更新完成${NC}"
}

step2_timezone() {
    echo -e "${YELLOW}[2/8] 正在设置时区为 Asia/Shanghai 并开启 NTP...${NC}"
    timedatectl set-timezone Asia/Shanghai
    timedatectl set-ntp true
    echo -e "${GREEN}✔ 时区设置完成${NC}"
}

step3_dns() {
    echo -e "${YELLOW}[3/8] 正在优化 DNS 设置...${NC}"
    cp /etc/resolv.conf /etc/resolv.conf.bak
    cat > /etc/resolv.conf << 'DNS_EOF'
nameserver 1.1.1.1
nameserver 8.8.8.8
DNS_EOF
    # 锁定防篡改（无论是否有nmcli，DHCP都可能覆盖）
    chattr +i /etc/resolv.conf 2>/dev/null || true
    echo -e "${GREEN}✔ DNS 设置完成 (已锁定防篡改，如需修改请先 chattr -i /etc/resolv.conf)${NC}"
}

step4_bbr() {
    echo -e "${YELLOW}[4/8] 正在配置 BBR 网络加速...${NC}"
    cat > /etc/sysctl.d/99-bbr.conf << 'BBR_EOF'
net.core.default_qdisc=fq
net.ipv4.tcp_congestion_control=bbr
BBR_EOF
    sysctl --system > /dev/null 2>&1
    if sysctl net.ipv4.tcp_congestion_control 2>/dev/null | grep -q bbr; then
        echo -e "${GREEN}✔ BBR 已生效${NC}"
    else
        echo -e "${YELLOW}✔ BBR 配置已写入，重启后生效${NC}"
    fi
}

step5_swap() {
    echo -e "${YELLOW}[5/8] 正在配置 2G 虚拟内存...${NC}"
    if [ ! -f /swapfile ]; then
        # dd 比 fallocate 兼容性更好（ZFS/Btrfs等）
        dd if=/dev/zero of=/swapfile bs=1M count=2048 status=progress
        chmod 600 /swapfile
        mkswap /swapfile > /dev/null
        swapon /swapfile
        if ! grep -q '/swapfile' /etc/fstab; then
            echo '/swapfile none swap sw 0 0' >> /etc/fstab
        fi
        cat > /etc/sysctl.d/99-swappiness.conf << 'SWAP_EOF'
vm.swappiness=10
SWAP_EOF
        sysctl --system > /dev/null 2>&1
        echo -e "${GREEN}✔ 2G Swap 配置完成${NC}"
    else
        echo -e "${YELLOW}! 检测到 Swap 已存在，跳过${NC}"
    fi
}

step6_ipv4() {
    echo -e "${YELLOW}[6/8] 正在设置 IPv4 优先...${NC}"
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

step7_firewall() {
    echo -e "${YELLOW}[7/8] 正在配置防火墙...${NC}"
    if [[ "$OS" == "ubuntu" || "$OS" == "debian" ]]; then
        if ! command -v ufw &> /dev/null; then
            apt install -y ufw
        fi
        ufw allow 22/tcp comment 'SSH'
        ufw allow 80/tcp comment 'HTTP'
        ufw allow 443/tcp comment 'HTTPS'
        ufw default deny incoming
        ufw default allow outgoing
        echo "y" | ufw enable
        echo -e "${GREEN}✔ UFW 防火墙配置完成${NC}"
    elif [[ "$OS" == "centos" || "$OS" == "rhel" || "$OS" == "almalinux" || "$OS" == "rocky" ]]; then
        if ! command -v firewall-cmd &> /dev/null; then
            dnf install -y firewalld
        fi
        systemctl enable --now firewalld
        firewall-cmd --permanent --add-service=ssh
        firewall-cmd --permanent --add-service=http
        firewall-cmd --permanent --add-service=https
        firewall-cmd --reload
        echo -e "${GREEN}✔ Firewalld 防火墙配置完成${NC}"
    fi
}

step8_fail2ban() {
    echo -e "${YELLOW}[8/8] 正在部署 Fail2Ban...${NC}"
    if [[ "$OS" == "ubuntu" || "$OS" == "debian" ]]; then
        apt install -y fail2ban
    elif [[ "$OS" == "centos" || "$OS" == "rhel" || "$OS" == "almalinux" || "$OS" == "rocky" ]]; then
        dnf install -y fail2ban
    fi
    systemctl enable --now fail2ban
    cat > /etc/fail2ban/jail.local << 'F2B_EOF'
[DEFAULT]
bantime = 86400
findtime = 600
maxretry = 4

[sshd]
enabled = true
port = 22
maxretry = 4
bantime = 86400
findtime = 600
F2B_EOF
    systemctl restart fail2ban
    echo -e "${GREEN}✔ Fail2Ban 部署完成${NC}"
}

# ------------------------------------------
# 交互菜单
# ------------------------------------------

show_menu() {
    clear
    echo -e "${CYAN}======================================${NC}"
    echo -e "${CYAN}   VPS 初始化脚本  系统: $OS${NC}"
    echo -e "${CYAN}======================================${NC}"
    echo ""
    echo -e "  ${GREEN}1${NC})  系统更新与清理"
    echo -e "  ${GREEN}2${NC})  时区设为 Asia/Shanghai + NTP"
    echo -e "  ${GREEN}3${NC})  DNS 优化 (1.1.1.1 / 8.8.8.8)"
    echo -e "  ${GREEN}4${NC})  开启 BBR 网络加速"
    echo -e "  ${GREEN}5${NC})  配置 2G Swap 虚拟内存"
    echo -e "  ${GREEN}6${NC})  IPv4 优先"
    echo -e "  ${GREEN}7${NC})  防火墙配置 (UFW/Firewalld)"
    echo -e "  ${GREEN}8${NC})  部署 Fail2Ban 防爆破"
    echo ""
    echo -e "  ${GREEN}a${NC})  执行全部"
    echo -e "  ${RED}0${NC})  退出"
    echo ""
    echo -e "${CYAN}======================================${NC}"
}

run_step() {
    case $1 in
        1) step1_update ;;
        2) step2_timezone ;;
        3) step3_dns ;;
        4) step4_bbr ;;
        5) step5_swap ;;
        6) step6_ipv4 ;;
        7) step7_firewall ;;
        8) step8_fail2ban ;;
    esac
    echo ""
    echo -e "${YELLOW}按回车键返回菜单...${NC}"
    read -r
}

run_all() {
    echo -e "${YELLOW}即将执行全部 8 项初始化任务...${NC}"
    echo -e "${YELLOW}确认执行？(y/n)${NC}"
    read -r confirm
    if [[ "$confirm" != "y" && "$confirm" != "Y" ]]; then
        echo -e "${RED}已取消${NC}"
        return
    fi
    for i in 1 2 3 4 5 6 7 8; do
        run_step $i
    done
    echo -e "${GREEN}======================================${NC}"
    echo -e "${GREEN} 全部 8 项初始化任务执行完毕！${NC}"
    echo -e "${GREEN}======================================${NC}"
}

# 主循环
while true; do
    show_menu
    read -rp "请选择 [1-8/a/0]: " choice
    case $choice in
        [1-8]) run_step "$choice" ;;
        a|A)   run_all ;;
        0|q|Q) echo -e "${GREEN}再见${NC}"; exit 0 ;;
        *)     echo -e "${RED}无效选择${NC}"; sleep 1 ;;
    esac
done
