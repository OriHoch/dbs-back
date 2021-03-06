from elasticsearch import Elasticsearch
from scripts.elasticsearch_create_index import ElasticsearchCreateIndexCommand
from copy import deepcopy
import os
from bhs_api.item import get_doc_id
from mocks import *
from bhs_api.constants import PIPELINES_ES_DOC_TYPE


def given_invalid_elasticsearch_client(app):
    app.es = Elasticsearch("192.0.2.0", timeout=0.000000001)

def index_doc(app, collection, doc):
    doc = deepcopy(doc)
    # sync pipelines adds this attribute, but for simplicity we don't include it in the mocks and just add it here
    doc.setdefault("title_he_lc", doc.get("title_he", "").lower())
    doc.setdefault("title_en_lc", doc.get("title_en", "").lower())
    # TODO: remove this code, doc_id for the new docs is much simpler
    # something like this: "{}_{}".format(doc["source"], doc["source_id"])
    if collection == "persons":
        # persons data is still not available in new schema
        doc_id = "{}_{}_{}".format(doc["tree_num"], doc["tree_version"], doc["person_id"])
    else:
        # get_doc_id detects new schema docs and sets correct doc_id
        doc_id = get_doc_id(collection, doc)
    app.es.index(index=app.es_data_db_index_name, doc_type=PIPELINES_ES_DOC_TYPE, body=doc, id=doc_id)

def index_docs(app, collections, reuse_db=False):
    if not reuse_db or not app.es.indices.exists(app.es_data_db_index_name):
        ElasticsearchCreateIndexCommand().create_es_index(es=app.es, es_index_name=app.es_data_db_index_name, delete_existing=True)
        for collection, docs in collections.items():
            for doc in docs:
                index_doc(app, collection, doc)
        app.es.indices.refresh(app.es_data_db_index_name)

def given_local_elasticsearch_client_with_test_data(app, session_id=None, additional_index_docs=None):
    """
    setup elasticsearch on localhost:9200 for testing on a testing index
    if given session_id param and it is the same as previous session_id param - will not reindex the docs
    """
    app.es = Elasticsearch("localhost")
    app.es_data_db_index_name = "bh_dbs_back_pytest"
    if not session_id or session_id != getattr(given_local_elasticsearch_client_with_test_data, "_session_id", None):
        given_local_elasticsearch_client_with_test_data._session_id = session_id
        reuse_db = os.environ.get("REUSE_DB", "") == "1"
        docs_to_index = {
            "places": [PLACES_BOURGES, PLACES_BOZZOLO],
            "photoUnits": [PHOTO_BRICKS, PHOTOS_BOYS_PRAYING],
            "familyNames": [FAMILY_NAMES_DERI, FAMILY_NAMES_EDREHY],
            "personalities": [PERSONALITIES_FERDINAND, PERSONALITIES_DAVIDOV],
            "movies": [MOVIES_MIDAGES, MOVIES_SPAIN],
            "persons": [PERSON_EINSTEIN, PERSON_LIVING, PERSON_MOSHE_A, PERSON_MOSHE_B],
        }
        if additional_index_docs:
            if not session_id:
                raise Exception("Must set session_id when using additional_index_docs")
            for collection, additional_docs in additional_index_docs.items():
                for doc in additional_docs:
                    docs_to_index[collection].append(doc)
        index_docs(app, docs_to_index, reuse_db)


def assert_error_response(res, expected_status_code, expected_error_startswith):
    assert res.status_code == expected_status_code
    assert res.json["error"].startswith(expected_error_startswith)

def assert_client_get(client, url, expected_status_code=200):
    res = client.get(url)
    assert res.status_code == expected_status_code, get_res_dump(res)
    return res.json

def assert_common_elasticsearch_search_results(res):
    assert res.status_code == 200, "invalid status, json response: {}".format(res.json)
    hits, total = res.json["hits"], res.json["total"]
    return hits, total

def assert_no_results(res):
    hits, total = assert_common_elasticsearch_search_results(res)
    assert hits == [] and total == 0

def assert_search_results(res, num_expected):
    hits, total = assert_common_elasticsearch_search_results(res)
    assert (len(hits) == num_expected
            and total == num_expected), "unexpected number of hits: {} / {}\n{}".format(len(hits), total, [hit["source"]+"_"+hit["source_id"] for hit in hits])
    for hit in hits:
        yield hit

def assert_search_hit_ids(client, search_params, expected_ids, ignore_order=False):
    hit_ids = [hit["source"]+"_"+hit["source_id"] for hit in assert_search_results(client.get(u"/v1/search?{}".format(search_params)), len(expected_ids))]
    if not ignore_order:
        assert hit_ids == expected_ids, "hit_ids={}".format(hit_ids)
    else:
        assert {id:id for id in hit_ids} == {id:id for id in expected_ids}, "actual IDs = {}".format(hit_ids)

def assert_suggest_response(client, collection, string,
                            expected_http_status_code=200, expected_error_message=None, expected_json=None):
    res = client.get(u"/v1/suggest/{}/{}".format(collection, string))
    assert res.status_code == expected_http_status_code, "{}: {}".format(res, res.json["traceback"])
    if expected_error_message is not None:
        assert expected_error_message in res.data
    if expected_json is not None:
        print(res.json)
        assert expected_json == res.json, "expected={}, actual={}".format(expected_json, res.json)

def get_res_dump(res):
    return (res.status_code, res.data)

def dump_res(res):
    print(get_res_dump(res))
