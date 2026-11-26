"""Summarize OPDI event coverage by airport and event type."""
import sys
import pandas as pd
import pyarrow.parquet as pq

t = pq.read_table(sys.argv[1], columns=['type', 'info']).to_pandas()
t['airport'] = t['info'].astype('string').str.extract(r'"osm_airport"\s*:\s*"([^"]+)"', expand=False)
print(t['type'].value_counts())
top = t['airport'].value_counts().head(25).index
print(pd.crosstab(t.loc[t.airport.isin(top), 'airport'], t.loc[t.airport.isin(top), 'type']))
