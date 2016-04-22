# -*- coding: utf-8 -*-
"""
Oisin Mulvihill
2015-02-06

"""
import uuid
import logging

import pytest
# imported so request.getfuncargvalue will find:
from testing.aid.containers import dk_logger
from testing.aid.containers import dk_config
from testing.aid.containers import dk_influxdb
from testing.aid.containers import dk_redis
from testing.aid.containers import dk_redis_session
from testing.aid.containers import dk_rethinkdb
from testing.aid.containers import dk_rethinkdb_session
from testing.aid.containers import dk_elasticsearch


def get_log(e=None):
    return logging.getLogger("{0}.{1}".format(__name__, e) if e else __name__)


@pytest.fixture(scope='function')
def elasticsearch(request):
    """Set up a elasticsearch reset and ready to roll.
    """
    log = get_log('elasticsearch')

    edb = request.getfuncargvalue('dk_elasticsearch')

    class Conn(object):
        def __init__(self):
            """Returned so others can ask for what port, host elasticsearch
            is running on.
            """
            ports = edb.settings['export']['ports']
            port = [p['export_port'] for p in ports if p['name'] == 'db']
            port = port[0]
            self.host = edb.settings['interface']
            self.port = port
            self.base_uri = 'http://{}:{}'.format(self.host, self.port)

    from pnc.user.index import db
    from pnc.user.index import document

    es_db = Conn()
    db.init(dict(es_endpoint=es_db.base_uri))
    log.info('Configuring indices for {}'.format(es_db.base_uri))
    document.init_indices()
    log.info('database ready for testing "{}"'.format(es_db.base_uri))

    def db_teardown(x=None):
        db.conn().hard_reset()
        log.warn(
            'teardown of "{}" OK.'.format(es_db.base_uri)
        )

    request.addfinalizer(db_teardown)

    return es_db


@pytest.fixture(scope='session')
def rethink_db_name_session(request):
    """Return the a unqiue db name to use for a tests running in a session.
    """
    return "testingdb_{}".format(uuid.uuid4().hex)


def _rethinkdb_setup(request):
    log = get_log('_rethinkdb_setup')

    redb = request.getfuncargvalue('dk_rethinkdb_session')
    db_name = request.getfuncargvalue('rethink_db_name_session')

    class Conn(object):
        def __init__(self):
            """Returned so others can ask for what port, host, etc rethinkdb
            is running on.
            """
            ports = redb.settings['export']['ports']
            port = [p['export_port'] for p in ports if p['name'] == 'db']
            port = port[0]
            self.host = redb.settings['interface']
            self.port = port
            self.db_name = db_name

    rdb = Conn()
    log.info("Rethinkdb host={} port={} db={}".format(
        rdb.port, rdb.host, rdb.db_name
    ))

    return rdb


@pytest.fixture(scope='session')
def rethinkdb_persist(request):
    """Set up a rethinkdb ready to roll once per complete test run.
    """
    return _rethinkdb_setup(request)


@pytest.fixture(scope='session')
def redis_session(request):
    """Set up a redis reset and ready to roll.
    """
    log = get_log('redis_session')

    redb = request.getfuncargvalue('dk_redis_session')

    class Conn(object):
        def __init__(self):
            """Returned so others can ask for what port, host, etc redis
            is running on.
            """
            ports = redb.settings['export']['ports']
            port = [p['export_port'] for p in ports if p['name'] == 'db']
            port = port[0]
            # cache db:
            self.db = redb.settings['export'].get('db', 2)
            # RQ worker / task queue
            self.defer_db = redb.settings['export'].get('defer_db', 6)
            self.host = redb.settings['interface']
            self.port = port

        def conn(self):
            import redis
            return redis.StrictRedis(
                host=self.host, port=self.port, db=self.db
            )

    rdb = Conn()
    log.debug(
        "redis config host '{}' port '{}' db '{}'.".format(
            rdb.host, rdb.port, rdb.db
        )
    )

    def db_teardown(x=None):
        # log.warn('Dropping all from redis db: {}'.format(
        #     rdb.conn().defer_db
        # ))
        # rdb.conn().flushall()
        log.warn('teardown OK.')

    request.addfinalizer(db_teardown)

    return rdb


@pytest.fixture(scope='function')
def redis(request):
    """Uses the long running session redis and resets the db after each test.
    """
    log = get_log('redis')

    rdb = request.getfuncargvalue('redis_session')

    def db_teardown(x=None):
        log.warn('Cleaing up redis db')
        rdb.conn().flushall()
        log.warn('teardown OK.')

    request.addfinalizer(db_teardown)

    return rdb


@pytest.fixture(scope='session')
def redis_persist(request):
    """Uses the long running session redis.
    """
    log = get_log('redis')

    rdb = request.getfuncargvalue('redis_session')

    def db_teardown(x=None):
        log.warn('Cleaing up redis db')
        rdb.conn().flushall()
        log.warn('teardown OK.')

    request.addfinalizer(db_teardown)

    return rdb


@pytest.fixture(scope='function')
def influxdb(request):
    """Set up a influxdb connection reset and ready to roll.
    """
    log = get_log('influxdb')

    influxdb = request.getfuncargvalue('dk_influxdb')

    class Conn(object):
        def __init__(self):
            """Returned so others can ask for what port, host, etc influx
            is running on.
            """
            ports = influxdb.settings['export']['ports']
            port = [p['export_port'] for p in ports if p['name'] == 'db']
            port = port[0]
            self.host = influxdb.settings['interface']
            self.port = port
            self.user = influxdb.settings['auth']['user']
            self.password = influxdb.settings['auth']['password']
            self.db = "testingdb_{}".format(uuid.uuid4().hex)

    dbconn = Conn()
    from pnc.stats.backend import db
    db.DB.init(dict(
        db=dbconn.db,
        port=dbconn.port,
        host=dbconn.host,
        user=dbconn.user,
        password=dbconn.password,
    ))
    db.DB.create_database()
    log.info('database ready for testing "{}"'.format(dbconn.db))

    def db_teardown(x=None):
        log.warn('teardown database for testing "{}"'.format(dbconn.db))
        db.DB.drop_database()

    request.addfinalizer(db_teardown)

    return dbconn
