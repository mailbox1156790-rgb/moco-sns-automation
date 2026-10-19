# Threads読み取り接続・実績取得結果

2026-10-19 21:43 JST。対象：[mocochan85](https://www.threads.com/@mocochan85)。Keychain保存、公式APIの本人ID照合、既存投稿3件のInsights取得が完了しました。新規公開は0件です。

## 接続先と認証

- 専用Metaアプリ：Moco SNS Automation、アプリID `1150847227441767`、ThreadsクライアントID `1774625623767445`。
- 本人が承認した読み取り権限：`threads_basic` / `threads_manage_insights`。公式設定画面で準備済み、本人がテスター招待を承認しました。
- 本人がSafariで認証し、Mac内の非表示フォームからKeychainへ保存。既存認証の上書きはありません。保存処理は終了済みです。
- `GET /me?fields=id,username` の応答：`mocochan85` / **27052393934458790**。本人指定プロフィールと照合し、このMacの設定へIDを固定しました。Metaのテスター検索候補に付いた内部IDは使用していません。
- 常駐用の固定コードでも同じIDを実取得し、共有設定が3媒体に反映されることを確認しました。
- `/me/permissions` はHTTP 500で一覧未取得。UIで準備した権限と実際に成功した読み取り操作は確認済みですが、APIによる付与権限一覧は未確認です。

ChromeのAnnaログイン、Anna用アプリの権限・認証情報は変更していません。Facebookパスワードの再設定も行っていません。保存済みパスワードの確認と入力は本人だけが行い、ツールで一覧・値を読み取っていません。

## 投稿ID・URL・実測の照合

本人APIの投稿一覧で所有とURLを確認してから、次の既存投稿を管理DBへ登録しました。`published` は既存投稿の取り込み状態であり、このシステムによる新規投稿を意味しません。

|管理ID|公式投稿ID|公開URL|
|---|---|---|
|moco-f25dca87a8144766|18095194346550481|https://www.threads.com/@mocochan85/post/Ddy3zryn4XT|
|moco-1f11caea27854a14|18011271278985402|https://www.threads.com/@mocochan85/post/DdsTXhvH77x|
|moco-1341594cf5de4d3d|18107107852919185|https://www.threads.com/@mocochan85/post/DdsTIqZHycD|

3件すべてで `views` / `likes` / `replies` / `reposts` / `quotes` / `shares` を実取得しました。今回の要求6指標に未取得はありません。取得時刻は21:43 JSTで、値と時刻・投稿ID・出典をMac内のSQLiteと `var/reports/metrics-管理ID.json` に保存しました。Insights数値はGitHubへ送っていません。

YouTube 3件、Instagram 3件、Threads 3件の計9件がローカル分析対象です。媒体や公開後の経過日数が異なるため、再生数を横断比較した順位や因果関係は示していません。視聴者属性・視聴維持率等は未取得です。

## 定期取得と残りの作業

このMacの6時間更新対象にThreadsを追加しました。登録済みの照合済み投稿だけを読み、停止中は収集しません。次の取得予定は2026-10-20 01:47 JSTです。Macの起動・ログイン・ネット接続が必要です。Instagram/Threadsの常駐実測成功は次周期待ちで、前景での取得成功や常駐用コードでのID確認とは区別します。

トークンの実際の期限・更新可否は未確認で、更新自動化も未実装です。公開用API・公開権限の追加は行っていません。次は本人のテーマ・素材・投稿頻度を確認し、具体的な下書きを制作します。初回公開は投稿先・内容・日時を本人が確認した後に進めます。

以前の認証・ブラウザ分離の経緯は [接続準備記録](2026-10-19-threads-preparation.md) を参照してください。
