# 直接部署到 PHP 服务器（Apache / Nginx，不用 Docker）

适用于已有 LAMP / LNMP 环境、想直接把代码放上去跑的场景。

Docker 里由镜像的入口脚本完成的三件事，这里要手工做：**导入表结构**、**固定工作目录**、**配置目录权限**。

---

## 1. 环境要求

| 项 | 要求 |
|---|---|
| PHP | **8.2**（最低 8.0，建议 8.2） |
| 扩展 | `mysqli`、`pdo_mysql`、`gd`（含 freetype/jpeg）、`zip`、`mbstring`、`iconv`、`curl`、`json`、`openssl`、`session` |
| 数据库 | MySQL 5.7+/8.0 或 MariaDB 10.4+ |
| Web | Apache 2.4（mod_php）或 Nginx + PHP-FPM |
| 磁盘 | 代码约 60MB，另加附件空间 |

检查：

```bash
php -v
php -m | grep -E 'mysqli|pdo_mysql|gd|zip|mbstring|iconv'
```

---

## 2. 放代码

```bash
cd /var/www
git clone git@github.com:szft2026/erp.git h5erp
```

**站点根必须是 `pc/`**，不要指向仓库根目录：

```
/var/www/h5erp/           ← 代码目录，不在 web 根
└── pc/                   ← 这才是 DocumentRoot
```

仓库根有 `erp.sql`、`Dockerfile`，暴露到公网等于把库结构和构建脚本公开。

---

## 3. 建库并导入表结构

```sql
CREATE DATABASE erp DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci;
CREATE USER 'erp'@'localhost' IDENTIFIED BY '你的强密码';
GRANT ALL PRIVILEGES ON erp.* TO 'erp'@'localhost';
FLUSH PRIVILEGES;
```

```bash
mysql -u erp -p erp < /var/www/h5erp/erp.sql
```

**这一步不能省。** Docker 里由入口脚本自动导入；直接部署没有入口脚本，不导入的话登录会直接报数据库错误。

导入后应有 25 张 `ci_` 表，`ci_admin` 里有 `admin`（密码 `admin888`）。

---

## 4. 配数据库连接

应用从环境变量读连接参数（`DB_HOST` / `DB_PORT` / `DB_DATABASE` / `DB_USERNAME` / `DB_PASSWORD`，也认 `DATABASE_URL`、`MYSQL_*`），都没设时用 `localhost` / `3306` / `erp` / `root` / `root`。

**方式 A：改配置文件（最简单）**

直接改 `pc/application/config/database.php` 里的默认值，或保留默认、用下面的环境变量。

**方式 B：环境变量**

Apache（VirtualHost 里）：

```apache
SetEnv DB_HOST 127.0.0.1
SetEnv DB_PORT 3306
SetEnv DB_DATABASE erp
SetEnv DB_USERNAME erp
SetEnv DB_PASSWORD 你的密码
```

Nginx + PHP-FPM（pool 配置里）：

```ini
env[DB_HOST] = 127.0.0.1
env[DB_DATABASE] = erp
env[DB_USERNAME] = erp
env[DB_PASSWORD] = 你的密码
clear_env = no
```

---

## 5. 关键一步：固定工作目录

代码里大量使用 `./data/...`、`./application/libraries/...` 这类**相对路径**，而 `pc/index.php` 只在 CLI 模式下 `chdir`，Web 请求不会。所以必须把进程的工作目录钉到 `pc/`。

**Nginx + PHP-FPM（推荐，一行搞定）**

pool 配置：

```ini
chdir = /var/www/h5erp/pc
```

**Apache（mod_php）**

把 `deploy/prepend-server.php` 复制到站点根：

```bash
cp /var/www/h5erp/deploy/prepend-server.php /var/www/h5erp/pc/
```

VirtualHost 里加：

```apache
php_admin_value auto_prepend_file /var/www/h5erp/pc/prepend-server.php
```

**不做这步的症状**：Excel 导入提示文件打不开、打印报错、部分页面提示路径不存在。

---

## 6. 目录权限

```bash
cd /var/www/h5erp/pc
chown -R www-data:www-data data/upfile application/cache application/logs
chmod -R 775 data/upfile application/cache application/logs
```

其余文件保持只读即可（`www-data` 只需要读）。

---

## 7. 访问保护

仓库里已经带了两个：

- `pc/application/.htaccess`、`pc/system/.htaccess` → `Deny from all`（Apache 需要 `mod_access_compat`，Debian/Ubuntu 默认开启）

还缺一个，复制过去：

```bash
cp /var/www/h5erp/deploy/download.htaccess /var/www/h5erp/pc/data/download/.htaccess
```

Nginx 不认 `.htaccess`，要在 server 块里 deny（见下一节）。

---

## 8. Apache 示例

```apache
<VirtualHost *:80>
    ServerName erp.example.com
    DocumentRoot /var/www/h5erp/pc

    <Directory /var/www/h5erp/pc>
        Options -Indexes +FollowSymLinks
        AllowOverride All
        Require all granted
        DirectoryIndex index.php
    </Directory>

    php_admin_value auto_prepend_file /var/www/h5erp/pc/prepend-server.php
    php_value upload_max_filesize 64M
    php_value post_max_size 64M
    php_value memory_limit 256M
    php_value max_execution_time 120
    php_value date.timezone Asia/Shanghai

    ErrorLog  ${APACHE_LOG_DIR}/h5erp-error.log
    CustomLog ${APACHE_LOG_DIR}/h5erp-access.log combined
</VirtualHost>
```

```bash
a2enmod rewrite
systemctl reload apache2
```

HTTPS 用 certbot 签一张证书挂到同一个 VirtualHost 即可。

---

## 9. Nginx + PHP-FPM 示例

```nginx
server {
    listen 80;
    server_name erp.example.com;
    root /var/www/h5erp/pc;
    index index.php;

    client_max_body_size 64m;

    # 源码、数据目录不对外
    location ^~ /application/ { deny all; }
    location ^~ /system/      { deny all; }
    location ^~ /data/download/ { deny all; }

    location / {
        try_files $uri $uri/ /index.php?$query_string;
    }

    location ~ \.php($|/) {
        fastcgi_split_path_info ^(.+\.php)(/.+)$;
        fastcgi_pass unix:/run/php/php8.2-fpm.sock;
        fastcgi_param SCRIPT_FILENAME $document_root$fastcgi_script_name;
        fastcgi_param PATH_INFO $fastcgi_path_info;
        include fastcgi_params;
    }
}
```

`/etc/php/8.2/fpm/pool.d/www.conf` 里加：

```ini
chdir = /var/www/h5erp/pc
clear_env = no
env[DB_HOST] = 127.0.0.1
env[DB_DATABASE] = erp
env[DB_USERNAME] = erp
env[DB_PASSWORD] = 你的密码
```

```bash
systemctl reload php8.2-fpm nginx
```

`PATH_INFO` 那两行不能少，否则 `/index.php/scm/invSa` 这种地址会 404。

---

## 10. 首次访问

打开 `http://erp.example.com`，用 `admin / admin888` 登录，**先改密码**，然后按顺序建基础资料：

```
商品分类 → 计量单位 → 仓库（状态正常）→ 结算账户 → 客户/供应商 → 商品
```

---

## 11. 升级

```bash
cd /var/www/h5erp
git pull

# 如果有表结构变更，按发布说明执行 ALTER（erp.sql 不会自动改已有表）
# 清一下缓存（可选）
rm -rf pc/application/cache/*
```

一般不需要重启；改过 `php.ini` / FPM pool 才需要 reload。

升级前建议备份：

```bash
mysqldump -u erp -p erp > backup_$(date +%F).sql
tar czf upfile_$(date +%F).tgz -C pc/data upfile
```

---

## 12. 排查

| 现象 | 原因 / 处理 |
|---|---|
| 500，页面空白 | 看 `h5erp-error.log` 或 `php-fpm.log`；`pc/index.php` 的 `ENVIRONMENT` 必须是 `production` |
| 登录报数据库错误 | `erp.sql` 没导入，或 `DB_*` 没生效（Apache 用 `SetEnv`、FPM 要 `clear_env = no`） |
| 上传报 413 / 上传失败 | `client_max_body_size`（Nginx）、`post_max_size` / `upload_max_filesize`（PHP） |
| Excel 导入/打印提示路径不存在 | 第 5 步的工作目录没固定 |
| 打开是目录列表或能看到源码 | `AllowOverride` 没开，或 Nginx 没配 deny |
| `/index.php/xxx` 404 | Nginx 缺 `PATH_INFO` 参数 |
| 报表/打印 500 | 确认代码是最新的（这些缺陷已在仓库里修掉） |
| 中文乱码 | 库/表字符集用 `utf8` 或 `utf8mb4`，连接不要指定 latin1 |

---

## 与 Docker 部署的差异

| 项 | Docker | 直接部署 |
|---|---|---|
| 建表 | 入口脚本自动导入 `erp.sql` | **手工 `mysql < erp.sql`** |
| 工作目录 | 镜像里 `auto_prepend_file=/var/www/html/prepend.php` | **FPM `chdir` 或 `prepend-server.php`** |
| 权限 | 构建时 `chown www-data` | **手工 `chown` 三个目录** |
| 端口 | 容器 8080 | 80/443，由 Apache/Nginx 决定 |
| 升级 | 重新 build 镜像 | `git pull` |
