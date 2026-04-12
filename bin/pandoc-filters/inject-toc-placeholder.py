#!/usr/bin/env python3
"""
inject-toc-placeholder.py

pandoc が生成した DOCX の TOC フィールド結果部分（空の目次エリア）に
プレースホルダテキストを挿入する。

Word でフィールドを更新（目次の再生成）すると、
プレースホルダは実際の目次に置き換えられる。

Usage:
    inject-toc-placeholder.py <docx_path> [placeholder_text]

Background:
    pandoc --toc で生成した DOCX の TOC は Word フィールドとして埋め込まれており、
    Word を開いてフィールドを更新するまでは空（フィールド結果部分が空）である。
    本スクリプトは fldChar[separate] と fldChar[end] の間に run を挿入することで、
    更新前の状態でも「目次を更新してください」等のアフォーダンステキストを表示する。
"""

import sys
import os
import zipfile
import re


def escape_xml(text):
    """XML の特殊文字をエスケープ"""
    return (text
            .replace('&', '&amp;')
            .replace('<', '&lt;')
            .replace('>', '&gt;'))


def build_placeholder_run(text):
    """
    プレースホルダとして挿入する w:r 要素の XML を生成する。
    スタイル: 灰色 (#606060) + 斜体
    テキスト中の \\n は Word の改行（<w:br/>）として出力する。
    Word の TOC フィールド更新時にこれらの run は置き換えられる。
    """
    rpr = '<w:rPr><w:color w:val="606060"/><w:i/><w:iCs/></w:rPr>'
    parts = []
    for i, line in enumerate(text.split('\n')):
        if i > 0:
            parts.append(f'<w:r>{rpr}<w:br/></w:r>')
        parts.append(f'<w:r>{rpr}<w:t xml:space="preserve">{escape_xml(line)}</w:t></w:r>')
    return ''.join(parts)


def inject_into_xml(xml, placeholder):
    """
    word/document.xml の内容を受け取り、TOC フィールドの
    fldChar[separate] と fldChar[end] の間にプレースホルダ run を挿入する。

    - TOC フィールドが見つからない場合 → None を返す（変更なし）
    - separate-end 間にすでにコンテンツがある場合 → None を返す（二重挿入防止）
    """
    # TOC フィールドの有無を確認
    if not re.search(r'<w:instrText\b[^>]*>[^<]*\bTOC\b', xml):
        return None

    placeholder_run = build_placeholder_run(placeholder)
    modified = [False]

    def process_paragraph(m):
        para = m.group(0)
        # この段落が TOC instrText を含まない場合はスキップ
        if not re.search(r'<w:instrText\b[^>]*>[^<]*\bTOC\b', para):
            return para

        # Case A: separate と end が異なる w:r に入っている場合
        #   ...<fldChar separate/></w:r>(\s*)<w:r>...<fldChar end/>...
        new_para, n = re.subn(
            r'(<w:fldChar\b[^>]*\bfldCharType=["\']separate["\'][^>]*/?>(?:</w:fldChar>)?\s*</w:r>)'
            r'(\s*)'
            r'(?=\s*<w:r\b[^>]*>\s*(?:<w:rPr>.*?</w:rPr>\s*)?<w:fldChar\b[^>]*\bfldCharType=["\']end["\'])',
            lambda mm: mm.group(1) + mm.group(2) + placeholder_run,
            para,
            flags=re.DOTALL
        )
        if n > 0:
            modified[0] = True
            return new_para

        # Case B: separate と end が同じ w:r に隣接している場合（pandoc の実際の出力）
        #   ...<fldChar separate/><fldChar end/>...
        #   → ...<fldChar separate/></w:r>[placeholder]<w:r><fldChar end/>...
        new_para, n = re.subn(
            r'(<w:fldChar\b[^>]*\bfldCharType=["\']separate["\'][^>]*/?>)'
            r'(\s*)'
            r'(?=\s*<w:fldChar\b[^>]*\bfldCharType=["\']end["\'])',
            lambda mm: mm.group(1) + '</w:r>' + mm.group(2) + placeholder_run + '<w:r>',
            para,
            flags=re.DOTALL
        )
        if n > 0:
            modified[0] = True
            return new_para

        return para

    result = re.sub(
        r'<w:p\b[^>]*>.*?</w:p>',
        process_paragraph,
        xml,
        flags=re.DOTALL
    )

    return result if modified[0] else None


def main():
    if len(sys.argv) < 2:
        print(
            'Usage: inject-toc-placeholder.py <docx_path> [placeholder_text]',
            file=sys.stderr
        )
        sys.exit(1)

    docx_path = sys.argv[1]
    placeholder = (sys.argv[2] if len(sys.argv) > 2
                   else '\n目次を更新してください。\nPlease update the table of contents.')

    if not os.path.isfile(docx_path):
        print(f'Error: file not found: {docx_path}', file=sys.stderr)
        sys.exit(1)

    # DOCX (ZIP) を読み込む
    with zipfile.ZipFile(docx_path, 'r') as z:
        infos = {info.filename: info for info in z.infolist()}
        doc_xml = z.read('word/document.xml').decode('utf-8')
        other_files = {
            name: (z.read(name), infos[name].compress_type)
            for name in infos
            if name != 'word/document.xml'
        }

    # プレースホルダを注入
    new_xml = inject_into_xml(doc_xml, placeholder)
    if new_xml is None:
        return  # TOC なし、または変更不要

    # DOCX を上書き保存（一時ファイル経由で安全に）
    tmp_path = docx_path + '.tmp'
    try:
        with zipfile.ZipFile(tmp_path, 'w') as z:
            z.writestr('word/document.xml', new_xml.encode('utf-8'),
                       zipfile.ZIP_DEFLATED)
            for name, (data, compress_type) in other_files.items():
                z.writestr(name, data, compress_type)
        os.replace(tmp_path, docx_path)
    except Exception:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        raise


if __name__ == '__main__':
    main()
