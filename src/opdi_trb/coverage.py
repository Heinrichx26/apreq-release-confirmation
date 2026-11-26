"""Daily coverage and travel-time summary for the OPDI departure records."""
import sys
import pandas as pd

x = pd.read_parquet(sys.argv[1])
x['local'] = x['offblock_utc'].dt.tz_convert('Europe/Zurich')
x['day'] = x['local'].dt.date
x['hour'] = x['local'].dt.hour
for ap in ['LSZH', 'EDDS', 'LFPO']:
    y = x[x.airport == ap]
    d = y.groupby('day').size()
    print(ap, 'days', len(d), 'min/median/max per day', d.min(), d.median(), d.max())
    print(' taxi p10/p50/p90', y.taxi_out_min.quantile([.1, .5, .9]).round(2).tolist())
    print(' per local hour mean', (y.groupby('hour').size() / len(d)).round(1).to_dict())
    print(' low days', d[d < d.median() * .6].to_dict())
