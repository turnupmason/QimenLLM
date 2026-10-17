"""Dependency-free WSGI research API. Serve on loopback only; not a public deployment."""
import json
from ..contracts import Inquiry


def create_app(service):
    def app(environ, start_response):
        status = '200 OK'
        try:
            path, method = environ.get('PATH_INFO',''), environ.get('REQUEST_METHOD','GET')
            if path=='/health' and method=='GET':
                result = {'status':'ok','phase':1 if service.knowledge.coverage()['chapters'] else 0,
                          'professional_analysis_available':False}
            elif path in ('/v1/ask','/v1/learn','/v1/calculate') and method=='POST':
                if environ.get('CONTENT_TYPE','').split(';')[0].strip()!='application/json':
                    raise ValueError('application/json required')
                length = int(environ.get('CONTENT_LENGTH','0'))
                if not 0 < length <= 65536: raise ValueError('Body must be 1..65536 bytes')
                body = environ['wsgi.input'].read(length)
                if len(body)!=length: raise ValueError('Incomplete request body')
                def reject_constant(value): raise ValueError('Nonfinite JSON constant')
                payload = json.loads(body,parse_constant=reject_constant)
                if not isinstance(payload,dict): raise ValueError('JSON object required')
                if path=='/v1/ask':
                    allowed = set(Inquiry.__dataclass_fields__)
                    if set(payload)-allowed: raise ValueError('Unknown inquiry field')
                    for key in allowed-{'context'}:
                        if key in payload and payload[key] is not None and not isinstance(payload[key],str):
                            raise ValueError(f'{key} must be a string')
                    if not isinstance(payload.get('context',{}),dict): raise ValueError('context must be an object')
                    result = service.ask(Inquiry(**payload))
                elif path=='/v1/learn':
                    if set(payload)!={'term'} or not isinstance(payload['term'],str): raise ValueError('term required')
                    result = service.learning.learn(payload['term'])
                else:
                    if set(payload)!={'operation','args'} or not isinstance(payload['operation'],str) or not isinstance(payload['args'],dict):
                        raise ValueError('operation string and args object required')
                    result=service.calculate(payload['operation'],payload['args'])
            else:
                status, result = '404 Not Found', {'error':'not_found'}
        except (ValueError,TypeError,UnicodeError,RecursionError):
            status, result = '400 Bad Request', {'error':'invalid_request'}
        except Exception:
            # Never expose exception text, SQL data, submitted text or credentials.
            status, result = '500 Internal Server Error', {'error':'internal_error'}
        encoded = json.dumps(result,ensure_ascii=False,allow_nan=False).encode('utf-8')
        start_response(status,[('Content-Type','application/json; charset=utf-8'),
            ('Content-Length',str(len(encoded))),('Cache-Control','no-store'),('X-Content-Type-Options','nosniff')])
        return [encoded]
    return app
