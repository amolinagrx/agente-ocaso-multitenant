"""Lightweight isolation/load smoke test; marked so CI can run it separately."""

from concurrent.futures import ThreadPoolExecutor

import pytest


@pytest.mark.load
def test_parallel_tenant_requests_do_not_bleed(client):
    # Separate clients emulate isolated browser sessions while sharing one DB/app.
    app = client.application

    def request_tenant(slug, expected):
        local_client = app.test_client()
        login = local_client.post(f'/{slug}/login', data={
            'email': 'shared@example.com', 'password': 'password-123',
        })
        assert login.status_code == 302
        for _ in range(20):
            response = local_client.get(f'/{slug}/clientes/')
            assert response.status_code == 200
            assert expected.encode() in response.data
        return True

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(
            lambda item: request_tenant(*item),
            [('alpha', 'Cliente Alpha'), ('beta', 'Cliente Beta')] * 4,
        ))
    assert all(results)
