#!/usr/bin/env python3
import os
import logging
from functools import partial
from argparse import ArgumentParser

def main(testing=False):
    from slack import SlackMessage
    from glidein import monitor

    logging.basicConfig(level='DEBUG' if testing else 'INFO')
    
    with open('.slack_token') as f:
        token = f.read().strip()
    slack = SlackMessage(token, testing=testing)
    #slack.run()
    monitor(server='http://glidein-simprod.icecube.wisc.edu:11001',
            send=partial(slack.send_message,'pyglidein-sites'))
    logging.error('glidein monitor has stopped')

if __name__ == '__main__':
    parser = ArgumentParser()
    parser.add_argument('--testing', action='store_true',
                        help='testing mode')

    args = parser.parse_args()
    main(testing=args.testing)
