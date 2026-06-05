# Admonition のサンプル

## 各タイプの表示

Markdown admonition と Doxygen タグの対応は次のとおりです。

| Markdown admonition | Doxygen タグ |
|---|---|
| NOTE | `@note` |
| TIP | `@remark` |
| IMPORTANT | `@important` |
| WARNING | `@warning` |
| CAUTION | `@attention` |

> [!NOTE]
> これは補足情報です。
> 複数行にわたる内容も記述できます。

> [!TIP]
> これは便利なヒントです。

> [!IMPORTANT]
> これは重要な情報です。

> [!WARNING]
> これは注意が必要な情報です。

> [!CAUTION]
> これは危険な操作に関する警告です。

## 通常の blockquote との共存

> これは通常の引用ブロックです。
> admonition には変換されません。

## Markdown 記法の使用

> [!NOTE]
> admonition 内で **太字** や `インラインコード` が使用できます。

## 未対応タイプ

> [!TODO]
> 対応していないタイプは通常の blockquote として表示されます。
