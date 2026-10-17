#!/usr/bin/env python3
"""Run real HTTP over a temporary loopback port, then close the listener."""
import argparse
import http.client
import json
import threading
from wsgiref.simple_server import make_server
from qimenllm.api.app import create_app
from qimenllm.cli import PrivateRequestHandler
from qimenllm.reasoning.service import QimenService


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--db',default='data/qimenllm.sqlite3')
    args=parser.parse_args()
    results=[]
    with make_server('127.0.0.1',0,create_app(QimenService(args.db)),handler_class=PrivateRequestHandler) as server:
        worker=threading.Thread(target=lambda:server.serve_forever(poll_interval=0.01),daemon=True)
        worker.start()
        try:
            for method,path,payload,expected in (
                ('GET','/health',None,'ok'),
                ('POST','/v1/ask',{'text':'工程空流程检查'},'blocked'),
                ('POST','/v1/learn',{'term':'工程空流程检查'},'awaiting_sources')):
                client=http.client.HTTPConnection('127.0.0.1',server.server_port,timeout=5)
                try:
                    body=None if payload is None else json.dumps(payload).encode()
                    client.request(method,path,body,{'Content-Type':'application/json'})
                    response=client.getresponse()
                    result=json.loads(response.read())
                    assert response.status==200,(path,response.status,result)
                    assert result['status']==expected,(path,result)
                    results.append({'path':path,'http_status':response.status,'status':result['status']})
                finally: client.close()
        finally:
            server.shutdown(); worker.join(timeout=5)
    print(json.dumps({'ok':True,'transport':'temporary_loopback_http','listener_closed':True,'results':results},indent=2))


if __name__=='__main__': main()
