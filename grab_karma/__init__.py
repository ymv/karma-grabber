#!/usr/bin/env python
#encoding: utf-8
import os
import os.path
import sys
import argparse
import time
import re
import httplib
import json
import lxml.html
import urllib

def load_cookie(path=None):
    paths = [path] if path is not None else [os.path.expanduser('~/.leper/auth_cookie'), './auth_cookie']
    for path in paths:
        if os.path.exists(path):
            with open(path, 'r') as f:
                return f.read().strip()
    return None

def die(msg, *argv):
    sys.stderr.write(msg % argv + '\n')
    sys.exit(1)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('users', nargs='+', help='User names to scan')
    parser.add_argument('--cookie', help='Auth cookie file (default to ~/.leper/auth_cookie or ./auth_cookie)')
    parser.add_argument('--json', dest='dumper', action='store_const', const=JSONDumper, default=TSVDumper, help='Dump to JSON (default to TSV)')
    args = parser.parse_args()

    cookie = load_cookie(args.cookie)
    if not cookie:
        die('Cookie file not found')

    grabber = Grabber(cookie)
    dumper = args.dumper()
    dumper.start()
    for user in args.users:
        try:
            data = grabber.grab(user, dumper.voters)
        except NotFoundError:
            dumper.not_found(user)
        except AuthError:
            die('Redirected. Cookie might be wrong or outdated')
        #except Exception as e:
        #    die('Error: %s', e)
        else:
            dumper.found(user, data)
    dumper.end()

class Dumper(object):
    voters = False
    def start(self): pass
    def end(self): pass
    def found(self, user, data): pass
    def not_found(self, user): pass

class JSONDumper(Dumper):
    voters = True
    def start(self):
        self._buffer = {'timestamp': int(time.time()), 'users': {}}
    def end(self):
        json.dump(self._buffer, sys.stdout)
    def found(self, user, data):
        self._buffer['users'][user] = data
    def not_found(self, user):
        self._buffer['users'][user] = None

class TSVDumper(Dumper):
    voters = False
    def found(self, user, data):
        print '\t'.join(['%d' % time.time(), user, str(data['comment_karma']), str(data['karma'])])
    def not_found(self, user):
        print '\t'.join(['%d' % time.time(), user, 'not found'])

class AuthError(Exception): pass
class NotFoundError(Exception): pass

class Grabber(object):
    def __init__(self, cookie):
        self._con = httplib.HTTPSConnection('leprosorium.ru')
        self._headers = {
            'Cookie': cookie,
            'User-Agent': 'Karmagrabber',
            'Connection': 'keep-alive',
        }

    def grab(self, user, voters):
        data = self._load('/users/'+user, None)
        tree = lxml.html.document_fromstring(data)
        r = self._parse(tree)
        if voters:
            scripts = tree.xpath('//script/text()')
            for s in scripts:
                csrf_match = re.search(ur"csrf_token\s*:\s*'([^']+)'", s)
                if csrf_match:
                    csrf = csrf_match.group(1)
                    break
            else:
                raise Exception('CSRF token not found')
            r['voters'] = self._grab_voters(r['id'], csrf)
        return r

    def _grab_voters(self, user_id, csrf):
        q = {
            'limit': '100500',
            'offset': '0',
            'csrf_token': csrf,
            'user': str(user_id)
        }
        data = self._load('/ajax/user/karma/list/', urllib.urlencode(q))
        obj = json.loads(data)
        return {x['user']['login']: int(x['vote'])*sign for sign, f in [(1, 'pros'), (-1, 'cons')] for x in (obj[f] or [])}

    def _load(self, url, data):
        if data is None:
            self._con.request('GET', url, headers=self._headers)
        else:
            headers = dict(self._headers)
            headers['Content-Type'] = 'application/x-www-form-urlencoded'
            self._con.request('POST', url, body=data, headers=headers)
        response = self._con.getresponse()
        data = response.read()
        if response.status == 404:
            raise NotFoundError()
        elif response.status == 302:
            raise AuthError()
        elif response.status != 200:
            raise Exception("Bad http code: %d %s" % (response.status, response.reason))
        return data

    def _parse(self, tree):
        rating_match = re.search(u'([-\d]+).+?([-\d]+).+?([-\d]+)', tree.cssselect('.b-user_stat')[0].text_content(), re.DOTALL)
        id_match = re.search(u'#([.\d]+)', tree.xpath('.//td[@class="b-table-cell"][h2]')[0].text_content())
        parents = tree.cssselect('.b-user_parent a')
        return {
            'id': int(id_match.group(1).replace('.','')),
            'karma': int(tree.cssselect('#js-karma')[0].text),
            'comment_karma': int(rating_match.group(3)),
            'post_count': int(rating_match.group(1)),
            'comment_count': int(rating_match.group(2)),
            'parent': parents[0].text if parents else None,
            'kids': [e.text for e in tree.cssselect('.b-user_children a')],
        }

if __name__ == '__main__':
    main()
