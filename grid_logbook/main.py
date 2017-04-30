#!/usr/bin/env python3
import os
import logging
from functools import partial
from argparse import ArgumentParser

from setproctitle import setproctitle

def main(testing=False):
    from slack import SlackMessage
    from mailinglist import monitor
    
    setproctitle('grid-logbook')

    logging.basicConfig(level='DEBUG' if testing else 'INFO',
                        format='%(asctime)s %(message)s')
    
    with open('.slack_token') as f:
        token = f.read().strip()
    slack = SlackMessage(token, testing=testing)
    #slack.run()
    if testing:
        def send_message(msg):
            pass
    else:
        def send_message(msg):
            slack.send_message('pyglidein-sites', 'grid-logbook: '+msg)
    kwargs = {}
    if os.path.exists('.http_auth'):
        for line in open('.http_auth').readlines():
            if '=' in line:
                key,value = [x.strip() for x in line.split('=',1)]
                kwargs[key] = value
    monitor(archives='http://lists.icecube.wisc.edu/pipermail/grid-logbook/',
            send=send_message, **kwargs)
    logging.error('grid-logbook monitor has stopped')

if __name__ == '__main__':
    parser = ArgumentParser()
    parser.add_argument('--testing', action='store_true',
                        help='testing mode')

    args = parser.parse_args()
    main(testing=args.testing)
