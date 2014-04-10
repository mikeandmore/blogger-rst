#!/usr/bin/env python

import sys, os, getopt
import httplib2, simplejson
from oauth2client import client
from apiclient.discovery import build

from cStringIO import StringIO
from docutils.core import publish_string
from lxml import etree

ACCESS_TOKEN_FILE='access_token'

def auth_access_token():
    flow = client.flow_from_clientsecrets('./client_secret.json', scope='https://www.googleapis.com/auth/blogger', redirect_uri='urn:ietf:wg:oauth:2.0:oob')
    print('please enter the following uri into your browser: ')
    print(flow.step1_get_authorize_url())
    code = raw_input('code: ')
    cred = flow.step2_exchange(code)
    with file(ACCESS_TOKEN_FILE, 'w') as f:
        f.write(cred.access_token)
    return cred

def read_access_token():
    with open(ACCESS_TOKEN_FILE, 'r') as f:
        return client.AccessTokenCredentials(f.read(), None)

def login(cred, http):
    cred.authorize(http)
    return build('blogger', 'v3', http=http)

def list_blogs(service, http, target_name=None):
    print('')
    print('List of blogs: ')
    target_id = None
    for blog in service.blogs().listByUser(userId='self').execute(http)['items']:
        print('* ' + blog['name'])
        if target_name is not None and target_name == blog['name']:
            target_id = blog['id']
    return target_id

def publish_or_update(service, http, blog_id, title, body):
    post_id = None
    search_result = service.posts().search(blogId=blog_id, q=title, orderBy=None, fetchBodies=False).execute(http)['items']
    for result in search_result:
        if result['title'] == title:
            post_id = result['id']
            break
    o_body = {'title': title, 'content': body}
    res = None
    if post_id is None:
        print('Posting: ' + title)
        res = service.posts().insert(blogId=blog_id, body=o_body, isDraft=False)
    else:
        print('Updating post: ' + title)
        res = service.posts().update(blogId=blog_id, postId=post_id, body=o_body)
    res.execute(http)

def parse_rst(f):
    raw_html = publish_string(f.read(), writer_name='html', settings_overrides={'generator': False, 'traceback': True, 'syntax_highlight': 'short'})
    parser = etree.HTMLParser()
    tree = etree.parse(StringIO(raw_html), parser)
    docdiv = tree.xpath('/html/body/div')[0]
    h1node = docdiv.xpath('h1')[0]
    title = h1node.text
    docdiv.remove(h1node)
    return title, etree.tostring(docdiv)

def main():
    cred = None
    try:
        cred = read_access_token()
    except IOError, e:
        print("unable to read access_token")
        try:
            cred = auth_access_token()
        except client.FlowExchangeError, e:
            print('login failed!')
            sys.exit(-1)
    http = httplib2.Http()
    service = login(cred, http)
    
    user = service.users().get(userId='self').execute(http)
    print('Hello ' + user['displayName'] + ', you\'re logged in successfully')

    blog_name = None
    post_title = None
    post_content = None

    optlist, args = getopt.getopt(sys.argv[1:], 'b:f:')
    for opt, val in optlist:
        if opt == '-b':
            blog_name = val
        elif opt == '-f':
            with open(val, 'r') as f:
                post_title, post_content = parse_rst(f)
    blog_id = list_blogs(service, http, blog_name)
    if blog_id is None:
        if blog_name is not None:
            print('cannot find blog ' + blog_name)
            sys.exit(-1)
        sys.exit(0)
    print('')
    print('Choose to update blog: ' + blog_name)
    publish_or_update(service, http, blog_id, post_title, post_content)

if __name__ == '__main__':
    try:
        main()
    except client.AccessTokenCredentialsError, e:
        print('access_token expired')
        os.remove(ACCESS_TOKEN_FILE)
        sys.exit(-1)
