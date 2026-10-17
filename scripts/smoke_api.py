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
    parser.add_argument('--chapter01',action='store_true',help='Check the actual supplied chapter in addition to the empty query')
    parser.add_argument('--chapter02',action='store_true',help='Check both chapter-two source plates through real HTTP')
    args=parser.parse_args()
    results=[]
    with make_server('127.0.0.1',0,create_app(QimenService(args.db)),handler_class=PrivateRequestHandler) as server:
        worker=threading.Thread(target=lambda:server.serve_forever(poll_interval=0.01),daemon=True)
        worker.start()
        try:
            checks=[
                ('GET','/health',None,'ok'),
                ('POST','/v1/ask',{'text':'工程空流程检查'},'blocked'),
                ('POST','/v1/learn',{'term':'工程空流程检查'},'awaiting_sources')]
            if args.chapter01:
                checks.extend([
                    ('POST','/v1/learn',{'term':'符头'},'sources_found'),
                    ('POST','/v1/calculate',{'operation':'duty','args':{
                        'dun':'阳遁','bureau':1,'hour_ganzhi':'壬寅'}},'computed')])
            if args.chapter02:
                checks.append(('POST','/v1/learn',{'term':'五鼠遁'},'sources_found'))
                for dun,bureau,hour in (('阳遁',3,'丁巳'),('阴遁',8,'戊戌')):
                    checks.append(('POST','/v1/calculate',{'operation':'symbolic_chart','args':{
                        'dun':dun,'bureau':bureau,'hour_ganzhi':hour,'method':'shenqi_ch2_paper_v1'}},'computed'))
                checks.append(('POST','/v1/ask',{'text':'来源演算检查','casting_method':'shenqi_ch2_paper_v1',
                    'context':{'dun':'阴遁','bureau':8,'hour_ganzhi':'戊戌'}},'blocked'))
            for method,path,payload,expected in checks:
                client=http.client.HTTPConnection('127.0.0.1',server.server_port,timeout=5)
                try:
                    body=None if payload is None else json.dumps(payload).encode()
                    client.request(method,path,body,{'Content-Type':'application/json'})
                    response=client.getresponse()
                    result=json.loads(response.read())
                    assert response.status==200,(path,response.status,result)
                    assert result['status']==expected,(path,result)
                    if path=='/v1/calculate':
                        assert result['evidence'] and not result['complete_chart'],result
                        if payload['operation']=='duty':
                            assert result['result']['zhifu_landing_palace']==5,result
                        else:
                            chart=result['result']
                            assert chart['plate_layout_complete'] and chart['validation_status']=='symbolic_verified',result
                            assert len(chart['palaces'])==9 and chart['palaces']['5']['heaven_stars']==[],result
                    if path=='/v1/ask' and payload.get('casting_method'):
                        assert result['chart_id'] and result['chart']['validation_status']=='symbolic_verified',result
                    results.append({'path':path,'http_status':response.status,'status':result['status']})
                finally: client.close()
        finally:
            server.shutdown(); worker.join(timeout=5)
    print(json.dumps({'ok':True,'transport':'temporary_loopback_http','listener_closed':True,'results':results},indent=2))


if __name__=='__main__': main()
