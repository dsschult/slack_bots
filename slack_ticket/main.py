#!/usr/bin/env python3
import os
import logging
from argparse import ArgumentParser

def main(testing=False):
    from slack import SlackMessage

    logging.basicConfig(level='DEBUG' if testing else 'INFO')
    
    with open('.slack_token') as f:
        token = f.read().strip()
    slack = SlackMessage(token, testing=testing)
    slack.run()

if __name__ == '__main__':
    parser = ArgumentParser()
    parser.add_argument('--testing', action='store_true',
                        help='testing - do not submit an actual ticket')

    args = parser.parse_args()
    main(testing=args.testing)
