"""Local end-to-end test for GET /api/v1/dashboard.

Runs against the local DB via Flask's test client. Does not touch production.
Asserts shape, not specific values (depends on local seed state).
"""
from app import create_app


def main():
    app = create_app()
    with app.test_client() as c:
        # 1. Login as admin
        r = c.post('/api/v1/auth/login',
                   json={'email': 'admin@romansms.local',
                         'password': 'ChangeMe123!'})
        print('login:', r.status_code)
        assert r.status_code == 200, 'login failed'
        token = r.get_json()['token']
        H = {'Authorization': f'Bearer {token}'}

        # 2. Fetch dashboard
        r = c.get('/api/v1/dashboard', headers=H)
        body = r.get_json()
        print('dashboard status:', r.status_code)
        print('dashboard keys:', sorted(body.keys()))
        assert r.status_code == 200, 'dashboard returned non-200'

        # 3. Shape assertions — every key the Flutter screen expects
        expected_keys = {
            'contacts', 'groups', 'campaigns',
            'sent_30d', 'delivered_30d', 'delivery_failed_30d',
            'failed_30d', 'pending_30d',
            'delivery_rate',
            'credits_spent_30d', 'avg_daily_spend', 'days_remaining',
            'balance', 'recent_activity',
        }
        missing = expected_keys - set(body.keys())
        assert not missing, f'missing keys: {missing}'

        # 4. Type checks
        assert isinstance(body['sent_30d'], int), 'sent_30d not int'
        assert isinstance(body['delivered_30d'], int)
        assert isinstance(body['failed_30d'], int)
        assert isinstance(body['pending_30d'], int)
        assert isinstance(body['contacts'], int)
        assert isinstance(body['groups'], int)
        assert isinstance(body['campaigns'], int)
        assert isinstance(body['balance'], int)
        assert isinstance(body['credits_spent_30d'], int)
        assert isinstance(body['avg_daily_spend'], (int, float))
        assert body['days_remaining'] is None or isinstance(body['days_remaining'], int)

        # delivery_rate: string ending in % or em-dash
        assert isinstance(body['delivery_rate'], str), 'delivery_rate not str'
        assert body['delivery_rate'] == '—' or body['delivery_rate'].endswith('%'), \
            f'delivery_rate malformed: {body["delivery_rate"]!r}'

        # recent_activity: list, possibly empty
        assert isinstance(body['recent_activity'], list), 'recent_activity not list'
        for item in body['recent_activity']:
            assert set(item.keys()) == {'type', 'title', 'date', 'amount'}, \
                f'activity item shape wrong: {item.keys()}'
            assert item['type'] in ('credit', 'debit'), f'bad type: {item["type"]}'
            assert isinstance(item['title'], str) and item['title'], 'empty title'
            assert isinstance(item['date'], str), 'date not str'
            assert isinstance(item['amount'], str), 'amount not str'
            assert item['amount'][0] in ('+', '-'), f'amount missing sign: {item["amount"]!r}'

        print('recent_activity count:', len(body['recent_activity']))
        if body['recent_activity']:
            print('first activity:', body['recent_activity'][0])

    print('\nALL ASSERTIONS PASSED')


if __name__ == '__main__':
    main()