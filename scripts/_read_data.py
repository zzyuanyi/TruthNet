"""一次性读取所有比赛数据，UTF-8 编码。"""
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from pathlib import Path
import pandas as pd

BASE = Path(r'd:\projects\TruthNet\data\raw\比赛数据')

# === Folder 1 ===
print('=' * 80)
print('[Folder 1] clean.xlsx')
print('=' * 80)
path = BASE / '1' / 'clean.xlsx'
xl = pd.ExcelFile(path)
print(f'Sheets: {xl.sheet_names}')
for sheet in xl.sheet_names:
    df = pd.read_excel(xl, sheet_name=sheet)
    print(f'  Sheet [{sheet}]: shape={df.shape}')
    print(f'  Columns: {list(df.columns)}')
    print(df.head(3).to_string())
    print('  ...')
    print()

# === Folder 2 ===
print('=' * 80)
print('[Folder 2] clean.xlsx (shareholders)')
print('=' * 80)
path = BASE / '2' / 'clean.xlsx'
xl = pd.ExcelFile(path)
print(f'Sheets: {xl.sheet_names}')
for sheet in xl.sheet_names:
    df = pd.read_excel(xl, sheet_name=sheet)
    print(f'  Sheet [{sheet}]: shape={df.shape}')
    print(f'  Columns: {list(df.columns)}')
    print(df.head(3).to_string())
    print('  ...')
    print()

# === Folder 3 ===
print('=' * 80)
print('[Folder 3] clean.xlsx (announcements)')
print('=' * 80)
path = BASE / '3' / 'clean.xlsx'
xl = pd.ExcelFile(path)
print(f'Sheets: {xl.sheet_names}')
for sheet in xl.sheet_names:
    df = pd.read_excel(xl, sheet_name=sheet)
    print(f'  Sheet [{sheet}]: shape={df.shape}')
    print(f'  Columns: {list(df.columns)}')
    print(df.head(3).to_string())
    print('  ...')
    print()

# === Folder 4 ===
for fname, label in [
    ('asharebalancesheet_202605261517', 'Balance Sheet'),
    ('asharecashflow_202605261518', 'Cash Flow'),
    ('ashareincome_202605261519', 'Income Statement'),
]:
    print('=' * 80)
    print(f'[Folder 4] {fname}.csv ({label})')
    print('=' * 80)
    path = BASE / '4' / f'{fname}.csv'
    df = pd.read_csv(path, low_memory=False, nrows=5)
    print(f'Columns ({len(df.columns)}): {list(df.columns)}')
    print(df.head(2).to_string())
    print('...')
    print()

# === Folder 5 ===
print('=' * 80)
print('[Folder 5] rr_main_202605281537.csv (Research Reports)')
print('=' * 80)
path = BASE / '5' / 'rr_main_202605281537.csv'
df = pd.read_csv(path, low_memory=False, nrows=5)
print(f'Columns ({len(df.columns)}): {list(df.columns)}')
print(df.head(3).to_string())
print('...')
