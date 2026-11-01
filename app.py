"""Sala Certa: demonstração local de reservas, API JSON e SQLite."""
from contextlib import closing
import argparse
import json
import re
import sqlite3
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit, parse_qs

BASE=Path(__file__).resolve().parent
ROOMS=[{'id':1,'nome':'Horizonte','capacidade':8},{'id':2,'nome':'Jardim','capacidade':4},{'id':3,'nome':'Estúdio','capacidade':12}]
class Problem(Exception):
    def __init__(self,message,status=422):self.status=status;super().__init__(message)
class Store:
    def __init__(self,path):
        self.path=str(path)
        with closing(self.connect()) as c:
            c.execute('CREATE TABLE IF NOT EXISTS reservas(id INTEGER PRIMARY KEY, sala INTEGER NOT NULL, titulo TEXT NOT NULL, responsavel TEXT NOT NULL, inicio TEXT NOT NULL, fim TEXT NOT NULL, pessoas INTEGER NOT NULL, cancelada INTEGER NOT NULL DEFAULT 0)')
    def connect(self):
        c=sqlite3.connect(self.path,timeout=10);c.row_factory=sqlite3.Row;return c
    def list(self,day):
        try:datetime.strptime(day,'%Y-%m-%d')
        except (ValueError,TypeError):raise Problem('Data inválida. Use AAAA-MM-DD.')
        with closing(self.connect()) as c:return [dict(r) for r in c.execute('SELECT * FROM reservas WHERE substr(inicio,1,10)=? AND cancelada=0 ORDER BY inicio,sala',(day,))]
    def create(self,data):
        if not isinstance(data,dict):raise Problem('Envie um objeto JSON.')
        sala,pessoas=data.get('sala'),data.get('pessoas')
        if type(sala) is not int or sala not in (1,2,3):raise Problem('Sala inválida.')
        room=ROOMS[sala-1]
        if type(pessoas) is not int or not 1<=pessoas<=room['capacidade']:raise Problem('Quantidade acima da capacidade ou inválida.')
        fields=[]
        for key in ('titulo','responsavel'):
            v=data.get(key)
            if not isinstance(v,str) or not 1<=len(v.strip())<=80:raise Problem('Título e responsável devem ter de 1 a 80 caracteres.')
            fields.append(v.strip())
        times=[]
        for key in ('inicio','fim'):
            v=data.get(key)
            if not isinstance(v,str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}',v):raise Problem('Horário inválido.')
            try:times.append(datetime.strptime(v,'%Y-%m-%dT%H:%M'))
            except ValueError:raise Problem('Data ou horário inexistente.')
        start,end=times
        if start.date()!=end.date() or start>=end or start.hour<8 or end.hour>19 or (end.hour==19 and end.minute):raise Problem('Use o mesmo dia, entre 08h e 19h, com fim após início.')
        c=self.connect()
        try:
            c.execute('BEGIN IMMEDIATE')
            exists=c.execute('SELECT id FROM reservas WHERE sala=? AND cancelada=0 AND inicio<? AND fim>?',(sala,data['fim'],data['inicio'])).fetchone()
            if exists:raise Problem('Esta sala já tem uma reserva nesse intervalo. Escolha outro horário ou sala.',409)
            row=c.execute('INSERT INTO reservas(sala,titulo,responsavel,inicio,fim,pessoas) VALUES(?,?,?,?,?,?)',(sala,*fields,data['inicio'],data['fim'],pessoas))
            result=dict(c.execute('SELECT * FROM reservas WHERE id=?',(row.lastrowid,)).fetchone());c.commit();return result
        except Exception:c.rollback();raise
        finally:c.close()
    def cancel(self,identity):
        with closing(self.connect()) as c:
            cur=c.execute('UPDATE reservas SET cancelada=1 WHERE id=? AND cancelada=0',(identity,))
            if not cur.rowcount:raise Problem('Reserva ativa não encontrada.',404)
            c.commit()

def handler(store):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args):pass
        def reply(self,status,payload,kind='application/json; charset=utf-8'):
            body=json.dumps(payload,ensure_ascii=False).encode() if kind.startswith('application/json') else payload
            self.send_response(status);self.send_header('Content-Type',kind);self.send_header('Content-Length',str(len(body)));self.send_header('Cache-Control','no-store');self.send_header('X-Content-Type-Options','nosniff');self.end_headers();self.wfile.write(body)
        def do_GET(self):
            target=urlsplit(self.path)
            try:
                if target.path=='/':return self.reply(200,(BASE/'index.html').read_bytes(),'text/html; charset=utf-8')
                if target.path=='/api/salas':return self.reply(200,ROOMS)
                if target.path=='/api/reservas':return self.reply(200,store.list(parse_qs(target.query).get('dia',[''])[0]))
                self.reply(404,{'erro':'Recurso não encontrado.'})
            except Problem as e:self.reply(e.status,{'erro':str(e)})
        def do_POST(self):
            # Rejeita chamadas de outras origens ao servidor local.
            origin=self.headers.get('Origin')
            if origin and origin!='http://'+self.headers.get('Host',''):return self.reply(403,{'erro':'Origem não permitida.'})
            try:
                if self.path=='/api/reservas':
                    if self.headers.get('Content-Type','').split(';')[0]!='application/json':raise Problem('Use application/json.',415)
                    try:length=int(self.headers.get('Content-Length','0'))
                    except ValueError:raise Problem('Tamanho inválido.',400)
                    if not 0<length<=16384:raise Problem('Corpo vazio ou excessivo.',413)
                    try:data=json.loads(self.rfile.read(length))
                    except (ValueError,UnicodeDecodeError):raise Problem('JSON inválido.',400)
                    return self.reply(201,store.create(data))
                match=re.fullmatch(r'/api/reservas/(\d+)/cancelar',self.path)
                if match:store.cancel(int(match[1]));return self.reply(200,{'mensagem':'Reserva cancelada.'})
                self.reply(404,{'erro':'Recurso não encontrado.'})
            except Problem as e:self.reply(e.status,{'erro':str(e)})
    return Handler
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--banco',default=str(BASE/'reservas.db'));p.add_argument('--porta',type=int,default=8771);a=p.parse_args()
    server=ThreadingHTTPServer(('127.0.0.1',a.porta),handler(Store(a.banco)))
    print(f'Sala Certa: http://127.0.0.1:{a.porta}',flush=True)
    try:server.serve_forever()
    except KeyboardInterrupt:pass
    finally:server.server_close()
