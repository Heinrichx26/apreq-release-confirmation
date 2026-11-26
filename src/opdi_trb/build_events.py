"""Build departure off-block and runway-entry records from OPDI v0.0.2."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import pandas as pd
import pyarrow.parquet as pq

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / 'data' / 'opdi' / 'extended' / 'raw'
OUT = ROOT / 'data' / 'opdi_trb' / 'processed'


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''):
            h.update(b)
    return h.hexdigest()


def flight_lists() -> pd.DataFrame:
    frames = [pq.read_table(p, columns=['id', 'adep']).to_pandas() for p in sorted(RAW.glob('flight_list_*.parquet'))]
    x = pd.concat(frames).drop_duplicates('id')
    x['id'] = x['id'].astype('uint64')
    x['adep'] = x['adep'].astype('string').str.upper()
    return x.set_index('id')


def read_events(path: Path) -> pd.DataFrame:
    rows = []
    for batch in pq.ParquetFile(path).iter_batches(batch_size=300_000, columns=['flight_id', 'type', 'event_time', 'info']):
        x = batch.to_pandas()
        x = x[x['type'].isin(['exit-parking_position', 'entry-runway'])]
        if not x.empty:
            x['airport'] = x['info'].astype('string').str.extract(r'"osm_airport"\s*:\s*"([^"]+)"', expand=False).str.upper()
            rows.append(x.drop(columns='info').dropna(subset=['airport']))
    return pd.concat(rows, ignore_index=True)


def build(files: list[Path], name: str) -> None:
    flights = flight_lists()
    events = pd.concat([read_events(p) for p in files], ignore_index=True)
    events['flight_id'] = events['flight_id'].astype('uint64')
    events = events.join(flights, on='flight_id', how='inner')
    events = events[events['airport'] == events['adep']]
    events['event_time'] = pd.to_datetime(events['event_time'], utc=True)
    exits = events[events['type'] == 'exit-parking_position'][['flight_id', 'airport', 'event_time']]
    runway = events[events['type'] == 'entry-runway'][['flight_id', 'airport', 'event_time']]
    pair = exits.merge(runway, on=['flight_id', 'airport'], suffixes=('_offblock', '_runway'))
    dt = (pair['event_time_runway'] - pair['event_time_offblock']).dt.total_seconds() / 60
    pair = pair[(dt >= 1) & (dt <= 120)].copy()
    pair['taxi_out_min'] = dt.loc[pair.index]
    pair = pair.sort_values(['flight_id', 'event_time_offblock', 'event_time_runway']).drop_duplicates('flight_id')
    pair = pair.rename(columns={'event_time_offblock': 'offblock_utc', 'event_time_runway': 'runway_entry_utc'})
    OUT.mkdir(parents=True, exist_ok=True)
    pair.to_parquet(OUT / f'{name}.parquet', index=False)
    meta = dict(source='EUROCONTROL Open Performance Data Initiative v0.0.2 flight events and flight lists',
                files=[dict(name=p.name, bytes=p.stat().st_size, sha256=sha256(p)) for p in files],
                records=int(len(pair)), airports=int(pair['airport'].nunique()),
                first_offblock=str(pair['offblock_utc'].min()), last_offblock=str(pair['offblock_utc'].max()),
                taxi_out_median=float(pair['taxi_out_min'].median()),
                taxi_out_p10=float(pair['taxi_out_min'].quantile(.1)),
                taxi_out_p90=float(pair['taxi_out_min'].quantile(.9)),
                rule='Departure-airport parking-position exit paired with the next same-airport runway entry between 1 and 120 minutes later')
    (OUT / f'{name}.json').write_text(json.dumps(meta, indent=2), encoding='utf-8')
    print(json.dumps(meta, indent=2))


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('name')
    ap.add_argument('files', nargs='+')
    a = ap.parse_args()
    build([RAW / f for f in a.files], a.name)
