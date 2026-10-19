# Instagram読み取り接続・既存リール実測

作業日：2026-10-19（Asia/Tokyo）。秘密値・非公開Insightsの数値はこの報告に含めません。SNSへの新規公開は0件です。

## 接続結果

- 対象プロフィール：[mocochan85](https://www.instagram.com/mocochan85/)
- Meta専用アプリ：Moco SNS Automation、アプリID `1150847227441767`
- Instagram用クライアントID：`2011482642896301`
- 公式API `/me?fields=user_id,username` の実応答：ユーザー名 `mocochan85`、アカウントID `17841469438292740`
- API IDと本人が承認したテスター行のID、本人指定のユーザー名が一致しました。
- APIバージョン：Meta公式Graph API Explorerで表示を確認した `v26.0`。この版で本人ID・投稿一覧・Insightsの実読取に成功しました。
- 認証情報：本人がMac内の非表示フォームからKeychainへ保存。既存レコードの上書きなし。フォームの待受は保存後に終了しました。
- 固定実行コピーからも同じKeychainを使い、本人IDの一致を再確認しました。

本人が承認した要求scopeは `instagram_business_basic` と `instagram_business_manage_insights` の2つです。投稿・DM・コメント管理権限は追加していません。`/me/permissions` はHTTP 400だったため、付与権限の一覧はAPI未取得として記録します。本人ID・投稿一覧・6指標の読み取り成功を、全権限一覧の取得成功とは扱いません。

## 既存リールの実測

本人アカウントの投稿一覧から12件のID・URL・種別を取得し、そのうち先頭の既存リール3本を所有照合してMacの運用DBへ登録しました。

|既存投稿ID|公開リンク|
|---|---|
|17967221522989453|https://www.instagram.com/reel/DROiiQMEpmv/|
|17997124286702760|https://www.instagram.com/reel/DRMhK08kjb0/|
|18422046529114651|https://www.instagram.com/reel/DQyyoNZkulu/|

3本すべてで `views`、`reach`、`likes`、`comments`、`saved`、`shares` を公式Insightsから実取得しました。これら6指標に欠測はありませんでした。視聴時間・維持率・視聴者属性は未取得です。取得時刻は各レコードの `collected_at` に保存します。

Insightsの数値はMac内のDBと `var/reports/metrics-管理ID.json` に保存します。公開リポジトリの自動報告へInstagramの非公開Insightsを混ぜません。現在のGitHub自動実測報告は引き続き公開確認済みYouTubeの3指標だけです。

既存投稿の取り込みを状態 `published` として登録しましたが、このMacから投稿したものではありません。新規アップロード・公開操作は行っていません。

## 定期取得と残作業

このMacのローカル設定だけで、登録済みYouTubeとInstagramを6時間ごとの更新対象にしました。基本設定の自動取得はfalseを維持します。次の周期は従来予定の2026-10-20 01:47 JST以降です。Macの起動・ログイン・接続が必要です。Instagramの初回実取得は前景、固定実行コピーでの本人ID照合も前景で検証しました。常駐でのInstagram実測更新成功はまだ確認していません。

トークンの有効期限・長期更新は未確認/未実装です。ThreadsのAPI認証とID照合、詳細YouTube Analytics、投稿アダプタも残っています。公開機能は未実装、モードは `draft_only` です。本人による初回公開の内容・日時確認を省略しません。

自動テスト59件成功。Keychain保存、Instagram実API照合、3本の実測取得はユニットテストと別にMacで確認しました。既存Annaアプリの権限・認証情報を変更していません。
