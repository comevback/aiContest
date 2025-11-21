bundle exec rails s -e production -b 0.0.0.0 -p 3000
uvicorn server:app --reload

python -m backend.agents.redmine-agent

**WSL + PostgreSQL + Redmine 6.1（Rails 6.1 / Ruby 3.0–3.2）**
（√ は初回/たまに必要な作業；★ は毎日起動する際に必要）

---

# 1. 初回準備（インストール時/再インストール時に一度だけ実行） √

1. システムと依存関係

```bash
sudo apt update
sudo apt install -y build-essential libpq-dev postgresql postgresql-contrib git pkg-config
sudo apt install -y rbenv ruby-build
rbenv install 3.2.2
rbenv global 3.2.2
```

2. データベースの作成（PostgreSQL）

```bash
sudo service postgresql start
sudo -u postgres psql <<'SQL'
CREATE ROLE redmine LOGIN ENCRYPTED PASSWORD 'redminepass';
CREATE DATABASE redmine WITH ENCODING='UTF8' OWNER=redmine;
ALTER DATABASE redmine SET default_transaction_isolation TO 'read committed';
SQL
# パスワード認証が必要な場合は、pg_hba.conf の上部に以下を追加：
# local all redmine                       md5
# host  all redmine 127.0.0.1/32          md5
sudo service postgresql restart
```

3. Redmine ディレクトリの準備（~/redmine にあると仮定）

- `config/database.yml`（production のみ残す）：

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

4. Bundler のインストールとデータベースドライバ（pg のみインストール）

```bash
gem install bundler
bundle config set --local with 'postgresql'
bundle config set --local without 'development test mysql sqlite'
bundle config set build.pg "--with-pg-config=/usr/bin/pg_config"
bundle install
```

5. サーバーと互換性（推奨）

- `Gemfile` に**確実に**（かつ一度だけ）含まれていること：

```ruby
gem 'puma', '~> 6.4'      # 本番用 Web サーバー
```

- Ruby 3.2 での Logger プリロードとの互換性（どちらか一方を選択）：
  A. `bin/rails` shebang の次の行と `config/boot.rb` の冒頭に以下を追加：

  ```ruby
  require 'logger'
  ```

  B. 起動コマンドに一時的に環境変数を追加：`RUBYOPT='-rlogger'`

6. 初回初期化（一度だけ実行）

```bash
RAILS_ENV=production bundle exec rake generate_secret_token
RAILS_ENV=production bundle exec rake db:migrate
RAILS_ENV=production bundle exec rake redmine:load_default_data   # en または zh を選択
# Redmine 6.1 では通常 assets:precompile は不要なのでスキップ可能
```

---

# 2. 毎日の起動（日常） ★

`~/redmine` にて：

```bash
# 方法1：Rails コマンド（自動的に Puma を使用）
bundle exec rails s -e production -b 0.0.0.0 -p 3000
# Logger がロードされていない場合：
# RUBYOPT='-rlogger' bundle exec rails s -e production -b 0.0.0.0 -p 3000
```

ブラウザでアクセス：`http://localhost:3000`
初期アカウント：`admin / admin`

---

# 3. 停止 / 再起動 / バックグラウンド実行（オプション）

- フォアグラウンドで起動している場合：`Ctrl + C` で停止
- バックグラウンド（デーモン）で Puma を使用する場合（ログと PID ディレクトリの準備が必要）：

```bash
mkdir -p tmp/pids tmp/sockets log
RAILS_ENV=production bundle exec puma -b tcp://0.0.0.0:3000 -d \
  --pidfile tmp/pids/puma.pid -S tmp/pids/puma.state \
  --redirect-stdout log/puma.stdout.log --redirect-stderr log/puma.stderr.log
# 停止：
bundle exec pumactl -S tmp/pids/puma.state stop
```

---

# 4. 迅速なトラブルシューティングガイド（エラーが発生したらまずここを確認）

1. DB に接続できない

   - TCP でテスト：`psql -U redmine -h 127.0.0.1 -d redmine -W`
   - `pg_hba.conf` に `md5` ルールがあるか確認し、変更後は `sudo service postgresql restart`
   - `config/database.yml` の `adapter: postgresql`、`encoding: unicode` を確認

2. Bundler が `mysql2` を強制的にインストールする

   - **原因**：`database.yml` のどこかに `adapter: mysql2` のセクションがある
   - **解決策**：PG 以外のセクションを削除し、production の postgresql のみ残す。その後、以下を実行：

     ```bash
     bundle clean --force && bundle install
     ```

3. `ActiveSupport::... Logger (NameError)`

   - **解決策**：上記の Logger プリロード（`bin/rails` / `config/boot.rb` の変更、または `RUBYOPT='-rlogger'` の使用）を参照

4. `invalid value for parameter "client_encoding": "utf8mb4"`

   - **解決策**：PostgreSQL は `utf8mb4` を認識しないため、`encoding: unicode` または `UTF8` に変更

5. `transaction_isolation: READ-COMMITTED` エラー

   - **解決策**：削除するか、`read committed`（小文字+スペース）に変更するか、上記の DB コマンドでデフォルトの分離レベルを設定する

6. サーバーが見つからない `Could not find server ""`

   - **解決策**：Gemfile に `gem 'puma', '~> 6.4'` を追加し、テストグループ内の `gem 'puma'` が重複していないことを確認する。その後、`bundle install` を実行

7. UI の言語が正しくない

   - ログイン後：右上隅の **My account → Language: English → Save**
   - グローバルデフォルト：**Administration → Settings → General → Default language: English**
   - 未ログイン：ブラウザで English を最優先にする。必要に応じてキャッシュをクリア：`RAILS_ENV=production bundle exec rake tmp:cache:clear`

---

# 5. ワンクリック起動スクリプト（オプション、`start_redmine.sh` として保存）

```bash
#!/usr/bin/env bash
set -e
cd "$(dirname "$0")"

# DB が起動していることを確認
sudo service postgresql start

# 必要なディレクトリ
mkdir -p tmp/pids tmp/sockets log public/plugin_assets

# production 環境で起動
RUBYOPT='-rlogger' bundle exec rails s -e production -b 0.0.0.0 -p 3000
```

```bash
chmod +x start_redmine.sh
./start_redmine.sh
```

---

# 6. さらなる最適化（後で確認）

- Nginx + Passenger リバースプロキシ、systemd 常駐化
- 定期バックアップ：`pg_dump redmine` + `files/`、`plugins/` のアーカイブ
- メール通知：`config/configuration.yml` で SMTP を設定
- プラグイン：`plugins/` に配置後、`RAILS_ENV=production bundle exec rake redmine:plugins:migrate`

```

```
