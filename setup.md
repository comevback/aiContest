可以 👍 我来一步步教你在 **WSL (Windows Subsystem for Linux)** 里安装 **Redmine**。
（假设你已经装好 WSL 和 Ubuntu。）

---

## 🧩 一、准备环境

在 WSL 终端执行以下命令：

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y git curl build-essential libssl-dev libreadline-dev zlib1g-dev libsqlite3-dev libpq-dev libxml2-dev libxslt1-dev imagemagick
```

---

## 🪄 二、安装 Ruby（推荐用 rbenv）

```bash
# 安装 rbenv 和 ruby-build
git clone https://github.com/rbenv/rbenv.git ~/.rbenv
git clone https://github.com/rbenv/ruby-build.git ~/.rbenv/plugins/ruby-build

# 配置环境变量
echo 'export PATH="$HOME/.rbenv/bin:$PATH"' >> ~/.bashrc
echo 'eval "$(rbenv init - bash)"' >> ~/.bashrc
source ~/.bashrc

# 查看 Ruby 可安装版本
rbenv install -l

# 安装 Redmine 推荐的 Ruby 版本（比如 3.2.2）
rbenv install 3.2.2
rbenv global 3.2.2
ruby -v
```

---

## 🧰 三、安装数据库（PostgreSQL 或 MySQL）

以 **PostgreSQL** 为例：

```bash
sudo apt install -y postgresql postgresql-contrib libpq-dev
sudo -u postgres createuser -s redmine
sudo -u postgres psql
# 在 psql 里输入：
# CREATE DATABASE redmine WITH ENCODING='UTF8';
# \q
```

---

## 🧱 四、下载并配置 Redmine

```bash
cd ~
wget https://www.redmine.org/releases/redmine-6.1.1.tar.gz
tar xzf redmine-6.1.1.tar.gz
mv redmine-6.1.1 redmine
cd redmine
```

### 配置数据库连接

```bash
cp config/database.yml.example config/database.yml
nano config/database.yml
```

修改 PostgreSQL 部分为：

```yaml
production:
  adapter: postgresql
  database: redmine
  host: localhost
  username: redmine
  password: ""
  encoding: utf8
```

---

## 💎 五、安装依赖包（Gem）

```bash
gem install bundler
bundle install --without development test
```

---

## 🔑 六、生成密钥并初始化数据库

```bash
bundle exec rake generate_secret_token
RAILS_ENV=production bundle exec rake db:migrate
RAILS_ENV=production bundle exec rake redmine:load_default_data
```

选择语言时可以输入 `zh`。

---

## 🚀 七、启动 Redmine 服务器

```bash
bundle exec rails server -e production -b 0.0.0.0 -p 3000
```

然后在浏览器访问：

👉 **[http://localhost:3000](http://localhost:3000)**

默认登录：

```
用户名：admin
密码：admin
```

---

## 🧹 八、可选优化（持久化运行）

安装 **puma 或 passenger** 并用 **nginx** 反向代理。
我可以帮你配成 `systemd` 自动启动版本（可选）。

---

是否要我帮你写一个 **一键安装脚本（.sh）**？
运行一次即可自动完成以上全部步骤。
