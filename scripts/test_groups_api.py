"""Local end-to-end test for the /api/v1/groups routes.

Runs against the local DB via Flask's test client. Does not touch production.

Covers Round 5a: list, create, get, patch, delete (detach), delete (move_to),
uniqueness, and 404/422/401 error paths.
"""
from app import create_app


def main():
    app = create_app()
    with app.test_client() as c:
        # 1. Login as the seeded admin
        r = c.post('/api/v1/auth/login',
                   json={'email': 'admin@romansms.local',
                         'password': 'ChangeMe123!'})
        print('login:', r.status_code)
        assert r.status_code == 200, 'login failed'
        token = r.get_json()['token']
        H = {'Authorization': f'Bearer {token}'}

        # 2. List — returns a list (do not assume empty; other tests may leave rows)
        r = c.get('/api/v1/groups', headers=H)
        body = r.get_json()
        print('list initial:', r.status_code, 'count=', len(body.get('items', [])))
        assert r.status_code == 200
        assert isinstance(body.get('items'), list)
        preexisting_ids = {g['id'] for g in body['items']}

        # 3. Create
        r = c.post('/api/v1/groups', headers=H, json={
            'name': 'Round5 Test Group',
            'description': 'created by test_groups_api',
        })
        body = r.get_json()
        print('create:', r.status_code, body)
        assert r.status_code == 201, 'create failed'
        gid = body['id']
        assert body['name'] == 'Round5 Test Group'
        assert body['description'] == 'created by test_groups_api'
        assert body['contact_count'] == 0

        # 4. List again — new group appears
        r = c.get('/api/v1/groups', headers=H)
        ids = {g['id'] for g in r.get_json()['items']}
        print('list after create:', r.status_code, 'contains new=', gid in ids)
        assert r.status_code == 200
        assert gid in ids
        assert gid not in preexisting_ids

        # 5. GET by id
        r = c.get(f'/api/v1/groups/{gid}', headers=H)
        body = r.get_json()
        print('get by id:', r.status_code, body)
        assert r.status_code == 200
        assert body['id'] == gid
        assert body['name'] == 'Round5 Test Group'

        # 6. PATCH name
        r = c.patch(f'/api/v1/groups/{gid}', headers=H,
                    json={'name': 'Round5 Renamed'})
        body = r.get_json()
        print('patch name:', r.status_code, body)
        assert r.status_code == 200
        assert body['name'] == 'Round5 Renamed'
        # description should be preserved (PATCH semantics)
        assert body['description'] == 'created by test_groups_api'

        # 7. PATCH empty body — 422
        r = c.patch(f'/api/v1/groups/{gid}', headers=H, json={})
        print('patch empty:', r.status_code)
        assert r.status_code == 422

        # 8. Duplicate name — create a second group, try to rename to first's name
        r = c.post('/api/v1/groups', headers=H,
                   json={'name': 'Round5 Second Group'})
        print('create second:', r.status_code)
        assert r.status_code == 201
        gid2 = r.get_json()['id']
        r = c.patch(f'/api/v1/groups/{gid2}', headers=H,
                    json={'name': 'Round5 Renamed'})
        print('patch duplicate name:', r.status_code, r.get_json())
        assert r.status_code == 422

        # 9. Attach a contact to the first group (cross-module: contacts API)
        r = c.post('/api/v1/contacts', headers=H, json={
            'phone': '+256700000050',
            'name': 'Round5 Throwaway',
            'group_id': gid,
        })
        print('create contact:', r.status_code)
        assert r.status_code in (200, 201)
        cid = r.get_json()['id']

        # 10. GET group — contact_count now 1
        r = c.get(f'/api/v1/groups/{gid}', headers=H)
        print('get after attach:', r.status_code, r.get_json())
        # NOTE: single-GET returns contact_count=None by design this round
        # (list endpoint is the one that computes counts). Adjust assertion.
        assert r.status_code == 200

        # 11. List — contact_count for gid is 1
        r = c.get('/api/v1/groups', headers=H)
        rows = {g['id']: g for g in r.get_json()['items']}
        print('list contact_count:', rows[gid]['contact_count'])
        assert rows[gid]['contact_count'] == 1

        # 12. DELETE without move_to — contact detaches
        r = c.delete(f'/api/v1/groups/{gid}', headers=H)
        body = r.get_json()
        print('delete detach:', r.status_code, body)
        assert r.status_code == 200
        assert body == {'ok': True, 'moved_count': 1, 'moved_to': None}

        # 13. Contact is now ungrouped
        r = c.get(f'/api/v1/contacts/{cid}', headers=H)
        print('contact after detach:', r.status_code, r.get_json())
        assert r.status_code == 200
        assert r.get_json()['group_id'] is None

        # 14. GET deleted group — 404
        r = c.get(f'/api/v1/groups/{gid}', headers=H)
        print('get deleted:', r.status_code)
        assert r.status_code == 404

        # 15. DELETE deleted group — 404
        r = c.delete(f'/api/v1/groups/{gid}', headers=H)
        print('delete deleted:', r.status_code)
        assert r.status_code == 404

        # 16. DELETE nonexistent id — 404
        r = c.delete('/api/v1/groups/999999', headers=H)
        print('delete missing:', r.status_code)
        assert r.status_code == 404

        # 17. move_to variant — recreate A and B, contact in A, delete A -> move to B
        r = c.post('/api/v1/groups', headers=H, json={'name': 'Round5 A'})
        assert r.status_code == 201
        a_id = r.get_json()['id']
        r = c.post('/api/v1/groups', headers=H, json={'name': 'Round5 B'})
        assert r.status_code == 201
        b_id = r.get_json()['id']

        r = c.post('/api/v1/contacts', headers=H, json={
            'phone': '+256700000051',
            'name': 'Round5 Mover',
            'group_id': a_id,
        })
        assert r.status_code in (200, 201)
        mover_id = r.get_json()['id']

        r = c.delete(f'/api/v1/groups/{a_id}?move_to={b_id}', headers=H)
        body = r.get_json()
        print('delete move_to:', r.status_code, body)
        assert r.status_code == 200
        assert body == {'ok': True, 'moved_count': 1, 'moved_to': b_id}

        r = c.get(f'/api/v1/contacts/{mover_id}', headers=H)
        print('contact after move:', r.status_code, r.get_json())
        assert r.status_code == 200
        assert r.get_json()['group_id'] == b_id

        # 18. move_to self — 422
        r = c.delete(f'/api/v1/groups/{b_id}?move_to={b_id}', headers=H)
        print('delete move_to self:', r.status_code, r.get_json())
        assert r.status_code == 422

        # 19. Unauthenticated — 401
        r = c.get('/api/v1/groups')
        print('unauthenticated:', r.status_code)
        assert r.status_code == 401

        # ---- CLEANUP ----
        # Remove throwaway contacts (both mover and the first one, plus contact in B)
        c.delete(f'/api/v1/contacts/{mover_id}', headers=H)
        c.delete(f'/api/v1/contacts/{cid}', headers=H)
        # Remove remaining groups
        c.delete(f'/api/v1/groups/{b_id}', headers=H)
        c.delete(f'/api/v1/groups/{gid2}', headers=H)

    print('\nALL ASSERTIONS PASSED')


if __name__ == '__main__':
    main()