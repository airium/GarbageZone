from re import match
from time import sleep
from pathlib import Path

import requests                         # python3 -m pip install requests
from more_itertools import chunked      # python3 -m pip install more-itertools

from tu import fromTorrent              # https://raw.githubusercontent.com/airium/TorrentUtils/master/tu.py

# config
DIR4TORRENTS = Path()
U2API_URL = ''

# sanity check
assert DIR4TORRENTS.is_dir(), f'Error: {DIR4TORRENTS} not exists'
assert match(r'https://u2\.dmhy.org/jsonrpc_torrentkey\.php\?apikey=[0-9a-f]{64}', U2API_URL)

# start
paths2torrent = list(DIR4TORRENTS.glob('*.torrent'))
torrents = list(map(fromTorrent, paths2torrent))
req = []
for i, t in enumerate(torrents, start=1):
    req.append({"jsonrpc": "2.0", "method": "query", "params": [ t.hash ], "id": i})
res = []
for c in chunked(req, 100): # max 100 entries per request
    res += requests.post(U2API_URL, json=c).json()
    sleep(3) # minimum 2 sec between requests
for r, t, p in zip(res, torrents, paths2torrent):
    if key := r.get('result'):
        t.announce = f'https://tracker.dmhy.org/announce?secure={key}'
        t.write(p, overwrite=True)
    else:
        print(f'Error: {p.name} {r.get("error").get("code")} {r.get("error").get("message")}')
