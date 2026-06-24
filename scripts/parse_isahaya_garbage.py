#!/usr/bin/env python3
"""
諫早市ごみ収集カレンダーPDFから燃えないごみの日付を抽出するスクリプト

使い方:
  python parse_isahaya_garbage.py
  python parse_isahaya_garbage.py --pdf-file /path/to/calendar.pdf
  python parse_isahaya_garbage.py --pdf-url URL --year 2026
"""

import re
import json
import argparse
import sys
import requests
import pdfplumber
from icalendar import Calendar, Event
from datetime import date, timedelta
from io import BytesIO
import os

DEFAULT_PDF_URL = "https://www.city.isahaya.nagasaki.jp/uploaded/attachment/24461.pdf"
DEFAULT_ZONE = "栄田町"

WEEKDAY_MAP = {"月": 0, "火": 1, "水": 2, "木": 3, "金": 4, "土": 5, "日": 6}

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "application/pdf,*/*",
    "Accept-Language": "ja,en;q=0.9",
    "Referer": "https://www.city.isahaya.nagasaki.jp/soshiki/38/1795.html",
}


def download_pdf(url: str) -> bytes:
    print(f"ダウンロード中: {url}")
    resp = requests.get(url, headers=HEADERS, timeout=60)
    resp.raise_for_status()
    return resp.content


def nth_weekday_of_month(year: int, month: int, weekday: int, n: int) -> date | None:
    """指定月のn番目の曜日の日付を返す（存在しない場合はNone）"""
    first = date(year, month, 1)
    offset = (weekday - first.weekday()) % 7
    d = first + timedelta(days=offset + (n - 1) * 7)
    return d if d.month == month else None


def fiscal_year_months(base_year: int) -> list[tuple[int, int]]:
    """年度の月リスト（4月〜翌3月）を (year, month) タプルで返す"""
    months = []
    for offset in range(12):
        month = (offset + 3) % 12 + 1
        year = base_year if month >= 4 else base_year + 1
        months.append((year, month))
    return months


def expand_weekly_pattern(pattern: str, base_year: int) -> list[str]:
    """
    「第2・4水曜日」「毎週火曜日」などのパターンを年度分の日付に展開する
    """
    weekday_match = re.search(r'([月火水木金土日])曜日', pattern)
    if not weekday_match:
        return []
    weekday = WEEKDAY_MAP[weekday_match.group(1)]

    week_nums_found = re.findall(r'第(\d)', pattern)
    if week_nums_found:
        week_nums = [int(n) for n in week_nums_found]
    elif "毎週" in pattern:
        week_nums = [1, 2, 3, 4, 5]
    else:
        return []

    dates = []
    for year, month in fiscal_year_months(base_year):
        for n in week_nums:
            d = nth_weekday_of_month(year, month, weekday, n)
            if d:
                dates.append(d.isoformat())
    return sorted(dates)


def extract_from_weekday_table(text: str, base_year: int) -> list[str]:
    """
    「燃えないごみ 第2・4 水曜日」形式のテーブルからパターンを抽出
    """
    lines = text.split("\n")
    funen_pattern = None

    for i, line in enumerate(lines):
        if re.search(r"燃えない(ごみ|ゴミ)|不燃(ごみ|ゴミ)", line):
            context = " ".join(lines[i : i + 4])
            match = re.search(
                r"(第[1-5][\s・、,第1-5]*[月火水木金土日]曜日|毎週[月火水木金土日]曜日)",
                context,
            )
            if match:
                funen_pattern = match.group(0)
                break

    if funen_pattern:
        return expand_weekly_pattern(funen_pattern, base_year)
    return []


def extract_from_date_list(text: str, base_year: int) -> list[str]:
    """
    「4月：8日・22日 5月：13日・27日...」形式から日付を抽出
    """
    dates = []
    # 燃えないごみのセクションを探す
    funen_section = re.search(
        r"燃えない(ごみ|ゴミ)[^\n]*\n(.*?)(?=燃え|可燃|資源|$)",
        text,
        re.DOTALL,
    )
    if not funen_section:
        return []

    section_text = funen_section.group(0)
    # 月と日付のペアを抽出
    for m in re.finditer(r"(\d{1,2})月[^0-9]*?([\d・、,\s]+)日", section_text):
        month = int(m.group(1))
        days_str = m.group(2)
        days = [int(d) for d in re.findall(r"\d+", days_str)]
        year = base_year if month >= 4 else base_year + 1
        for day in days:
            try:
                dates.append(date(year, month, day).isoformat())
            except ValueError:
                pass
    return sorted(dates)


def parse_pdf(pdf_bytes: bytes, base_year: int) -> list[str]:
    """PDFから燃えないごみの日付を抽出（複数の解析戦略を試みる）"""
    all_text = []
    all_tables = []

    with pdfplumber.open(BytesIO(pdf_bytes)) as pdf:
        print(f"PDFページ数: {len(pdf.pages)}")
        for page_num, page in enumerate(pdf.pages, 1):
            text = page.extract_text() or ""
            all_text.append(text)
            for table in page.extract_tables():
                for row in table:
                    if row:
                        all_tables.append(
                            " ".join(str(c) for c in row if c)
                        )

    full_text = "\n".join(all_text + all_tables)

    # 戦略1: 曜日パターン（例: 第2・4水曜日）
    dates = extract_from_weekday_table(full_text, base_year)
    if dates:
        print(f"曜日パターンで{len(dates)}件抽出")
        return dates

    # 戦略2: 日付リスト（例: 4月：8日・22日）
    dates = extract_from_date_list(full_text, base_year)
    if dates:
        print(f"日付リストで{len(dates)}件抽出")
        return dates

    print("警告: 自動抽出に失敗しました")
    print("抽出されたテキストのサンプル（最初の500文字）:")
    print(full_text[:500])
    return []


def generate_ics(dates: list[str], zone: str) -> str:
    cal = Calendar()
    cal.add("prodid", "-//諫早市燃えないごみカレンダー//JP")
    cal.add("version", "2.0")
    cal.add("X-WR-CALNAME", f"燃えないごみ ({zone})")
    cal.add("X-WR-TIMEZONE", "Asia/Tokyo")

    for date_str in dates:
        event = Event()
        event.add("summary", "燃えないごみ")
        event.add("dtstart", date.fromisoformat(date_str))
        event.add("dtend", date.fromisoformat(date_str) + timedelta(days=1))
        event.add("description", f"諫早市 {zone} 燃えないごみ収集日")
        cal.add_component(event)

    return cal.to_ical().decode()


def main():
    parser = argparse.ArgumentParser(description="諫早市ごみカレンダーPDF解析")
    parser.add_argument("--pdf-url", default=DEFAULT_PDF_URL, help="PDFのURL")
    parser.add_argument("--pdf-file", help="ローカルPDFファイルパス（URLより優先）")
    parser.add_argument("--zone", default=DEFAULT_ZONE, help="収集地区名")
    parser.add_argument(
        "--year",
        type=int,
        default=date.today().year,
        help="年度の開始年（例: 2026なら2026年4月〜2027年3月）",
    )
    parser.add_argument("--output-dir", default="docs", help="出力ディレクトリ")
    args = parser.parse_args()

    if args.pdf_file:
        with open(args.pdf_file, "rb") as f:
            pdf_bytes = f.read()
        print(f"ローカルファイルを使用: {args.pdf_file}")
    else:
        try:
            pdf_bytes = download_pdf(args.pdf_url)
        except requests.HTTPError as e:
            print(f"エラー: PDFダウンロード失敗 ({e})")
            print("--pdf-file でローカルファイルを指定してください")
            sys.exit(1)

    dates = parse_pdf(pdf_bytes, args.year)

    os.makedirs(args.output_dir, exist_ok=True)

    calendar_data = {
        "generated_at": date.today().isoformat(),
        "zone": args.zone,
        "year": args.year,
        "pdf_url": args.pdf_url if not args.pdf_file else None,
        "funen_dates": dates,
        "count": len(dates),
    }

    json_path = os.path.join(args.output_dir, "calendar.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(calendar_data, f, ensure_ascii=False, indent=2)
    print(f"JSON出力: {json_path} ({len(dates)}件)")

    ics_path = os.path.join(args.output_dir, "isahaya_funen.ics")
    with open(ics_path, "w", encoding="utf-8") as f:
        f.write(generate_ics(dates, args.zone))
    print(f"ICS出力: {ics_path}")

    if not dates:
        print("\n日付が抽出できませんでした。")
        print("PDFをダウンロードして --pdf-file で指定し、")
        print("スクリプトを再実行してください。")
        sys.exit(1)


if __name__ == "__main__":
    main()
