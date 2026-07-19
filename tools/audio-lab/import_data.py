import argparse
from eventmonitor.importer import import_package, import_folder
p=argparse.ArgumentParser(); p.add_argument('source'); p.add_argument('--folder',action='store_true'); a=p.parse_args()
if a.folder:
    for row in import_folder(a.source): print(*row,sep=' | ')
else:
    rid,created=import_package(a.source); print(f'Aufnahme #{rid}: '+('importiert' if created else 'bereits vorhanden'))
