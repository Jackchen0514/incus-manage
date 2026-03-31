# Incus Manager API — Systemd 服务安装说明

## 1. 复制服务文件

```bash
cp /root/workspace/incus/incus-manager.service /etc/systemd/system/
```

## 2. 重载 systemd 配置

```bash
systemctl daemon-reload
```

## 3. 开机自启 + 立即启动

```bash
systemctl enable --now incus-manager
```

## 4. 常用管理命令

```bash
# 查看运行状态
systemctl status incus-manager

# 启动 / 停止 / 重启
systemctl start incus-manager
systemctl stop incus-manager
systemctl restart incus-manager

# 实时查看日志
journalctl -u incus-manager -f

# 查看最近 100 行日志
journalctl -u incus-manager -n 100
```
