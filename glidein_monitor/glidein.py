import logging
import time
from datetime import datetime, timedelta
import json

from lxml import html, objectify
import requests

from json_store import load, store

logger = logging.getLogger('glidein')

def monitor(server, send=lambda a:None, delay=60*5, failure_thresh=5):
    """
    Monitor a pyglidein server.
    
    Args:
        server (str): address of pyglidein server
        send (func): function to send a message to
        delay (int): sleep delay between checks
        failure_thresh (int): number of page failures before error
    """
    main_failures = 0
    sites = load('.sites')
    while True:
        final_cutoff = datetime.utcnow()-timedelta(days=30)
        cutoff = datetime.utcnow()-timedelta(hours=4)
        try:
            r = requests.get(server, timeout=10)
            r.raise_for_status()
        except:
            logger.warn('error getting server page', exc_info=True)
            main_failures += 1
            if main_failures > failure_thresh:
                send('pyglidein server is down')
        else:
            try:
                root = objectify.fromstring(r.content, parser=html.HTMLParser())
                for e in root.body.cssselect('div.clients div'):
                    if not e.cssselect('span.uuid'):
                        continue
                    uuid = e.cssselect('span.uuid')[0].text
                    date_raw = e.cssselect('span.date')[0].text
                    date = datetime.strptime(date_raw, '%Y-%m-%d %H:%M:%S')
                    if date < final_cutoff:
                        continue
                    if uuid not in sites:
                        sites[uuid] = {'date':date,'status':'OK'}
                    elif sites[uuid]['status'] == 'OK' and date < cutoff:
                        send('site *%s* is down. last heard from at %s'%(uuid,date_raw))
                        sites[uuid] = {'date':date,'status':'FAILED'}
                    elif sites[uuid]['status'] != 'OK' and date > cutoff:
                        sites[uuid] = {'date':date,'status':'OK'}
                store(sites, '.sites')
            except:
                logger.warn('parsing error', exc_info=True)

        time.sleep(delay)
