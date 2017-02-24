#!/usr/bin/env python3
import os
import logging
from functools import partial
from argparse import ArgumentParser

from setproctitle import setproctitle

def main(testing=False):
    from slack import SlackMessage
    from updown import monitor
    
    setproctitle('updown_monitor')

    logging.basicConfig(level='DEBUG' if testing else 'INFO')
    
    with open('.slack_token') as f:
        token = f.read().strip()
    slack = SlackMessage(token, testing=testing)
    #slack.run()
    monitor([
        {'server':'https://iceprod2.icecube.wisc.edu',
         'send':partial(slack.send_message,'iceprod2')},
        {'server':'https://sub-simprod-2.icecube.wisc.edu:9080',
         'send':partial(slack.send_message,'iceprod2')},
    ])
    logging.error('updown monitor has stopped')

if __name__ == '__main__':
    parser = ArgumentParser()
    parser.add_argument('--testing', action='store_true',
                        help='testing mode')

    args = parser.parse_args()
    main(testing=args.testing)
