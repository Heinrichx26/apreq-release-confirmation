"""Assemble the public code and data package for the APREQ confirmation study."""
import shutil, re, json
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
DST = ROOT / 'open_source_apreq'
SKIP = re.compile(r'(update_article|export_article|finalize_submission|revise_article|fetch_ntrs|check_release_sources|solver_probe|solver_audit|__pycache__|\.pyc$)')
def copy(src, dst=None):
    s = ROOT / src; d = DST / (dst or src)
    if s.is_file():
        d.parent.mkdir(parents=True, exist_ok=True); shutil.copy2(s, d); return
    for p in s.rglob('*'):
        if p.is_file() and not SKIP.search(p.as_posix()):
            q = d / p.relative_to(s); q.parent.mkdir(parents=True, exist_ok=True); shutil.copy2(p, q)
if DST.exists():
    for p in DST.iterdir():
        if p.name != '.git':
            shutil.rmtree(p) if p.is_dir() else p.unlink()
DST.mkdir(exist_ok=True)
for d in ['src/trb_error_20261030', 'src/trb_external_error_20261030', 'src/trb_information_transfer_20261030',
          'src/trb_calibrated_20261030', 'src/trb_transfer_20261030', 'src/opdi_trb',
          'src/figures/plot_apreq_evidence.py', 'src/figures/plot_restored_evidence.py', 'src/figures/export_apreq_concept.py',
          'data/opdi_trb/design.json', 'data/opdi_trb/cases', 'data/opdi_trb/processed/zurich_full.parquet', 'data/opdi_trb/processed/zurich_full.json',
          'data/trb_external_error_20261030', 'data/trb_transfer_20261030', 'data/trb_information_transfer_20261030',
          'results/opdi_trb', 'results/trb_external_error_20261030', 'results/trb_transfer_20261030']:
    copy(d)
for f in ['full.json', 'matched_full.json', 'adaptive_full.json', 'uncertainty_summary.json', 'range_check.json']:
    copy(f'results/trb_information_transfer_20261030/{f}')
copy('open_source_release/data/independent_adsb_q1/processed/airport_departures_2025_q1.csv', 'data/independent_adsb_q1/processed/airport_departures_2025_q1.csv')
copy('open_source_release/data/independent_adsb_q1/source_manifest.json', 'data/independent_adsb_q1/source_manifest.json')
u = DST / 'src/opdi_trb/us_travel.py'
u.write_text(u.read_text(encoding='utf-8').replace("open_source_release/data/independent_adsb_q1", "data/independent_adsb_q1"), encoding='utf-8')
for p in (DST / 'src').rglob('*.py'):
    t = p.read_text(encoding='utf-8')
    t = t.replace("'results/figures'", "'results/figures'").replace("ROOT / 'results' / 'tables'", "ROOT / 'results' / 'tables'").replace("ROOT / 'results/figures'", "ROOT / 'results/figures'").replace("ROOT / 'results/figures'", "ROOT / 'results/figures'")
    p.write_text(t, encoding='utf-8')
print(sum(1 for _ in DST.rglob('*') if _.is_file()), 'files')
