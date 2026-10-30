"""Local end-to-end test for PUT /auth/profile and POST /auth/change-password."""
from app import create_app


def main():
    app = create_app()
    with app.test_client() as c:
        # 1. Login
        r = c.post('/api/v1/auth/login',
                   json={'email': 'admin@romansms.local',
                         'password': 'ChangeMe123!'})
        print('login:', r.status_code)
        assert r.status_code == 200
        token = r.get_json()['token']
        H = {'Authorization': f'Bearer {token}'}

        # 2. Get current user state
        r = c.get('/api/v1/auth/me', headers=H)
        print('me:', r.status_code, r.get_json()['user'])
        assert r.status_code == 200
        original_name = r.get_json()['user'].get('full_name') or r.get_json()['user'].get('name')

        # 3. Update full_name
        r = c.put('/api/v1/auth/profile',
                  headers=H, json={'full_name': 'Test Admin Renamed'})
        print('put profile:', r.status_code, r.get_json())
        assert r.status_code == 200

        # 4. Verify it stuck
        r = c.get('/api/v1/auth/me', headers=H)
        body = r.get_json()['user']
        print('me after update:', body)
        assert body.get('full_name') == 'Test Admin Renamed' or body.get('name') == 'Test Admin Renamed'

        # 5. Restore original name
        r = c.put('/api/v1/auth/profile',
                  headers=H, json={'full_name': original_name})
        assert r.status_code == 200

        # 6. Empty body → 422
        r = c.put('/api/v1/auth/profile', headers=H, json={})
        print('put empty:', r.status_code, r.get_json())
        assert r.status_code == 422

        # 7. Change password with wrong current → 422
        r = c.post('/api/v1/auth/change-password', headers=H, json={
            'current_password': 'wrong-password-xyz',
            'new_password': 'NewPass123!',
        })
        print('change-password wrong current:', r.status_code, r.get_json())
        assert r.status_code == 422

        # 8. Change password to something, then back
        NEW_PW = 'Round4Test2026!'
        r = c.post('/api/v1/auth/change-password', headers=H, json={
            'current_password': 'ChangeMe123!',
            'new_password': NEW_PW,
        })
        print('change-password ok:', r.status_code)
        assert r.status_code == 200

        # 9. Login with new password
        r = c.post('/api/v1/auth/login',
                   json={'email': 'admin@romansms.local', 'password': NEW_PW})
        print('relogin new pw:', r.status_code)
        assert r.status_code == 200

        # 10. Change back
        H2 = {'Authorization': f'Bearer {r.get_json()["token"]}'}
        r = c.post('/api/v1/auth/change-password', headers=H2, json={
            'current_password': NEW_PW,
            'new_password': 'ChangeMe123!',
        })
        print('change-password back:', r.status_code)
        assert r.status_code == 200

    print('\nALL ASSERTIONS PASSED')


if __name__ == '__main__':
    main()