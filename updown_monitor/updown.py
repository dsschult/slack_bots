import logging
import time

import requests

logger = logging.getLogger('updown')

def monitor(servers, delay=60, failure_thresh=5):
    """
    Monitor a set of servers.
    
    Args:
        servers (list): list of dicts to monitor/send
        delay (int): sleep delay between checks
        failure_thresh (int): number of page failures before error
    """
    for s in servers:
        s['failures'] = 0
    while True:
        start = time.time()
        for s in servers:
            try:
                r = requests.get(s['server'], verify=False, timeout=10)
                r.raise_for_status()
            except:
                logger.warn('error getting server page', exc_info=True)
                s['failures'] += 1
                if s['failures'] == failure_thresh:
                    s['send'](s['server']+' is down')
            else:
                s['failures'] = 0

        time.sleep(delay-(time.time()-start))
