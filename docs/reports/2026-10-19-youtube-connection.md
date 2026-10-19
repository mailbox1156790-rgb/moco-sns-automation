# YouTube読み取り接続・定期実測の報告

作業日：2026-10-19（Asia/Tokyo）。新規公開投稿は0件。認証情報・認証URLは含みません。

本人の読み取りOAuthをmacOS Keychainに保存し、`channels.list(mine=true)` と `forHandle=@MOCOchannel` のIDが `UCjcZcz7chD2o6hu4ZUZSA8Q` で一致しました。Google認証時に使った既存アプリの所有も本人が確認済みです。

公開Shorts一覧で動画IDを確認し、公式APIで同じチャンネルの所有と公開状態を照合してから実測を保存しました。非公開動画の情報は報告に含めていません。

|公開URL|再生数|高評価|コメント|取得時刻（JST）|
|---|---:|---:|---:|---|
|https://www.youtube.com/shorts/yMQsYOj3RP4|611|7|0|2026-10-19 19:49:59|
|https://www.youtube.com/shorts/8zPGBs_XNoc|546|6|0|2026-10-19 19:50:00|
|https://www.youtube.com/shorts/QgNc3Gyotts|2134|9|0|2026-10-19 19:50:00|

視聴時間・維持率・リーチ・人口統計・収益は未取得です。YouTube Analyticsの詳細レポートは未実装です。3本の初回観測だけで、テーマの優劣や因果関係、投稿時刻の最適値を断定しません。

次の実験案は、同じテーマで冒頭の問いかけだけを変え、同じ公開後経過時間で比較することです。内容と日時は本人確認後に決めます。

## 常駐での検証

- 6時間ごとに、登録済みの投稿IDだけを再取得します。対象はこのMacのローカル設定でYouTubeのみ有効です。
- launchdによる最初の更新は3件成功、失敗0件。完了時刻は2026-10-19 19:50 JST。手動取得とは別のバックグラウンドAPI接続を確認しました。
- 再起動後も取得間隔を維持し、失敗を0件の実績に置き換えません。停止操作は定期取得にも適用されます。
- 配置時にSwiftソースの時刻を保持し、変更のない補助プログラムの不要な再コンパイルを防ぎました。
- 自動テスト59件成功。14分後の認証完了、不正state、拒否と期限切れの区別、取得間隔、停止、誤アカウント、欠測の保持を含みます。

初回の認証はMacの5分待受が終了し、Googleからの戻り先で接続拒否になりました。待受を60分へ延長した後の再接続で解消しました。

DB上の既存公開動画3本は取り込み記録です。Macで制作したサンプルは本人確認待ちで、新規公開は行っていません。

## 次の作業

- Instagramは本人ログイン・Professionalを確認しました。Meta本人確認と開発者画面のアクセス復旧を確認しました。本人が専用アプリを作成し、読取2権限追加・テスター承認も完了。再設定後の新しい認証からトークン生成まで確認し、Macへの保存・API接続照合は未完了です。
- Instagram/ThreadsのAPI認証・ID照合、YouTube詳細Analyticsは未完了/未実装です。
- 定期実測はMacに保存し、完了周期の結果と最新の公開YouTube実測を固定Issue #3へ自動追記します。最初の常駐送信と重複防止を確認済みです。2026-10-19 20:11 JSTに公開状態を再照合した3本のカウンターは上表と同値でした。最新の取得時刻は実測JSONを参照してください。
- 公開アダプタは未実装。新規公開は本人が投稿先・内容・日時を確認した後の段階です。

機械可読の実測：[2026-10-19-youtube-measurements.json](2026-10-19-youtube-measurements.json)。
取得に使用した公式API：[videos.list](https://developers.google.com/youtube/v3/docs/videos/list)、[playlistItems.list](https://developers.google.com/youtube/data/reference/rest/v3/playlistItems/list)。
