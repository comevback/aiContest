**WSL + PostgreSQL + Redmine 6.1（Rails 6.1 / Ruby 3.0–3.2）**
（√ 标注为首次/偶尔需要；★ 为每天启动常用）

---

# 一次性准备（首装/重装时做一次） √

1. 系统与依赖

```bash
sudo apt update
sudo apt install -y build-essential libpq-dev postgresql postgresql-contrib git pkg-config
```

2. 数据库创建（PostgreSQL）

```bash
sudo service postgresql start
sudo -u postgres psql <<'SQL'
CREATE ROLE redmine LOGIN ENCRYPTED PASSWORD 'redminepass';
CREATE DATABASE redmine WITH ENCODING='UTF8' OWNER=redmine;
ALTER DATABASE redmine SET default_transaction_isolation TO 'read committed';
SQL
# 如需密码方式登录，pg_hba.conf 中靠前加入：
# local all redmine                       md5
# host  all redmine 127.0.0.1/32          md5
sudo service postgresql restart
```

3. Redmine 目录准备（假设在 ~/redmine）

* `config/database.yml`（只保留 production）：

```yaml
production:
  adapter: postgresql
  database: redmine
  host: 127.0.0.1
  username: redmine
  password: "redminepass"
  encoding: unicode
  pool: 10
```

4. Bundler 安装与数据库驱动（只装 pg）

```bash
gem install bundler
bundle config set --local with 'postgresql'
bundle config set --local without 'development test mysql sqlite'
bundle config set build.pg "--with-pg-config=/usr/bin/pg_config"
bundle install
```

5. 服务器与兼容项（推荐）

* `Gemfile` 中**确保**有（且只出现一次）：

```ruby
gem 'puma', '~> 6.4'      # 生产 Web 服务器
```

* 兼容 Ruby 3.2 上的 Logger 预加载（任选其一，二选一即可）
  A. 在 `bin/rails` shebang 后一行与 `config/boot.rb` 顶部加入：

  ```ruby
  require 'logger'
  ```

  B. 启动命令临时加环境变量：`RUBYOPT='-rlogger'`

6. 首次初始化（只做一次）

```bash
RAILS_ENV=production bundle exec rake generate_secret_token
RAILS_ENV=production bundle exec rake db:migrate
RAILS_ENV=production bundle exec rake redmine:load_default_data   # 选 en 或 zh
# Redmine 6.1 一般不需要 assets:precompile，可跳过
```

---

# 每次启动（日常） ★

在 `~/redmine`：

```bash
# 方式1：Rails 命令（自动用 Puma）
bundle exec rails s -e production -b 0.0.0.0 -p 3000
# 若遇到 Logger 未加载：
# RUBYOPT='-rlogger' bundle exec rails s -e production -b 0.0.0.0 -p 3000
```

浏览器访问：`http://localhost:3000`
初始账号：`admin / admin`

---

# 停止 / 重启 / 后台运行（可选）

* 前台启动时：`Ctrl + C` 停止
* 后台（daemon）用 Puma（需准备日志和 pid 目录）：

```bash
mkdir -p tmp/pids tmp/sockets log
RAILS_ENV=production bundle exec puma -b tcp://0.0.0.0:3000 -d \
  --pidfile tmp/pids/puma.pid -S tmp/pids/puma.state \
  --redirect-stdout log/puma.stdout.log --redirect-stderr log/puma.stderr.log
# 停止：
bundle exec pumactl -S tmp/pids/puma.state stop
```

---

# 快速排错手册（遇错优先看这里）

1. 连不上 DB

   * 用 TCP 测试：`psql -U redmine -h 127.0.0.1 -d redmine -W`
   * `pg_hba.conf` 里有 `md5` 规则，改后 `sudo service postgresql restart`
   * `config/database.yml` 的 `adapter: postgresql`、`encoding: unicode`

2. Bundler 硬装 `mysql2`

   * **原因**：`database.yml` 某段 `adapter: mysql2`
   * **解**：删掉非 PG 段，只留 production：postgresql；然后

     ```bash
     bundle clean --force && bundle install
     ```

3. `ActiveSupport::... Logger (NameError)`

   * **解**：按上面的 Logger 预加载（修改 `bin/rails` / `config/boot.rb` 或用 `RUBYOPT='-rlogger'`）

4. `invalid value for parameter "client_encoding": "utf8mb4"`

   * **解**：PostgreSQL 不认 `utf8mb4`，改为 `encoding: unicode` 或 `UTF8`

5. `transaction_isolation: READ-COMMITTED` 报错

   * **解**：删掉或改成 `read committed`（小写+空格），或用上面 DB 语句设置默认隔离级别

6. 找不到服务器 `Could not find server ""`

   * **解**：Gemfile 加 `gem 'puma', '~> 6.4'`，确保测试组里的 `gem 'puma'` 不重复；`bundle install`

7. UI 语言不对

   * 登录后：右上角 **My account → Language: English → Save**
   * 全局默认：**Administration → Settings → General → Default language: English**
   * 未登录：浏览器把 English 放首位；必要时清缓存：`RAILS_ENV=production bundle exec rake tmp:cache:clear`

---

# 一键启动脚本（可选，存为 `start_redmine.sh`）

```bash
#!/usr/bin/env bash
set -e
cd "$(dirname "$0")"

# 确保 DB 起
sudo service postgresql start

# 必要目录
mkdir -p tmp/pids tmp/sockets log public/plugin_assets

# 以 production 启
RUBYOPT='-rlogger' bundle exec rails s -e production -b 0.0.0.0 -p 3000
```

```bash
chmod +x start_redmine.sh
./start_redmine.sh
```

---

# 进一步优化（以后再看）

* Nginx + Passenger 反向代理、systemd 常驻
* 定时备份：`pg_dump redmine` + 打包 `files/`、`plugins/`
* 邮件通知：`config/configuration.yml` 配 SMTP
* 插件：放 `plugins/` 后 `RAILS_ENV=production bundle exec rake redmine:plugins:migrate`
