"""
Communicate with slack as an RTM bot
"""

import os
import time
import logging
import random
import re
from datetime import datetime, timedelta
from contextlib import contextmanager
from pprint import pprint

import requests
from slackclient import SlackClient


def parse_slack_message(txt):
    """Remove added bits from slack message text, like url links"""
    return ''.join(p if i%2==0 else p.split('|',1)[-1] for i,p in enumerate(re.split('<(.*)>',txt)))

class SlackMessage:
    def __init__(self, token, handler=None, filter_me=True, delay=1.0,
                 pingtime=10.0, testing=False):
        self.client = SlackClient(token)
        self.handler = None
        self.filter_me = filter_me
        self.delay = delay
        self.pingtime = 10.0
        self.lastping = time.time()
        self.testing = testing

        if not self.client.rtm_connect():
            raise Exception('could not connect to slack rtm')
        self.name = self.client.server.username
        self.id = self.client.server.login_data['self']['id']
        self.usercache = {u.id:(u.real_name if u.real_name else u.name)
                          for u in self.client.server.users}

    def _client_read(self):
        backoff = 1
        for _ in range(100):
            try:
                ret = self.client.rtm_read()
            except Exception:
                logging.warn('client error - attempting to reconnect')
                backoff = random.randint(backoff,backoff*2)
                time.sleep(backoff)
                try:
                    self.client.server.rtm_connect(reconnect=True)
                except:
                    logging.warn('failed to reconnect')
            else:
                ret.reverse()
                return ret
        raise Exception('cannot connect to slack')

    def _client_write(self, channel, msg):
        backoff = 1
        for _ in range(100):
            try:
                return self.client.rtm_send_message(channel, msg)
            except Exception:
                logging.warn('client error - attempting to reconnect', exc_info=True)
                backoff = random.randint(backoff,backoff*2)
                time.sleep(backoff)
                try:
                    self.client.server.rtm_connect(reconnect=True)
                except:
                    logging.warn('failed to reconnect')
        raise Exception('cannot connect to slack')

    def stop(self):
        self.keep_running = False

    def run(self):
        if (not self.handler) or not callable(self.handler):
            raise Exception('need a handler defined')
        self.keep_running = True
        while self.keep_running:
            last_read = self._client_read()
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

    def send_message(self, channel, msg):
        logging.info('sending message to %s: %s', channel, msg)
        # do a read first, to prime the connection
        last_read = self._client_read()
        backoff = 10
        for _ in range(10):
            self._client_write(channel, msg)
            time.sleep(10)
            received = False
            while not received:
                last_read = self._client_read()
                if not last_read:
                    break
                for m in last_read:
                    logging.warn('%r',m)
                    try: # check that we actually sent it
                        if parse_slack_message(m['text']) == msg:
                            received = True
                            break
                    except:
                        pass
            if not received:
                logging.warn('client error - failed to send')
                backoff = random.randint(backoff,backoff*2)
                time.sleep(backoff)
                continue
            break

    def handle_message(self, msg):
        reply = None

        if 'subtype' in msg or 'edited' in msg:
            return
        if 'user' in msg:
            if msg['user'] == self.id:
                return
            
            parts = msg['text'].split(':',1)
            if len(parts) > 2 and (self.name in parts[0] or '<@'+self.id+'>' in parts[0]):
                msg['text'] = parts[1]
            elif self.filter_me:
                logging.info('filter a message that is not for me')
                return

            pprint(msg)
            name = self.get_username(msg['user'])
            
            try:
                reply = self.handler(msg['text'], user=name,
                                     channel=msg['channel'][0])
            except Exception:
                logging.warn('error handling message', exc_info=True)

        if reply:
            self._client_write(msg['channel'], reply)

    def get_username(self, user_id):
        if user_id not in self.usercache:
            ret = self.client.api_call('users.info', user=user_id)
            if ret['user']['real_name']:
                self.usercache[user_id] = ret['user']['real_name']
            else:
                self.usercache[user_id] = ret['user']['name']
        return self.usercache[user_id]
