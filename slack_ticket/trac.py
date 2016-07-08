"""
Talk with trac over http, just like a normal user.
"""

import os
import time
import logging
from datetime import datetime, timedelta
from contextlib import contextmanager
from pprint import pprint

import requests

def get(url, username=None, password=None, session=None, **params):
    if not session:
        session = requests
    kwargs = {'timeout': 10}
    if username and password:
        kwargs['auth'] = (username, password)
    if params:
        kwargs['params'] = params
    logging.info('GET for %s, args: %r',url,kwargs)
    r = session.get(url, **kwargs)
    r.raise_for_status()
    return r

def post(url, username=None, password=None, session=None, **params):
    if not session:
        session = requests
    kwargs = {'timeout': 10}
    if username and password:
        kwargs['auth'] = (username, password)
    if params:
        kwargs['data'] = params
    logging.info('POST for %s, args: %r',url,kwargs)
    r = session.post(url, **kwargs)
    r.raise_for_status()
    return r


@contextmanager
def start_session(url):
    s = requests.Session()
    with open(os.path.join(os.path.dirname(__file__),'.tracauth')) as f:
        u,p = f.read().split()
    get(url, username=u, password=p, session=s)
    yield s


TicketConstants = {
    'type': ['defect', 'enhancement', 'task', 'rumor / allegation', 'cleanup'],
    'priority': ['blocker', 'critical', 'major', 'normal', 'minor', 'trivial'],
    'component': ['cmake', 'icecube offline', 'icerec', 'infrastructure', 'jeb + pnf', 'other', 'simulation', 'tools/ports'],
}

base_url = 'http://code.icecube.wisc.edu/projects/icecube/'

def get_users():
    """
    Get a list of names/usernames for trac
    
    Returns:
        dict: {real name: username}
    """
    r = get(os.path.join(base_url,'subjects'))
    users = {}
    for line in r.text.split('\n'):
        parts = line.split('|')
        name = ' '.join(parts[-1].split())
        if name:
            users[name] = parts[0]
    return users

def new_ticket(summary=None, reporter='icecube', description=None,
               type=None, priority=None, milestone=None,
               component=None, keywords='', cc='',
               owner='', dry_run=False):

    if not summary and not description:
        raise Exception('need summary or description')
    if not summary:
        summary = description.split('. ',1)[0]
    if not description:
        description = summary
        
    users = get_users()
    if reporter in users:
        reporter = users[reporter]

    def locate(phrases):
        s = summary.lower()+description.lower()
        return any(p in s for p in phrases)

    def find_phrase(phrases, valid=None):
        for phrase in phrases:
            pos = description.find(phrase)
            if pos >= 0:
                pos += len(phrase)
                while pos < len(description) and description[pos] == ' ':
                    pos += 1
                pos2 = description.find(' ',pos)
                if pos2 > 0:
                    ret = description[pos:pos2]
                else:
                    ret = description[pos:]
                if valid:
                    ret = ret.lower()
                    if ret not in valid:
                        continue
                return ret
        raise Exception('phrases not found')

    if type:
        type = type.lower()
        if type not in TicketConstants['type']:
            raise Exception('invalid type')
    else:
        type = 'rumor / allegation'
        for t in TicketConstants['type']:
            if locate([t]):
                type = t
                break
        else:
            if locate(['bug','fix','error','broke']):
                type = 'defect'
            elif locate(['idea','what if','new','feature']):
                type = 'enhancement'
            elif locate(['todo','cleanup','clean up']):
                type = 'cleanup'

    if priority:
        priority = priority.lower()
        if priority not in TicketConstants['priority']:
            raise Exception('invalid priority')
    else:
        priority = 'normal'
        for p in TicketConstants['priority']:
            if locate([p]):
                priority = p
                break
        else:
            if type == 'defect':
                priority = 'major'

    if not milestone:
        d = datetime.now()+timedelta(days=1)
        milestone = d.strftime(format='%B %Y')

    if component:
        component = component.lower()
        if component not in TicketConstants['component']:
            raise Exception('invalid component')
    else:
        component = 'icerec'
        for c in TicketConstants['component']:
            if locate([c]):
                component = c
                break
        else:
            try:
                component = find_phrase(['component:','component to'],
                                        valid=TicketConstants['component'])
            except Exception:
                pass
    
    if not owner:
        try:
            owner = find_phrase(['owner:','owner to'])
        except Exception:
            pass
    if owner in users:
        owner = users[owner]

    cc = ','.join(users[c] if c in users else c for c in cc.split(',') if c)
 
    with start_session(base_url+'login') as s:
        # get form token
        r = get(base_url+'newticket', session=s)
        text = r.text
        pos = text.index('form_token=')+12
        pos2 = text.index('";',pos)
        token = text[pos:pos2]

        data = {
            '__FORM_TOKEN': token,
            'field_summary': summary,
            'field_reporter': reporter,
            'field_description': description,
            'field_type': type,
            'field_priority': priority,
            'field_milestone': milestone,
            'field_component': component,
            'field_keywords': keywords,
            'field_owner': owner,
        }
        pprint(data)
        
        if not dry_run:
            r = post(base_url+'newticket', session=s, **data)
            return r.url

