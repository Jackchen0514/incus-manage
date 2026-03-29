# Incus Manager API

基于 FastAPI + pylxd 构建的 LXD/Incus 容器管理系统，提供完整的 RESTful API 接口。

---

## 目录

- [快速开始](#快速开始)
- [项目结构](#项目结构)
- [配置说明](#配置说明)
- [API 文档](#api-文档)
- [认证方式](#认证方式)
- [接口列表](#接口列表)
- [使用示例](#使用示例)
- [运行测试](#运行测试)
- [注意事项](#注意事项)

---

## 快速开始

### 环境要求

- Python 3.8+
- LXD (snap 安装) 或 Incus
- root 权限（访问 LXD unix socket）

### 安装依赖

```bash
pip3 install -r requirements.txt
```

### 启动服务

```bash
# 默认端口 5000
./start.sh

# 自定义端口
PORT=8888 ./start.sh

# 修改管理员密码
ADMIN_PASSWORD=yourpassword ./start.sh
```

### 访问文档

| 地址 | 说明 |
|------|------|
| `http://localhost:5000/docs` | Swagger UI 交互文档 |
| `http://localhost:5000/redoc` | ReDoc 文档 |
| `http://localhost:5000/health` | 健康检查 |

---

## 项目结构

```
incus/
├── main.py                    # FastAPI 应用入口，注册所有路由
├── start.sh                   # 启动脚本
├── requirements.txt           # Python 依赖
├── .env.example               # 环境变量示例
├── app/
│   ├── core/
│   │   ├── config.py          # 配置项（读取环境变量）
│   │   ├── security.py        # JWT 生成/验证，权限依赖
│   │   └── users.py           # 内存用户存储（可替换为数据库）
│   ├── routers/
│   │   ├── auth.py            # 登录、用户 CRUD
│   │   ├── instances.py       # 容器/VM 生命周期管理
│   │   ├── images.py          # 镜像管理
│   │   ├── networks.py        # 网络管理
│   │   ├── storage.py         # 存储池和卷管理
│   │   ├── profiles.py        # Profile 管理
│   │   ├── snapshots.py       # 快照管理
│   │   └── system.py          # 系统信息和资源
│   └── services/
│       └── lxd_client.py      # pylxd 客户端单例封装
└── tests/
    └── test_api.py            # pytest 集成测试
```

---

## 配置说明

复制 `.env.example` 为 `.env` 并修改：

```bash
cp .env.example .env
```

| 环境变量 | 默认值 | 说明 |
|----------|--------|------|
| `SECRET_KEY` | `change-this-...` | JWT 签名密钥，**生产环境必须修改** |
| `ADMIN_PASSWORD` | `admin123` | 初始管理员密码 |
| `LXD_SOCKET` | `/var/snap/lxd/common/lxd/unix.socket` | LXD Unix socket 路径 |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `1440` (24h) | Token 有效期（分钟） |
| `DEBUG` | `false` | 调试模式 |

**Incus（非 snap）的 socket 路径：**
```
LXD_SOCKET=/var/lib/incus/unix.socket
```

---

## API 文档

### 认证方式

所有 API（除登录外）均需 Bearer Token 认证。

**Step 1：登录获取 Token**
```bash
curl -X POST http://localhost:5000/api/v1/auth/token \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=admin&password=admin123"
```

返回：
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer"
}
```

**Step 2：携带 Token 调用 API**
```bash
curl http://localhost:5000/api/v1/instances \
  -H "Authorization: Bearer <access_token>"
```

---

## 接口列表

### 认证 `/api/v1/auth`

| 方法 | 路径 | 权限 | 说明 |
|------|------|------|------|
| POST | `/token` | 公开 | 登录，获取 JWT |
| GET | `/me` | 登录用户 | 查看当前用户信息 |
| GET | `/users` | admin | 列出所有用户 |
| POST | `/users` | admin | 创建用户 |
| DELETE | `/users/{username}` | admin | 删除用户 |

### 实例 `/api/v1/instances`

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/` | 列出所有容器/VM |
| POST | `/` | 创建实例 |
| GET | `/{name}` | 获取实例详情 |
| DELETE | `/{name}` | 删除实例 |
| POST | `/{name}/start` | 启动 |
| POST | `/{name}/stop` | 停止（`?force=true` 强制） |
| POST | `/{name}/restart` | 重启 |
| POST | `/{name}/freeze` | 暂停（冻结） |
| POST | `/{name}/unfreeze` | 恢复（解冻） |
| POST | `/{name}/exec` | 在实例内执行命令 |
| GET | `/{name}/state` | 获取 CPU/内存/网络/磁盘状态 |
| PATCH | `/{name}/config` | 更新实例配置 |

### 镜像 `/api/v1/images`

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/` | 列出本地镜像 |
| GET | `/{fingerprint}` | 获取镜像详情 |
| POST | `/copy` | 从远程服务器下载镜像 |
| DELETE | `/{fingerprint}` | 删除本地镜像 |

### 网络 `/api/v1/networks`

| 方法 | 路径 | 权限 | 说明 |
|------|------|------|------|
| GET | `/` | 登录用户 | 列出所有网络 |
| GET | `/{name}` | 登录用户 | 获取网络详情 |
| POST | `/` | admin | 创建网络 |
| DELETE | `/{name}` | admin | 删除网络 |

### 存储 `/api/v1/storage`

| 方法 | 路径 | 权限 | 说明 |
|------|------|------|------|
| GET | `/pools` | 登录用户 | 列出存储池 |
| GET | `/pools/{pool}` | 登录用户 | 存储池详情 |
| POST | `/pools` | admin | 创建存储池 |
| DELETE | `/pools/{pool}` | admin | 删除存储池 |
| GET | `/pools/{pool}/volumes` | 登录用户 | 列出卷 |
| POST | `/pools/{pool}/volumes` | 登录用户 | 创建卷 |
| DELETE | `/pools/{pool}/volumes/{type}/{name}` | 登录用户 | 删除卷 |

### Profile `/api/v1/profiles`

| 方法 | 路径 | 权限 | 说明 |
|------|------|------|------|
| GET | `/` | 登录用户 | 列出 profiles |
| GET | `/{name}` | 登录用户 | 获取详情 |
| POST | `/` | admin | 创建 profile |
| PUT | `/{name}` | admin | 更新 profile |
| DELETE | `/{name}` | admin | 删除 profile |

### 快照 `/api/v1/instances/{name}/snapshots`

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/` | 列出快照 |
| POST | `/` | 创建快照 |
| POST | `/{snapshot}/restore` | 恢复快照 |
| DELETE | `/{snapshot}` | 删除快照 |

### 系统 `/api/v1/system`

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/info` | LXD 版本、驱动、架构、资源信息 |
| GET | `/resources` | 主机 CPU/内存详细数据 |

---

## 使用示例

### 创建并启动一个容器

```bash
BASE=http://localhost:5000
TOKEN=$(curl -s -X POST $BASE/api/v1/auth/token \
  -d "username=admin&password=admin123" | python3 -c "import sys,json;print(json.load(sys.stdin)['access_token'])")

# 创建容器
curl -s -X POST $BASE/api/v1/instances \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name": "mycontainer", "image": "ubuntu:22.04"}'

# 启动容器
curl -s -X POST $BASE/api/v1/instances/mycontainer/start \
  -H "Authorization: Bearer $TOKEN"

# 执行命令
curl -s -X POST $BASE/api/v1/instances/mycontainer/exec \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"command": ["hostname"]}'
```

### 创建快照并恢复

```bash
# 创建快照
curl -s -X POST $BASE/api/v1/instances/mycontainer/snapshots \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name": "snap1"}'

# 恢复快照
curl -s -X POST $BASE/api/v1/instances/mycontainer/snapshots/snap1/restore \
  -H "Authorization: Bearer $TOKEN"
```

### 创建普通用户

```bash
curl -s -X POST $BASE/api/v1/auth/users \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"username": "alice", "password": "alice123", "is_admin": false}'
```

---

## 运行测试

```bash
python3 -m pytest tests/ -v
```

测试覆盖：认证流程、权限控制、实例/网络/镜像/存储/Profile/系统信息等 17 个场景。

---

## 注意事项

1. **生产环境安全**：修改 `SECRET_KEY` 和 `ADMIN_PASSWORD`，不要使用默认值
2. **持久化用户**：当前用户存储在内存中，重启后清空，生产环境应替换为数据库（SQLite/PostgreSQL）
3. **权限**：服务进程需要访问 LXD unix socket，通常需要 root 或 lxd 组成员
4. **CORS**：默认允许所有来源，生产环境应在 `main.py` 中限制 `allow_origins`
5. **Incus vs LXD**：Incus 的 socket 路径为 `/var/lib/incus/unix.socket`，通过 `LXD_SOCKET` 环境变量配置
