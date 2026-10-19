# Mac操作手順

Macのチェックアウトで以下を実行します。クラウド側CodexのシェルはMacではありません。

## 現在はThreadsの文章のみ

本人指示により動画制作・Instagram/YouTube投稿を休止しています。以下に残した動画/他媒体の手順は以前の基盤の記録で、現在は実行しません。制作対象はthreadsのみ、video_enabledはfalseです。

Threadsのrenderは原稿JSONとpost.txtの保存だけです。reviewで本文・確認ハッシュ・投稿先URL・固定IDを確認します。

```sh
python3 -m moco render moco-5ab9604cc71245a4
python3 -m moco review moco-5ab9604cc71245a4
```

現在は読み取り接続のみです。専用アプリにthreads_content_publishを追加する本人確認・再認証後、`python3 -m moco secret-import threads_publish` で投稿用認証を別のKeychainキーへ保存し、本人IDを照合します。既存の読み取り認証は上書きしません。

本文・投稿先・公開タイミングの本人承認後にだけ、Macのmodeをthreads_text、publishing.threads.enabledとpermission_owner_approvedをtrueにします。`approve-threads 管理ID --digest 確認ハッシュ --at nowまたは将来のISO時刻 --owner-confirmed` で承認記録を固定し、`publish-threads 管理ID --owner-confirmed` で公開します。これらはGitHubから呼べません。初回成功と投稿頻度/時刻の本人確認後にだけautomatic_schedulingをtrueにします。現在はすべて無効です。

POST応答不明は再実行せずreconciliation_requiredで照合します。コンテナ待ち、受領済み投稿IDの結果待ちはGETだけで再確認できます。詳細は [Threads専用報告](reports/2026-10-19-threads-only.md)。

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

### 認証が期限切れになったとき

古い `/login/device/authorize` が404になり、CLIに `expired_token` が表示された場合は、新しい認証を開始します。招待の承諾はやり直しません。

```sh
python3 scripts/login_github.py
```

この補助スクリプトは公式CLIを使い、一時コードをMacのクリップボードへコピーします。コードやCLIの生出力はログへ出さず、認証トークンは公式CLIの保管処理へ任せます。
`code_copied_to_mac_clipboard` が出たらChromeで https://github.com/login/device を開き、招待を承諾したアカウントを選択します。左端のコード欄に⌘Vで貼り付け、Continue、Authorizeへ進みます。
補助スクリプトの `authorized` と `python3 -m moco github-check` の成功を確認して完了とします。
ブラウザの過去の成功画面だけでは、現在Macで待っている認証の完了とは判断しません。
最後の許可操作は本人が行います。コードは期限付きで、終了時にはクリップボードがこのコードのままなら消去します。

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
Macの認証処理は最大60分間待ちます。その間は起動した処理を終了しないでください。
`127.0.0.1 で接続が拒否されました` と出る場合、Mac側の待受が終了している可能性があります。
Mac側が `oauth_authorization_timed_out` なら新しい認証を開始します。古い戻り先URLは再利用・共有しません。
本人が拒否した場合は `oauth_authorization_denied` と区別して記録します。

## 4. Instagram / Threads

このMacではInstagramの本人ログインとプロフェッショナルダッシュボードを確認済みです。Creator/Businessの内訳は未確認です。Metaの本人確認を通過し、開発者アプリ画面へアクセスできることを確認しました。専用アプリ「Moco SNS Automation」は本人が作成済み。本人承認後に `instagram_business_basic` と `instagram_business_manage_insights` の2権限だけ追加し、mocochan85のInstagramテスター招待も本人が承認しました。既存Anna用アプリを編集していません。公式Instagramで本人ログイン・読み取り同意を進め、トークンをKeychainへ保存後にAPIのID照合を行います。Metaの標準生成リンクは投稿/DMを含む5権限を要求したため、認証URLのscopeを承認済みの2権限へ絞りました。認証URLやトークンを報告へ貼らないでください。コードや画面の認証URLをGitHubへ貼らないでください。
Threadsはプロフィール→共有→リンクをコピーでURLを確認します。

本人がパスワードを再設定し、mocochan85での通常ログインを再確認しました。古い認証URLを使わず、読み取り2権限に限定した新しい認証を開始し、Metaの「トークンが生成されました」まで確認しています。新しいパスワードや復旧リンクは取得・保存していません。
Meta Developer側のアプリ作成・本人ログイン・同意・必要な審査は本人操作です。現在は自動化していません。
必要な読取権限・API版を公式画面で確認後、トークンをMacの非表示入力からKeychainへ保存します。

```sh
python3 -m moco secret-set instagram
python3 -m moco secret-set threads
python3 -m moco account instagram
python3 -m moco account threads
```

Meta画面のトークンをターミナルへ貼らずに保存する場合は、Macで次を実行します。

```sh
python3 -m moco secret-import instagram
python3 -m moco secret-import threads
```

表示された `http://127.0.0.1:ポート/` をこのMacのブラウザで開き、Metaの生成画面からコピーしたトークンを非表示欄へ貼り付けます。フォームは最大60分だけ待ち受け、1回保存すると終了します。トークンをURL、ファイル、ログへ書きません。Host・Origin・CSRF・入力サイズを検証し、CSPとno-storeを設定しています。HTTPはMacのループバック内だけに使用し、外部APIのTLS証明書検証は引き続き有効です。

このフォームはKeychainへ新規追加するだけで、既存レコードを上書きしません。既存レコードがある場合は保存を拒否します。保存成功とAPI接続確認は別で、保存後にアカウントIDを照合します。GitHub指示からこの認証コマンドを起動する機能は追加していません。

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

### 実測値の定期更新

このMacの現在の更新対象はThreadsの登録済み投稿だけで、6時間ごとに分析JSONも更新します。基本設定のmetrics_collection.enabledはfalse、Macのconfig/local.jsonでthreadsだけを有効にしています。過去に取得した他媒体の実測は保全しています。
`interval_seconds: 21600`、`max_posts_per_run: 20`。対象は既に所有照合された `published` の投稿IDです。
結果は `var/reports/metrics-collection.json`。取得失敗時は失敗を記録して次の周期を待ちます。停止中は実測の外部APIへ接続しません。

### GitHubへの実測自動報告

以前のYouTube報告は現在無効です。以下は過去の実装記録です。完了した取得周期ごとに、固定した報告用Issueへ1件追記する仕組みを検証しました。このMacの宛先は[Issue #3](https://github.com/mailbox1156790-rgb/moco-sns-automation/issues/3)です。基本設定では無効で、秘密値を含まない `github.metrics_report_issue: {"number": 3, "id": 5922764913}` をMacの個別設定に置きます。
リポジトリ・Issue数値ID・作者の信頼を照合します。対象は公開状態と本人チャンネルを確認したYouTube動画の再生・高評価・コメント数のみ。非公開/限定公開動画や詳細Insights、認証情報、任意のAPIフィールドを送りません。

送信記録は `var/reports/github-metrics-outbox.json`。送信前にpayloadを固定し、再実行時は保存したコメントIDを使います。送信結果が不明な場合はGETで同じマーカーを照合し、確認できなければ `verification_required` で止めます。自動POST再試行はしません。手動で送信記録を削除する前に、GitHubのコメントを照合してください。停止中はこの実測報告も送信しません。
`status.json` の `github_metrics_report` で結果を確認できます。`public: false` はSNSへの新規公開がないことを表します。GitHubの報告コメントは指定リポジトリの閲覧範囲へ共有されます。

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
Mac内フォームのReferrer-Policyは `same-origin` とします。ChromeのPOSTでOriginを維持しつつ、他オリジンへRefererを送りません。`no-referrer` ではOriginがnullとなり厳格な照合で拒否されることを実ブラウザで確認しました。Host/Origin/CSRFを緩めて対処しないでください。

Swiftのコンパイルキャッシュは共有データ内の `swift-cache-canonical/` の実パスに固定します。PCHが古いリリースのパスを記憶して再ビルドできなくなる問題を解消し、以前のキャッシュは保持しています。
移行前のデータはチェックアウト内の `work/var-before-runtime-*` に保持します。DBはSQLiteバックアップAPIでコピーし、元を削除しません。
登録・更新はMacでのみ行います。フルディスクアクセスの付与やOSの保護設定変更は行っていません。
