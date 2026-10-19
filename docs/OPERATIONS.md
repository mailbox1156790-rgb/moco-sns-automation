# Mac操作手順

Macのチェックアウトで以下を実行します。クラウド側CodexのシェルはMacではありません。

## 1. GitHub本人認証

```sh
/usr/local/bin/gh auth login --hostname github.com --git-protocol https --web
/usr/local/bin/gh auth setup-git
python3 -m moco github-check
python3 scripts/configure_github.py
```

対話で `Authenticate Git ... (Y/n)` が出たら `y` とEnter。認証コードはMacのブラウザのGitHub画面だけに入力します。
認証後の保存先はKeychainを利用します。秘密値をコマンド引数・チャットへ貼らないでください。
リポジトリ所有者、または招待を承諾した本人の共同作業アカウントで認証します。`configure_github.py` は指定リポジトリへの書き込み権限を検証してから、認証した本人の数値IDをローカルに登録します。他の協力者を追加する場合も本人確認を行います。

GitHub CLIでラベルを作成し、常駐処理をGitHub受信モードで登録します。

```sh
gh label create 'moco:command' --repo mailbox1156790-rgb/moco-sns-automation --color 37B99B --description 'Macへの本人の定型指示'
python3 scripts/install_runtime.py --github
python3 scripts/service.py status
```

ラベルが既に存在する場合は作成不要です。IssueテンプレートのJSON以外の説明文を残さず、`command_id` は指示ごとに新しいUUIDへ置き換えます。
例は `examples/command-status.json` と `examples/command-draft.json`。結果は元Issueにコメントされます。
`render` 指示は `{"version":1,"command_id":"新しいUUID","action":"render","id":"moco-管理ID"}`。
`analyze` / `stop` は `status` のactionだけ置き換えます。

## 2. 原稿と制作

```sh
python3 -m moco draft --platform youtube --topic 'AI動画の企画を一つに絞る'
python3 -m moco render moco-ここを管理IDに置換
```

制作物は `var/assets/管理ID/`。`draft.json` に企画意図・台本・投稿文・確認事項、`cover.png` にカバー、`video.mp4` に動画を保存します。
原稿修正は別ファイルでJSONを編集し、`python3 -m moco revise 管理ID --file 修正JSONのパス`、再びrenderします。
原稿・素材の権利・事実・導線を本人が確認してください。テンプレート内のチェック欄は編集記録であり、公開許可には使いません。

```sh
python3 -m moco review 管理ID
python3 -m moco approve 管理ID --digest 確認したハッシュ --owner-confirmed
python3 -m moco schedule 管理ID --at '2026-10-20T16:00:00+09:00'
python3 -m moco tick
```

これは予約シミュレーションだけです。公開用の動画をSNSへアップロードしません。
本人が確認するまではapproveを実行しないでください。

## 3. YouTubeの読み取り認証

本人がGoogle Cloud Consoleでプロジェクト、YouTube Data API v3、YouTube Analytics API、OAuth同意画面、デスクトップアプリ用OAuthクライアントを用意します。
OAuthクライアントJSONはGit管理の外へ保存し、Macで次を実行します。

```sh
python3 -m moco auth-youtube --client-file /安全な場所の/client_secret.json
python3 -m moco account youtube
```

本人がブラウザの同意を操作します。この版が要求するのは読み取り権限だけです。コード/トークンをチャットへ送らないでください。
`mine=true` と `forHandle=@MOCOchannel` のID一致を確認した後、本人確認済みのIDを `config/local.json` に設定します。
OAuthアプリの公開/テスト状態や再同意要否はGoogle Consoleで確認します。

## 4. Instagram / Threads

Instagramアプリでプロフィール→メニュー→アカウントの種類とツール等を確認し、Business/Creatorアカウントであるか確認してください。画面名称は版で異なることがあります。
Threadsはプロフィール→共有→リンクをコピーでURLを確認します。
Meta Developer側のアプリ作成・本人ログイン・同意・必要な審査は本人操作です。現在は自動化していません。
必要な読取権限・API版を公式画面で確認後、トークンをMacの非表示入力からKeychainへ保存します。

```sh
python3 -m moco secret-set instagram
python3 -m moco secret-set threads
python3 -m moco account instagram
python3 -m moco account threads
```

Instagramは確認済みのGraph API版を `config/local.json` の `accounts.instagram.api_version` に指定するまで接続を拒否します。
各媒体の確認済み `account_id` と `owner_confirmed: true` も同ファイルに設定します。設定に秘密値は書きません。

## 5. 既存投稿の実測と分析

```sh
python3 -m moco collect youtube --remote-id 実際の動画ID
python3 -m moco collect instagram --remote-id 実際のメディアID
python3 -m moco collect threads --remote-id 実際の投稿ID
python3 -m moco analyze
```

APIで投稿の所有を照合してから、投稿ID・URL・取得時刻・指標の実値を保存します。APIで未対応/未取得は `null`。YouTube詳細分析や人口統計はまだ取り込みません。
公開画面の参考数値、拡張機能の推計値、テストの架空データはこの集計に混ぜません。

## 6. 停止・バックアップ

```sh
python3 -m moco stop
python3 scripts/service.py stop
python3 -m moco status
```

再開は `python3 -m moco resume --owner-confirmed` 後、`python3 scripts/install_runtime.py --github`。
常駐解除は `python3 scripts/service.py uninstall`。登録名は `jp.moco.sns-automation`、ログは `var/worker.*.log`、DBは `var/state.sqlite3`。
SQLiteのバックアップはPythonの `sqlite3.Connection.backup()` 等を使い、保存先もGitの外にします。Keychainは別管理です。
Macの電源・ネット接続・ログインセッションが必要です。電源やスリープ設定はこの作業では変更していません。
この版のログは自動ローテーション未対応です。長期運用前にローテーションと異常通知を追加します。

## 実行用コピーについて

macOSのバックグラウンド処理はDocumentsフォルダにアクセスできないため、`scripts/install_runtime.py` が必要なコードを `~/Library/Application Support/MocoSNS/releases/コードハッシュ/` へ配置します。
launchdはこの固定コピーを実行します。GitHubやクラウド側の編集は自動的に実行コードへ反映しません。変更をMacで確認・テスト後に再度installerを実行します。
共有データは同フォルダの `data/`、個別設定は `local-settings.json`。チェックアウトの `var` と `config/local.json` からシンボリックリンクで参照します。
移行前のデータはチェックアウト内の `work/var-before-runtime-*` に保持します。DBはSQLiteバックアップAPIでコピーし、元を削除しません。
登録・更新はMacでのみ行います。フルディスクアクセスの付与やOSの保護設定変更は行っていません。
