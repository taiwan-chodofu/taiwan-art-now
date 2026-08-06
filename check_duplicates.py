"""manual_exhibitions.json / archive.json のソースデータ重複チェック。
新規展示追加後に毎回実行する。(museum, dates) が一致する組は同一展示の疑いとして報告する。
タイトルやアーティスト名が違っていても、同じ会場・同じ会期なら誤登録(別名義での重複追加等)を拾える。
"""
import json
import os
import sys
from collections import defaultdict

BASE = os.path.dirname(__file__)


def _load(name):
    path = os.path.join(BASE, name)
    with open(path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    return data.get('exhibitions', []) if isinstance(data, dict) else data


def _venue_key(ex):
    return (ex.get('museum', ''), (ex.get('dates') or '').strip())


def _title_key(ex):
    title = (ex.get('title_zh') or ex.get('title_en') or '').strip().lower()
    return title


def _label(ex):
    title = ex.get('title_zh') or ex.get('title_en') or '(no title)'
    artists = ', '.join(ex.get('artists', []) or [])
    return f"{title[:30]}" + (f" [{artists}]" if artists else "")


def _artist_overlap(a, b):
    sa, sb = set(a.get('artists', []) or []), set(b.get('artists', []) or [])
    if not sa or not sb:
        return False
    return bool(sa & sb)


def check_duplicates():
    """展示データの重複を2種類の観点でチェックする。

    1. EXACT DUP: 同一ファイル内で (museum, dates, title) が完全一致 — コピペミス等の事故的重複。
    2. LEFTOVER: archive.json に存在する展示が manual_exhibitions.json にまだ残っている
       — 「アーカイブしたら元ファイルから削除する」ルール違反。タイトルが違う場合は
       別名義での誤登録（今回のAlica Han/absenceの件）の可能性が高いため要確認マークを付ける。

    同一会場・同一会期でもタイトルが異なる場合(同時開催の別個展等)は正常なので、
    within-fileチェックではタイトル一致を必須条件にしてノイズを排除している。
    """
    manual = _load('manual_exhibitions.json')
    archive = _load('archive.json')

    issues = []

    # Check 1: 同一ファイル内の完全重複（museum + dates + title が一致）
    for name, exs in [('manual_exhibitions.json', manual), ('archive.json', archive)]:
        by_key = defaultdict(list)
        for ex in exs:
            if not isinstance(ex, dict):
                continue
            by_key[(_venue_key(ex), _title_key(ex))].append(ex)
        for (venue_key, title_key), group in by_key.items():
            if len(group) > 1 and title_key:
                museum, dates = venue_key
                labels = ' / '.join(_label(e) for e in group)
                issues.append(
                    f"[EXACT DUP in {name}] {museum} @ {dates}: {len(group)} entries — {labels}"
                )

    # Check 2: archive.json に移動済みなのに manual_exhibitions.json に残っている(削除漏れ)
    manual_by_venue = defaultdict(list)
    for ex in manual:
        if isinstance(ex, dict):
            manual_by_venue[_venue_key(ex)].append(ex)

    for ex in archive:
        if not isinstance(ex, dict):
            continue
        vkey = _venue_key(ex)
        if vkey not in manual_by_venue:
            continue
        museum, dates = vkey
        for m_ex in manual_by_venue[vkey]:
            same_title = _title_key(m_ex) == _title_key(ex) and _title_key(ex)
            if same_title:
                issues.append(
                    f"[LEFTOVER] {museum} @ {dates}: already in archive.json but still in "
                    f"manual_exhibitions.json — '{_label(m_ex)}' (remove from manual)"
                )
            elif _artist_overlap(m_ex, ex):
                issues.append(
                    f"[SUSPICIOUS - same venue/dates, different title, shared artist] "
                    f"{museum} @ {dates}: manual='{_label(m_ex)}' vs archive='{_label(ex)}' "
                    f"— possible duplicate under different attribution, verify manually"
                )

    if issues:
        print(f"Found {len(issues)} potential duplicate(s):\n")
        for issue in issues:
            print(issue)
    else:
        print("No duplicates found.")

    return issues


if __name__ == '__main__':
    issues = check_duplicates()
    sys.exit(1 if issues else 0)
