import json
import logging
import pytest

from pytest_flask.plugin import client
from fixtures import get_auth_header

# The documentation for client is at http://werkzeug.pocoo.org/docs/0.9/test/

def test_fsearch_api(client):
    res = client.get('/fsearch?last_name=Cohen')
    assert 'items' in res.json
    assert int(res.json['total']) > 10000

