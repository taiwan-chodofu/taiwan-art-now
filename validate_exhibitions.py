"""展示データの品質チェックスクリプト。
キャッシュリフレッシュ後に自動実行し、問題を検出してログに記録する。"""
import json
import os
import re
from collections import defaultdict
from datetime import datetime, timezone, timedelta

def validate_exhibitions():
    # cache.json はローカルの一時キャッシュ（6時間TTL、gitで管理されない）で
    # 古くなっていることが多く、これを検証してもmanual_exhibitions.jsonへの
    # 直近の変更は一切チェックされない（2026-08-26に発覚：cache.jsonが2日前の
    # 134件のまま、その間に171件まで追加されたデータが未検証だった）。
    # source of truthであるmanual_exhibitions.jsonを直接検証する。
    manual_path = os.path.join(os.path.dirname(__file__), 'manual_exhibitions.json')
    log_path = os.path.join(os.path.dirname(__file__), 'validation_log.txt')

    if not os.path.exists(manual_path):
        return

    with open(manual_path, 'r', encoding='utf-8') as f:
        manual = json.load(f)

    exhibitions = manual.get('exhibitions', [])
    issues = []
    
    # Check 1: Same artists appearing in multiple exhibitions at same museum
    by_museum = defaultdict(list)
    for ex in exhibitions:
        if not isinstance(ex, dict):
            continue
        artists = ex.get('artists', [])
        if artists:
            by_museum[ex.get('museum', '')].append({
                'title': ex.get('title_zh', '') or ex.get('title_en', ''),
                'artists': tuple(sorted(artists)),
            })
    
    for mid, exs in by_museum.items():
        if len(exs) < 2:
            continue
        # Check if any two exhibitions share the same artist set
        for i in range(len(exs)):
            for j in range(i+1, len(exs)):
                if exs[i]['artists'] == exs[j]['artists'] and len(exs[i]['artists']) > 2:
                    issues.append(
                        f"[DUPLICATE ARTISTS] {mid}: '{exs[i]['title'][:30]}' and '{exs[j]['title'][:30]}' share identical {len(exs[i]['artists'])} artists"
                    )
    
    # Check 2: UI/navigation junk in artist names
    junk_indicators = ['線上藝廊', '登入', '購物', '服務條款', '展覽回顧', '當期展覽']
    for ex in exhibitions:
        if not isinstance(ex, dict):
            continue
        for artist in ex.get('artists', []):
            if any(junk in artist for junk in junk_indicators):
                issues.append(
                    f"[JUNK ARTIST] {ex.get('museum','')}: '{ex.get('title_zh','')[:20]}' has junk artist name: '{artist}'"
                )
    
    # Check 3: Shared links (warning only)
    from collections import Counter
    links = [ex.get('link','') for ex in exhibitions if isinstance(ex, dict) and ex.get('link')]
    shared = {link: count for link, count in Counter(links).items() if count > 1}
    for link, count in shared.items():
        issues.append(
            f"[SHARED LINK] {count} exhibitions share link: {link[:60]}"
        )

    # Check 4: 必須フィールド欠落（生命線チェック）
    required_fields = {
        'title': lambda ex: ex.get('title_zh') or ex.get('title_en'),
        'dates': lambda ex: ex.get('dates'),
        'museum': lambda ex: ex.get('museum'),
        'link': lambda ex: ex.get('link'),
    }
    for ex in exhibitions:
        if not isinstance(ex, dict):
            continue
        title = ex.get('title_zh', '') or ex.get('title_en', '') or '(no title)'
        museum = ex.get('museum', '?')
        for field, check in required_fields.items():
            if not check(ex):
                issues.append(
                    f"[MISSING FIELD] {museum}: '{title[:30]}' is missing '{field}'"
                )
    
    # Check 5: 3言語完全性（description / description_en / description_ja）
    # performance/eventタイプ（venue_eventsとして別枠表示され、descriptionを使わない）は対象外
    for ex in exhibitions:
        if not isinstance(ex, dict):
            continue
        if ex.get('type') == 'performance' or 'events' in ex:
            continue
        title = ex.get('title_zh', '') or ex.get('title_en', '') or '(no title)'
        museum = ex.get('museum', '?')
        desc = (ex.get('description') or '').strip()
        desc_en = (ex.get('description_en') or '').strip()
        desc_ja = (ex.get('description_ja') or '').strip()
        if not desc and not desc_en and not desc_ja:
            issues.append(
                f"[NO DESCRIPTION AT ALL] {museum}: '{title[:30]}' has no description in any language"
            )
        elif desc and (not desc_en or not desc_ja):
            missing = [lang for lang, val in (('EN', desc_en), ('JA', desc_ja)) if not val]
            issues.append(
                f"[MISSING {'/'.join(missing)} TRANSLATION] {museum}: '{title[:30]}' has zh description but no {'/'.join(missing)}"
            )

    # Check 6: description(中文)欄への日本語混入（2026-08-27発覚: 一部展示のdescription
    # フィールドに、翻訳作成時の取り違いで日本語のかな・カタカナ交じり文がそのまま
    # 残っていた。全角中点(U+30FB)等は日中共通の記号なので誤検出防止のため除外し、
    # 実際のひらがな/カタカナ文字のみを検出対象にする。
    kana_pattern = re.compile(r'[ぁ-ゖァ-ヺ]')
    for ex in exhibitions:
        if not isinstance(ex, dict):
            continue
        desc = ex.get('description') or ''
        if kana_pattern.search(desc):
            title = ex.get('title_zh', '') or ex.get('title_en', '') or '(no title)'
            museum = ex.get('museum', '?')
            issues.append(
                f"[MIXED LANGUAGE IN ZH] {museum}: '{title[:30]}' description field contains Japanese kana"
            )

    # Write log
    if issues:
        tw_now = datetime.now(timezone(timedelta(hours=8))).strftime('%Y-%m-%d %H:%M')
        with open(log_path, 'a', encoding='utf-8') as f:
            f.write(f"\n--- Validation {tw_now} ---\n")
            for issue in issues:
                f.write(issue + '\n')
        print(f"Validation found {len(issues)} issues. See validation_log.txt")
    else:
        print('Validation passed: no issues found.')
    
    return issues


if __name__ == '__main__':
    validate_exhibitions()
