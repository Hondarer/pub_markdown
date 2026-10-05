#!/bin/bash

# Pandoc の -N (--number-sections) が出力した見出し番号を、docsfw の採番形式へ変換する。
# 標準入力の HTML を変換して標準出力へ書き出す。
#
# Markdown H5/H6 は --shift-heading-level-by=-1 により 4/5 段の番号になる。
# 本文と目次の番号だけを (1) / (a) へ変換し、見出し ID と href は維持する。
# 変換後の番号は変換対象の形式に一致しないため、再実行しても結果は変わらない。
exec perl -0777 -pe '
    s{(<span class="(?:header|toc)-section-number">)\s*(\d+(?:\.\d+){3,4})\s*(</span>)}{
        my ($open, $number, $close) = ($1, $2, $3);
        my @parts = split /\./, $number;
        my $label = $parts[-1];
        if (@parts == 5 && $label > 0) {
            my $letters = "";
            while ($label > 0) {
                $label--;
                $letters = chr(97 + $label % 26) . $letters;
                $label = int($label / 26);
            }
            $label = $letters;
        }
        "$open($label)$close";
    }ge;
'
