import concurrent.futures
import json
import tempfile
import threading
import unittest
import urllib.request
import urllib.error
from pathlib import Path
from http.server import ThreadingHTTPServer
from app import Store, Problem, handler

class Reservations(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.store=Store(Path(self.temp.name)/'test.db')
        self.data={'sala':1,'titulo':'Planejamento fictício','responsavel':'Equipe Aurora','inicio':'2026-11-05T09:00','fim':'2026-11-05T10:00','pessoas':4}
    def tearDown(self):self.temp.cleanup()
    def test_conflict_adjacent_and_other_room(self):
        self.store.create(self.data)
        with self.assertRaises(Problem) as e:self.store.create({**self.data,'inicio':'2026-11-05T09:30','fim':'2026-11-05T10:30'})
        self.assertEqual(e.exception.status,409)
        self.store.create({**self.data,'inicio':'2026-11-05T10:00','fim':'2026-11-05T11:00'})
        self.store.create({**self.data,'sala':2});self.assertEqual(len(self.store.list('2026-11-05')),3)
    def test_cancel_frees_interval_and_persistence(self):
        row=self.store.create(self.data);self.store.cancel(row['id']);self.store.create(self.data)
        self.assertEqual(len(Store(self.store.path).list('2026-11-05')),1)
        with self.assertRaises(Problem):self.store.cancel(row['id'])
    def test_validation(self):
        for fields in ({'sala':True},{'pessoas':True},{'pessoas':9},{'titulo':' '},{'inicio':'2026-02-30T09:00'},{'fim':'2026-11-05T08:30'},{'fim':'2026-11-06T10:00'},{'inicio':'2026-11-05T07:00'}):
            with self.subTest(fields=fields),self.assertRaises(Problem):self.store.create({**self.data,**fields})
    def test_concurrent_collision(self):
        def reserve(_):
            try:self.store.create(self.data);return 201
            except Problem as e:return e.status
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:statuses=list(pool.map(reserve,range(2)))
        self.assertEqual(sorted(statuses),[201,409])
        self.assertEqual(len(self.store.list('2026-11-05')),1)
    def test_http_roundtrip_and_malformed_json(self):
        server=ThreadingHTTPServer(('127.0.0.1',0),handler(self.store));t=threading.Thread(target=server.serve_forever,daemon=True);t.start()
        base='http://127.0.0.1:'+str(server.server_port)
        opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
        try:
            req=urllib.request.Request(base+'/api/reservas',data=json.dumps(self.data).encode(),headers={'Content-Type':'application/json'})
            with opener.open(req) as r:self.assertEqual(r.status,201)
            with opener.open(base+'/api/reservas?dia=2026-11-05') as r:self.assertEqual(len(json.load(r)),1)
            req=urllib.request.Request(base+'/api/reservas',data=b'{',headers={'Content-Type':'application/json'})
            with self.assertRaises(urllib.error.HTTPError) as e:opener.open(req)
            self.assertEqual(e.exception.code,400)
        finally:server.shutdown();server.server_close();t.join()
if __name__=='__main__':unittest.main()
