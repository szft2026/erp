# H5ERP 进销存（PC 端）

进销存管理后台。原 **PHP 5.6 + CodeIgniter 2.2.5**，已升级到 **PHP 8.2 + Apache**，做成 Docker 镜像。

功能：基础资料、采购/销售/调拨/收付款/其他出入库/成本调整/销售订单、库存、51 个报表、PDF 打印、Excel 导入导出、数据库备份恢复、用户权限。

---

## 快速开始

```bash
git clone git@github.com:szft2026/erp.git
cd erp

cp .env.example .env        # 按需改 DB_PASSWORD / DB_DATABASE

docker compose up -d --build
```

打开 <http://localhost:8080>，账号 `admin / admin888`。

首次启动会自动建库并导入 `erp.sql`（25 张表 + 管理员 + 菜单）。

> 不用 Docker、想直接装在 Apache / Nginx 上？见 **[DEPLOY-php-server.md](DEPLOY-php-server.md)**。

---

## 配置（`.env`）

| 变量 | 默认 | 说明 |
|---|---|---|
| `DB_PASSWORD` | `root123` | MySQL root 密码，也是应用连库的密码 |
| `DB_DATABASE` | `erp` | 库名 |
| `AUTO_INIT_SCHEMA` | `1` | 空库自动建表；库里有数据设 `0` |
| `DB_DEBUG` | `1` | `0` = 页面不显示 SQL 错误（正式环境建议 0） |

`DB_PASSWORD` 只在 **`db-data` 卷第一次创建时**生效；库已初始化后再改 `.env`，MySQL 里的密码不会跟着变。

---

## 升级

```bash
cd erp
docker compose down

cd ..
mv erp erp_old                    # 旧目录先留着（里面有 .env）
git clone git@github.com:szft2026/erp.git
cp erp_old/.env erp/.env          # 配置带回来

cd erp
docker compose up -d --build
```

- 数据库和上传文件在 Docker 卷 `db-data` / `app-data` 里，**删目录、重新克隆都不影响数据**
- 不想重新克隆也可以：`git pull` 后直接 `docker compose up -d --build`
- 升级前建议备份：系统内「设置 → 备份与恢复」，或
  `docker exec h5erp-db sh -c 'exec mysqldump -uroot -p"$MYSQL_ROOT_PASSWORD" "$MYSQL_DATABASE"' > backup.sql`
- `erp.sql` 只在空库首次初始化时导入，升级**不会自动改已有表结构**；有新字段按发布说明手工 `ALTER`

---

## 用你自己的 MySQL

```bash
cp .env.example .env
```

`.env` 里填：

```env
DB_HOST=10.0.0.5
DB_PORT=3306
DB_DATABASE=erp
DB_USERNAME=erp
DB_PASSWORD=你的密码
AUTO_INIT_SCHEMA=0
```

启动（只起应用，不起 MySQL）：

```bash
docker compose -f docker-compose.external.yml up -d --build
```

数据库要提前准备好：

```sql
CREATE DATABASE erp DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci;
CREATE USER 'erp'@'%' IDENTIFIED BY '你的强密码';
GRANT ALL PRIVILEGES ON erp.* TO 'erp'@'%';
FLUSH PRIVILEGES;
```

- 版本：MySQL 5.7+/8.0 或 MariaDB 10.4+，不支持 PostgreSQL
- 账号要能从容器所在机器访问（安全组 / `user@'%'`）
- 库是空的就把 `AUTO_INIT_SCHEMA` 设 `1`，会自动导入 `erp.sql`

---

## 首次登录后

1. `admin / admin888` 登录，**先改密码**
2. 按顺序建基础资料，否则开单会选不到东西：

```
商品分类 → 计量单位 → 仓库（状态正常）→ 结算账户 → 客户/供应商 → 商品
```

3. 采购入库 → 审核 → 库存增加 → 销货出库 → 审核 → 打印 PDF

---

## 常见问题

| 现象 | 处理 |
|---|---|
| 页面 502 / 白屏 | `docker compose logs app`，多半是数据库连不上 |
| 登录提示账号密码错误 | `ci_admin.userpwd` 必须是 32 位 md5 |
| 页面能开但点不动 | `pc/index.php` 的 `ENVIRONMENT` 必须是 `production`（仓库里已固定） |
| 报表/打印 500 | 确认镜像是最新代码（重新 `up -d --build`） |
| 中文乱码 | 库/表字符集用 `utf8` 或 `utf8mb4` |

---

## 文档

- [DOCKER.md](DOCKER.md) — Docker 运行细节
- [DEPLOY-blitz.md](DEPLOY-blitz.md) — 部署到 blitz.cloud
- [DEPLOY-php-server.md](DEPLOY-php-server.md) — 直接装在 Apache / Nginx 上（不用 Docker）
- [docs/API-接口文档.md](docs/API-接口文档.md) — 43 个控制器 / 355 个接口
- [docs/PHP8-升级说明.md](docs/PHP8-升级说明.md) — PHP 5.6 → 8.2 改动清单
