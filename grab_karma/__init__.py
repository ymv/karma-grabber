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
            data = grabber.grab(user)
        except NotFoundError:
            dumper.not_found(user)
        except AuthError:
            die('Redirected. Cookie might be wrong or outdated')
        except Exception as e:
            die('Error: %s', e)
        else:
            dumper.found(user, data)
    dumper.end()

class Dumper(object):
    def start(self): pass
    def end(self): pass
    def found(self, user, data): pass
    def not_found(self, user): pass

class JSONDumper(Dumper):
    def start(self):
        self._buffer = {'timestamp': int(time.time()), 'users': {}}
    def end(self):
        json.dump(self._buffer, sys.stdout)
    def found(self, user, data):
        self._buffer['users'][user] = data
    def not_found(self, user):
        self._buffer['users'][user] = None

class TSVDumper(Dumper):
    def found(self, user, data):
        print '\t'.join(['%d' % time.time(), user, str(data['comment_karma']), str(data['karma'])])
    def not_found(self, user):
        print '\t'.join(['%d' % time.time(), user, 'not found'])

class AuthError(Exception): pass
class NotFoundError(Exception): pass

class Grabber(object):
    def __init__(self, cookie):
        self._con = httplib.HTTPConnection('leprosorium.ru')
        self._headers = {
            'Cookie': cookie,
            'User-Agent': 'Karmagrabber',
            'Connection': 'keep-alive',
        }

    def grab(self, user):
        data = self._load('/users/'+user)
        tree = lxml.html.document_fromstring(data)
        return self._parse(tree)

    def _load(self, url):
        self._con.request('GET', url, headers=self._headers)
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
        rating_match = re.search(u'([-\d]+).+?([-\d]+).+?([-\d]+)', tree.cssselect('.userrating')[0].text_content())
        return {
            'karma': int(tree.cssselect('.uservoteholder span em')[0].text),
            'comment_karma': int(rating_match.group(3)),
            'post_count': int(rating_match.group(1)),
            'comment_count': int(rating_match.group(2)),
            'parent': tree.cssselect('.userparent a')[0].text,
            'kids': [e.text for e in tree.cssselect('.userchildren a')],
        }

if __name__ == '__main__':
    main()
