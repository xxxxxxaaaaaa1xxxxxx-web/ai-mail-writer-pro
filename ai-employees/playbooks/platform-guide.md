# 海外プラットフォーム攻略ガイド

ヤヌス・カルメン・イリスが各PFで運用する際の **実戦攻略ノウハウ** をまとめたプレイブック。

## 1. Gumroad（メイン販売チャネル）

### 特徴
- **最重要PF**（オススメ1位）
- 手数料：10%（最も安い水準）
- 即時決済、PDF自動配信
- 海外向け販売の事実上のスタンダード

### 攻略ポイント
- **価格帯**：$19 / $29 / $49 が黄金比
- **タイトル**："Japanese [Concept]: [Benefit] in [Time]" 形式
- **サムネ**：白背景＋墨色＋差し色1色のミニマル
- **タグ**：5個（minimalism, japan, zen, mindfulness, productivity 等）
- **カテゴリ**：Personal Development > Self-Improvement
- **プレビュー**：本文の15-20%を「Read sample」で公開
- **License**：Personal use only, no resale

### 売上加速施策
1. **Gumroad Discover**：レビュー10件以上で表紙推奨表示
2. **メール配信**：購入者リストへ月1回新作告知
3. **割引コード**：Black Friday時に20%OFFコード配布
4. **アップセル**：購入完了画面で他商品を提示

### 出品テンプレ（API）
```json
{
  "name": "Danshari: Declutter Your Mind in 7 Days",
  "price": 2900,
  "description": "...PASフォーミュラのLP本文...",
  "url": "danshari-7-days",
  "preview_url": "https://...",
  "tags": ["minimalism", "japan", "zen", "mindfulness", "productivity"],
  "is_pay_what_you_want": false,
  "is_subscriptive": false,
  "license": "personal_use_only"
}
```

---

## 2. Medium（集客ファネル上流）

### 特徴
- **集客装置**：Mediumで読者を獲得 → Gumroadへ送客
- Partner Program：直接収益も発生（月$5-$200程度）
- SEO的に強い（Google検索で上位）

### 攻略ポイント
- **publication 投稿**：
  - 自己啓発：Better Humans / The Ascent / Mind Cafe
  - 仕事系：Better Marketing / Better Programming
  - ライフスタイル：The Apeiron Blog
- **タイトル公式**："I Tried [Japanese Concept] for [Time]. Here's What Changed."
- **タグ**：5個（メイン+サブ）
- **paywall**：Partner Program参加なら有料化、そうでなければ無料公開＋CTA
- **末尾CTA**：必ずGumroadリンク
- **サブヘッディング**：日本文化の権威性を強調

### 売上加速施策
1. **Top Writer in [Topic]** 取得（同タグで月10記事＋）
2. **Curated Stories**：エディタにDistribution依頼
3. **Newsletter**：自分のフォロワーに毎週配信
4. **コメント返信**：エンゲージメント上げる

### 投稿テンプレ
```
Title: I Tried the Japanese Kakeibo Method for 30 Days. I Saved $847.
Subtitle: An ancient practice from 1904 Japan, made simple for 2026 wallets.

[Hook 段落: 自分の悩みから始める（Mediumの典型）]

[展開: kakeibo の歴史と仕組み]

[実体験: 30日間の記録]

[結論: 学び3つ]

---
Want the full 30-day kakeibo workbook with daily prompts?
👉 Get it on Gumroad for $29: [URL]
```

---

## 3. Substack（サブスクリプション化）

### 特徴
- メールニュースレター主体
- サブスクリプション収益（リカーリング）
- ファン化に強い

### 攻略ポイント
- **無料セクション**：30%
- **有料セクション**：70%
- **配信頻度**：週1〜2回（多すぎると解除される）
- **値付け**：$5/月 or $50/年
- **founding member**：$100で限定特典付き

### 売上加速施策
1. **クロスポスト**：他Substackerと相互紹介
2. **Notes**：Substackの新機能でショート投稿
3. **Recommendations**：他のSubstackをrecommend、相互フォロー
4. **アーカイブの強化**：過去記事を再宣伝

---

## 4. KaryaKarsa（インドネシア）

### 特徴
- 東南アジア最大級
- インドネシアGDP成長率5.1%、購買力急上昇
- 競合少ない（ブルーオーシャン）

### 攻略ポイント
- **言語**：英語でも可、ただしバハサ・インドネシア対応すれば爆発
- **価格**：USDより現地通貨（IDR）建て、$5-$15相当が売れ筋
- **テーマ**：ライフスタイル、自己啓発、ビジネス

---

## 5. readAwrite / meb（タイ）

### 特徴
- タイ語マーケット
- mebは電子書籍メイン、readAwriteは連載小説形式

### 攻略ポイント
- 翻訳必要（DeepLでタイ語翻訳→現地ネイティブにレビュー依頼推奨）
- 価格帯：$3-$10相当
- ジャンル：自己啓発、フィクション、料理（日本食人気）

---

## 6. Ghost（シンガポール拠点）

### 特徴
- WordPress代替の出版プラットフォーム
- 独自ドメインで運用可能
- メンバーシップ機能内蔵

### 攻略ポイント
- 自社ドメイン（zigokuglobal.com）でブランド構築
- SEO重視、長文記事＋メルマガ
- $5-$15/月 のサブスク

---

## 7. Steady（ヨーロッパ）

### 特徴
- ドイツ発、欧州メインのPatreon型
- 月額・年額のサブスク
- ジャーナリスト・クリエイター御用達

### 攻略ポイント
- **言語**：英語＋ドイツ語推奨
- 文化系コンテンツが好まれる
- $5-$20/月

---

## 8. Ko-fi（イギリス）

### 特徴
- 投げ銭＋ショップ＋メンバーシップ
- 手数料0%（Ko-fi Goldで5%）
- イギリス・米国で人気

### 攻略ポイント
- まず無料記事で投げ銭ファン獲得
- ショップでPDF販売（Gumroadのバックアップ的位置）
- $3-$15

---

## プラットフォーム間連携戦略

```
[Medium] 無料記事で集客
   ↓ CTA
[Gumroad] 単発高単価販売 ($29)
   ↓ 購入者リスト
[Substack] ファン化・リカーリング ($5/月)
   ↓ 上位ファン
[Ko-fi] 限定コンテンツ・直接サポート
```

## ヤヌスへの優先順位（リソース配分）

| PF | リソース配分 | 理由 |
|---|---|---|
| Gumroad | 50% | 売上の中核 |
| Medium | 25% | 集客の中核 |
| Substack | 15% | リテンションの中核 |
| 他5PF合計 | 10% | 実験・分散リスク |
