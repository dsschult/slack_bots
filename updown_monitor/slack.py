"""
Communicate with slack as an RTM bot
"""

import os
import time
import logging
import random
from datetime import datetime, timedelta
from contextlib import contextmanager
from pprint import pprint

import requests
from slackclient import SlackClient

class SlackMessage:
    def __init__(self, token, delay=1.0, pingtime=10.0, testing=False):
        self.client = SlackClient(token)
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

    def stop(self):
        self.keep_running = False

    def run(self):
        self.keep_running = True
        while self.keep_running:
            try:
                last_read = self.client.rtm_read()
                self.backoff = 1
            except Exception:
                logging.warn('client error - attempting to reconnect')
                self.backoff = random.getint(self.backoff,self.backoff*2)
                time.sleep(self.backoff)
                self.client.server.rtm_connect(reconnect=True)
                continue
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

    def send_message(self, channel, msg):
        logging.info('sending message to %s: %s', channel, msg)
        backoff = 1
        for _ in range(10):
            try:
                last_read = self.client.rtm_send_message(channel, msg)
                backoff = 1
            except Exception:
                logging.warn('client error - attempting to reconnect', exc_info=True)
                backoff = random.randint(backoff,backoff*2)
                time.sleep(backoff)
                self.client.server.rtm_connect(reconnect=True)
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
            if len(parts) < 2:
                return
            if not (self.name in parts[0] or
                    '<@'+self.id+'>' in parts[0]):
                return

            pprint(msg)
            name = self.get_username(msg['user'])
            
            # process status request
            return
            #try:
            #    ticket_url = new_ticket(reporter=name, description=parts[1].strip(),
            #                            dry_run=self.testing)
            #except Exception:
            #    logging.warn('error making ticket', exc_info=True)
            #    reply = 'error occurred'
            #else:
            #    if msg['channel'][0] == 'D' and ticket_url:
            #        reply = 'new ticket: '+ticket_url

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
