"""展示データの品質チェックスクリプト。
キャッシュリフレッシュ後に自動実行し、問題を検出してログに記録する。"""
import json
import os
from collections import defaultdict
from datetime import datetime, timezone, timedelta

def validate_exhibitions():
    cache_path = os.path.join(os.path.dirname(__file__), 'cache.json')
    log_path = os.path.join(os.path.dirname(__file__), 'validation_log.txt')
    
    if not os.path.exists(cache_path):
        return
    
    with open(cache_path, 'r', encoding='utf-8') as f:
        cache = json.load(f)
    
    exhibitions = cache.get('exhibitions', [])
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
