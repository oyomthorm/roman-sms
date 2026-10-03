"""
Manual test of the EgoSMS client.

Sends one real message to the number you provide and prints the full
response, including cost and follow-up code.

    python scripts/test_egosms.py 256700123456
    python scripts/test_egosms.py 256700123456 --sandbox

The --sandbox flag temporarily overrides config, so you can validate
without spending credits. Run without it once you are ready for a live
send.
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.abspath(
    os.path.join(os.path.dirname(__file__), '..')))

from app import create_app
from app.services.egosms_client import EgoSMSClient


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('number', help='Phone number, e.g. 256700123456')
    parser.add_argument('--sandbox', action='store_true',
                        help='Hit sandbox endpoint instead of live')
    parser.add_argument('--message', default='Roman SMS connectivity test.',
                        help='Message body')
    args = parser.parse_args()

    app = create_app()
    if args.sandbox:
        app.config['EGOSMS_SANDBOX'] = True

    with app.app_context():
        client = EgoSMSClient()
        print(f'Endpoint: {client.endpoint}')
        print(f'Username: {client.username}')
        print(f'Sender:   {client.sender}')
        print(f'To:       {args.number}')
        print('-' * 50)

        resp = client.send_batch([{
            'number': args.number,
            'message': args.message,
        }])

        print(f'ok:              {resp.ok}')
        print(f'status:          {resp.status}')
        print(f'message:         {resp.message}')
        print(f'cost:            {resp.cost}')
        print(f'follow_up_code:  {resp.follow_up_code}')
        print('-' * 50)
        print('Raw response:')
        print(resp.raw)


if __name__ == '__main__':
    main()