#!/usr/bin/env python3
import os
import logging

def main(testing=False):
    from slack import SlackMessage
    with open('.slack_token') as f:
        token = f.read().strip()
    slack = SlackMessage(token, testing=testing)
    slack.run()

if __name__ == '__main__':
    logging.basicConfig(level='DEBUG')
    main(testing=True)
