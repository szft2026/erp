<?php
/**
 * 非 Docker 部署（Apache / Nginx + PHP-FPM）用的 prepend 脚本。
 *
 * 代码里大量使用 ./data/... 、./application/libraries/... 这类相对路径，
 * 依赖进程的工作目录 = 站点根（pc/）。Docker 镜像里用 deploy/prepend.php 写死了
 * /var/www/html；直接装在 PHP 服务器上路径不同，所以这里按 DOCUMENT_ROOT 动态取。
 *
 * 用法（任选一种）：
 *   1) php.ini / php-fpm pool：auto_prepend_file = /var/www/h5erp/pc/prepend-server.php
 *   2) Nginx + PHP-FPM：直接在 pool 里写 chdir = /var/www/h5erp/pc，不需要本文件
 */

if (PHP_SAPI === 'cli') {
    return;
}

$root = isset($_SERVER['DOCUMENT_ROOT']) ? realpath($_SERVER['DOCUMENT_ROOT']) : '';

if ($root && getcwd() !== $root) {
    @chdir($root);
}
