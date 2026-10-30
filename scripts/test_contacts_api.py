"""Local end-to-end test for the new /api/v1/contacts routes.

Runs against the local DB via Flask's test client. Does not touch production.
"""
from app import create_app
from app.extensions import db


def main():
    app = create_app()
    with app.test_client() as c:
        # 1. Login as the seeded admin
        r = c.post('/api/v1/auth/login',
                   json={'email': 'admin@romansms.local',
                         'password': 'ChangeMe123!'})
        print('login:', r.status_code, r.get_json())
        assert r.status_code == 200, 'login failed'
        token = r.get_json()['token']

        # Every subsequent request needs the bearer token.
        H = {'Authorization': f'Bearer {token}'}

        # 2. Create a throwaway contact
        r = c.post('/api/v1/contacts', headers=H, json={
            'phone': '+256700000001',
            'name': 'Round1 Throwaway',
        })
        print('create:', r.status_code, r.get_json())
        assert r.status_code in (200, 201), 'create failed'
        contact_id = r.get_json()['id']

        # 3. PATCH name
        r = c.patch(f'/api/v1/contacts/{contact_id}',
                    headers=H, json={'name': 'Round1 Renamed'})
        body = r.get_json()
        print('patch name:', r.status_code, body)
        assert r.status_code == 200 and body['name'] == 'Round1 Renamed'

        # 4. PATCH group_id=null
        r = c.patch(f'/api/v1/contacts/{contact_id}',
                    headers=H, json={'group_id': None})
        body = r.get_json()
        print('patch clear_group:', r.status_code, body)
        assert r.status_code == 200 and body['group_id'] is None

        # 5. PATCH district_id=null
        r = c.patch(f'/api/v1/contacts/{contact_id}',
                    headers=H, json={'district_id': None})
        body = r.get_json()
        print('patch clear_district:', r.status_code, body)
        assert r.status_code == 200 and body['district_id'] is None

        # 6. PATCH empty body — should be a 200 no-op
        r = c.patch(f'/api/v1/contacts/{contact_id}', headers=H, json={})
        print('patch empty:', r.status_code)
        assert r.status_code == 200

        # 7. optout (first time)
        r = c.post(f'/api/v1/contacts/{contact_id}/optout', headers=H)
        body = r.get_json()
        print('optout first:', r.status_code, body)
        assert r.status_code == 200 and body['opted_out'] is True

        # 8. optout again — idempotent 200
        r = c.post(f'/api/v1/contacts/{contact_id}/optout', headers=H)
        body = r.get_json()
        print('optout second:', r.status_code, body)
        assert r.status_code == 200 and body['opted_out'] is True

        # 9. DELETE
        r = c.delete(f'/api/v1/contacts/{contact_id}', headers=H)
        print('delete:', r.status_code)
        assert r.status_code == 204

        # 10. DELETE again — 404
        r = c.delete(f'/api/v1/contacts/{contact_id}', headers=H)
        print('delete again:', r.status_code)
        assert r.status_code == 404

        # 11. PATCH missing — 404
        r = c.patch(f'/api/v1/contacts/{contact_id}',
                    headers=H, json={'name': 'ghost'})
        print('patch missing:', r.status_code)
        assert r.status_code == 404

        # 12. optout missing — 404
        r = c.post(f'/api/v1/contacts/{contact_id}/optout', headers=H)
        print('optout missing:', r.status_code)
        assert r.status_code == 404

    print('\nALL ASSERTIONS PASSED')


if __name__ == '__main__':
    main()