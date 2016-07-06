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
from slackclient import SlackClient


def get(url, username=None, password=None, session=None, **params):
    if session:
        requests = session
    kwargs = {'timeout': 10}
    if username and password:
        kwargs['auth'] = (username, password)
    if params:
        kwargs['params'] = params
    logging.info('GET for %s, args: %r',url,kwargs)
    r = requests.get(url, **kwargs)
    r.raise_for_status()
    return r

def post(url, username=None, password=None, session=None, **params):
    if session:
        requests = session
    kwargs = {'timeout': 10}
    if username and password:
        kwargs['auth'] = (username, password)
    if params:
        kwargs['data'] = params
    logging.info('POST for %s, args: %r',url,kwargs)
    r = requests.post(url, **kwargs)
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

def new_ticket(summary=None, reporter='icecube', description=None,
               type=None, priority=None, milestone=None,
               component=None, keywords='', cc='',
               owner=''):

    if not summary and not description:
        raise Exception('need summary or description')
    if not summary:
        summary = description.split('. ',1)[0]
    if not description:
        description = summary

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
        print(data)
        r = post(base_url+'newticket', session=s, **data)
        return r.url


class SlackMessage:
    def __init__(self, token, delay=1.0, pingtime=10.0):
        self.client = SlackClient(token)
        self.delay = delay
        self.pingtime = 10.0
        self.lastping = time.time()
        if not self.client.rtm_connect():
            raise Exception('could not connect to slack rtm')
        self.name = self.client.server.username
        self.id = self.client.server.login_data['self']['id']
        self.usercache = {u.id:(u.real_name if u.real_name else u.name)
                          for u in self.client.server.users}

    def stop(self):
        self.keep_running = False

    def run(self):
        self.keep_running = True
        while self.keep_running:
            last_read = self.client.rtm_read()
            last_read.reverse()
            while last_read:
                try:
                    self.dispatch(last_read.pop())
                except Exception:
                    logging.info('error handling event', exc_info=True)
            self.ping()
            time.sleep(self.delay)
    
    def ping(self):
        now = time.time()
        if now >= self.lastping + self.pingtime:
            self.client.server.ping()
            self.lastping = now

    def dispatch(self, event):
        if 'type' in event and event['type'] == 'message':
            self.handle_message(event)

    def handle_message(self, msg):
        reply = None

        if 'subtype' in msg or 'edited' in msg:
            return
        if 'user' in msg:
            if msg['user'] == self.id:
                return
            
            parts = msg['text'].split(':',1)
            if len(parts) < 2:
                return
            if not (self.name in parts[0] or
                    '<@'+self.id+'>' in parts[0]):
                return

            pprint(msg)
            name = self.get_username(msg['user'])
            
            # make trac ticket
            ticket_url = new_ticket(reporter=name, description=parts[1].strip())
            
            if msg['channel'][0] == 'D':
                reply = 'new ticket: '+ticket_url

        if reply:
            self.client.rtm_send_message(msg['channel'], reply)

    def get_username(self, user_id):
        if user_id not in self.usercache:
            ret = self.client.api_call('users.info', user=user_id)
            if ret['user']['real_name']:
                self.usercache[user_id] = ret['user']['real_name']
            else:
                self.usercache[user_id] = ret['user']['name']
        return self.usercache[user_id]

def main():
    with open('.slack_token') as f:
        token = f.read().strip()
    slack = SlackMessage(token)
    slack.run()

if __name__ == '__main__':
    logging.basicConfig(level='DEBUG')
    main()
