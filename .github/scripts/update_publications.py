"""
ORCID Publication Updater
前田太郎 ORCID: 0000-0003-4185-0135

GitHub Actions から週次で実行され、index.html の
Publications セクションを最新データで更新します。
"""

import requests
import re
import json
from datetime import date

ORCID_ID = "0000-0003-4185-0135"
HTML_FILE = "index.html"

TYPE_LABELS = {
    "journal-article":  "査読論文",
    "conference-paper": "学会発表",
    "book-chapter":     "書籍章",
    "book":             "書籍",
    "preprint":         "プレプリント",
    "data-set":         "データセット",
    "other":            "その他",
}

ORCID_KEYWORDS = {
    "Sacoglossa", "Kleptoplasty", "Elysia", "Plakobranchus",
    "Genome", "Phenoklepty", "Sea slug", "Chloroplast",
}


def fetch_works(orcid_id: str) -> list[dict]:
    """ORCID Public API から論文リストを取得"""
    url = f"https://pub.orcid.org/v3.0/{orcid_id}/works"
    resp = requests.get(url, headers={"Accept": "application/json"}, timeout=20)
    resp.raise_for_status()
    data = resp.json()

    works = []
    for group in data.get("group", []):
        ws_list = group.get("work-summary", [])
        if not ws_list:
            continue
        ws = ws_list[0]  # 最初のサマリを使用

        ext_ids = (ws.get("external-ids") or {}).get("external-id", [])
        doi = next(
            (e.get("external-id-value", "") for e in ext_ids
             if e.get("external-id-type") == "doi"), ""
        )
        url_val = next(
            (e.get("external-id-url", {}).get("value", "") for e in ext_ids
             if e.get("external-id-type") == "uri"), ""
        )

        pub_date = ws.get("publication-date") or {}
        year = (pub_date.get("year") or {}).get("value", "")

        journal_obj = ws.get("journal-title")
        journal = journal_obj.get("value", "") if journal_obj else ""

        title_obj = ws.get("title", {}).get("title", {})
        title = title_obj.get("value", "(No title)") if title_obj else "(No title)"

        work_type = ws.get("type", "")

        works.append({
            "title":   title,
            "journal": journal,
            "year":    year,
            "doi":     doi,
            "url":     url_val,
            "type":    work_type,
        })

    # 年の降順でソート
    works.sort(key=lambda w: w["year"] or "0", reverse=True)
    return works


def render_pub_item(w: dict) -> str:
    """1件の論文 HTML を生成"""
    type_label = TYPE_LABELS.get(w["type"], "")

    # タイトル内キーワードで自動タグ付け
    auto_tags = [kw for kw in ORCID_KEYWORDS
                 if kw.lower() in w["title"].lower() or kw.lower() in w["journal"].lower()]
    tags_html = ""
    all_tags = ([type_label] if type_label else []) + auto_tags[:3]
    if all_tags:
        tags_html = '<div class="pub-tags">' + "".join(
            f'<span class="pub-tag">{t}</span>' for t in all_tags[:4]
        ) + "</div>"

    if w["doi"]:
        link = f'<a class="pub-link" href="https://doi.org/{w["doi"]}" target="_blank">DOI: {w["doi"]} →</a>'
    elif w["url"]:
        link = f'<a class="pub-link" href="{w["url"]}" target="_blank">Link →</a>'
    else:
        link = ""

    journal_html = f'<div class="pub-journal">{w["journal"]}</div>' if w["journal"] else ""
    return f"""
      <div class="pub-item reveal">
        <div class="pub-year">{w['year'] or '—'}</div>
        <div>
          <div class="pub-title">{w['title']}</div>
          <div class="pub-authors"><strong>Maeda T</strong> et al.</div>
          {journal_html}
          {tags_html}
          {link}
        </div>
      </div>"""


def build_pub_section(works: list[dict]) -> str:
    """論文セクション全体のHTMLを生成"""
    today = date.today().strftime("%Y年%m月%d日")
    items_html = "\n".join(render_pub_item(w) for w in works)

    return f"""
    <div class="pub-list">
      <div style="font-size:0.72rem; color:var(--text-light); margin-bottom:1.2rem; display:flex; align-items:center; gap:0.5rem;">
        <span style="display:inline-block; width:6px; height:6px; border-radius:50%; background:var(--green-light);"></span>
        ORCID より自動取得 — {today} 現在（{len(works)} 件）
      </div>
{items_html}

      <div class="pub-item reveal">
        <div class="pub-year">—</div>
        <div>
          <p style="font-size:0.82rem; color:var(--text-light); font-style:italic; margin-bottom:0.8rem;">全論文リストは ORCID・researchmap にて公開しています。</p>
          <div style="display:flex; gap:0.6rem; flex-wrap:wrap;">
            <a class="btn btn-ghost" href="https://orcid.org/0000-0003-4185-0135" target="_blank" style="font-size:0.72rem; padding:0.5rem 1rem;">ORCID →</a>
            <a class="btn btn-ghost" href="https://researchmap.jp/maedat_bio" target="_blank" style="font-size:0.72rem; padding:0.5rem 1rem;">researchmap →</a>
          </div>
        </div>
      </div>

    </div>"""


def update_html(html: str, pub_section_html: str) -> str:
    """index.html の pub-list ブロックを置換"""
    pattern = re.compile(
        r'(<section id="publications">.*?<div class="section-rule"></div>\s*</div>\s*)'  # header
        r'(<div class="pub-list">.*?</div>\s*)'                                          # pub-list
        r'(</div>\s*</section>)',                                                         # closing
        re.DOTALL
    )

    def replacer(m):
        return m.group(1) + pub_section_html + "\n  " + m.group(3)

    result, n = pattern.subn(replacer, html)
    if n == 0:
        raise ValueError("pub-list block not found in index.html — pattern may need updating.")
    return result


def main():
    print(f"Fetching works for ORCID {ORCID_ID}...")
    works = fetch_works(ORCID_ID)
    print(f"  → {len(works)} works retrieved")

    pub_html = build_pub_section(works)

    with open(HTML_FILE, encoding="utf-8") as f:
        html = f.read()

    updated = update_html(html, pub_html)

    with open(HTML_FILE, "w", encoding="utf-8") as f:
        f.write(updated)

    print(f"  → {HTML_FILE} updated successfully!")
    print("Works:")
    for w in works:
        print(f"  [{w['year']}] {w['title'][:70]}")


if __name__ == "__main__":
    main()
