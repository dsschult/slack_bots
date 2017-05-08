import os
import logging
import time
from datetime import datetime, timedelta
import json
import re
import gzip
import tempfile

from lxml import html, objectify
import requests
from hashlib import sha512

from json_store import load, store

logger = logging.getLogger('glidein')

def hash(text):
    """Hash some text"""
    m = sha512()
    m.update(text.encode('utf-8'))
    return m.hexdigest()

def decompress(in_data):
    """Decompress the gzip txt file"""
    with tempfile.TemporaryFile() as f:
        f.write(in_data)
        f.flush()
        f.seek(0)
        return gzip.open(f).read().decode('utf-8')

def parse_msg(text):
    """Parse an email message into summary text"""
    logger.debug('parse_msg: %r',text)
    process_header = True
    sender = None
    date = None
    subject = None
    body = ''
    for line in text.split('\n'):
        line = line.strip()
        if process_header:
            if not line:
                process_header = False
            elif line.startswith('From:'):
                val = line.split(':',1)[1].strip().replace(' at ','@')
                if '(' in val and ')' in val:
                    val = val.split('(',1)[1].rsplit(')',1)[0].strip()
                sender = val
            elif line.startswith('Date:'):
                val = line.split(':',1)[1].strip()
                d = datetime.strptime(val, '%a, %d %b %Y %H:%M:%S %z')
                val = (d - d.utcoffset()).replace(tzinfo=None).isoformat()
                date = val+' UTC'
            elif line.startswith('Subject:'):
                val = line.split(':',1)[1].replace('[grid-logbook]','').strip()
                subject = val
        elif line.startswith('-------------- next part --------------'):
            break # done processing
        else:
            body += line+'\n'
    ret = ''
    if sender:
        ret += 'From: '+sender+'\n'
    if date:
        ret += 'Date: '+date+'\n'
    if subject:
        ret += 'Subject: '+subject+'\n'
    if body:
        ret += '\n'+body.strip()
    return ret

def parse_month(text):
    buffer = ''
    ret = []
    for line in text.split('\n'):
        if re.match(r'From \w*.\w* at \w*.\w*.\w* *\w*',line) and buffer:
            msg = parse_msg(buffer)
            ret.append({'hash':hash(msg), 'text':msg})
            buffer = ''
        else:
            buffer += line+'\n'
    if buffer:
        msg = parse_msg(buffer)
        ret.append({'hash':hash(msg), 'text':msg})
    logger.debug('month: %r',ret)
    return ret

def monitor(archives, send=lambda a:None, delay=60*5, failure_thresh=5,
            user=None, password=None):
    """
    Monitor a mailinglist archive.
    
    Args:
        archives (str): url of mailinglist archive
        send (func): function to send a message to
        delay (int): sleep delay between checks
        failure_thresh (int): number of failures before error
        user (str): username for http basic auth
        password (str): password for http basic auth
    """
    main_failures = 0
    last_message = load('.last_message')
    if not last_message:
        last_message = {'hash':None, 'link':None}
    request_args = {}
    if user and password:
        request_args['auth'] = (user,password)
    while True:
        try:
            r = requests.get(archives, timeout=10, **request_args)
            r.raise_for_status()
        except Exception:
            logger.warn('error getting main page', exc_info=True)
            main_failures += 1
            if main_failures > failure_thresh:
                send('mailinglist server is down')
        else:
            month_links = []
            try:
                root = objectify.fromstring(r.content, parser=html.HTMLParser())
                for e in root.body.cssselect('table td a'):
                    link = e.get('href')
                    if link.endswith('.txt'):
                        month_links.append(link)
                        if link == last_message['link']:
                            break # stop once we've reached the recorded month

                # sort by recorded month first
                month_links.reverse()
                for link in month_links:
                    logger.info('anaylzing %s',link)
                    try:
                        r = requests.get(os.path.join(archives, link), timeout=10,
                                         **request_args)
                        r.raise_for_status()
                    except Exception:
                        logger.warn('error getting month page')
                        raise
                    else:
                        if link.endswith('.gz'):
                            data = decompress(r.content)
                        else:
                            data = r.text
                        out_buffer = []
                        last_hash = None
                        # filter the messages to remove previously sent ones
                        for msg in parse_month(data):
                            if msg['hash'] == last_message['hash']:
                                out_buffer = []
                                continue
                            out_buffer.append(msg)
                        # send the messages
                        if not out_buffer:
                            logger.info('no new messages')
                            continue
                        for msg in out_buffer:
                            logger.info('sending new message:\n%r',msg['text'])
                            send('```'+msg['text']+'```')
                            last_message = {'hash':msg['hash'],'link':link}
                            store(last_message, '.last_message')
            except Exception:
                logger.warn('parsing error', exc_info=True)
                continue

        time.sleep(delay)
