"""
testing config.
"""

import os


# default config for backing services
# NOTE: defaults may be duplicated in the .env file; update both or
# simply write down a function that parses the .env file

ELASTICSEARCH_CONFIG = {
    'port': int(os.getenv("TEST_ELASTICSEARCH_PORT", 9200)),
}

CASSANDRA_CONFIG = {
    'port': int(os.getenv("TEST_CASSANDRA_PORT", 9042)),
}

POSTGRES_CONFIG = {
    'host' : 'localhost',
    'port': int(os.getenv("TEST_POSTGRES_PORT", 5432)),
    'user' : os.getenv("TEST_POSTGRES_USER", "postgres"),
    'password' : os.getenv("TEST_POSTGRES_PASSWORD", "postgres"),
    'dbname' : os.getenv("TEST_POSTGRES_DB", "postgres"),
}

MYSQL_CONFIG = {
    'host' : '127.0.0.1',
    'port' : int(os.getenv("TEST_MYSQL_PORT", 3306)),
    'user' : os.getenv("TEST_MYSQL_USER", 'test'),
    'password' : os.getenv("TEST_MYSQL_PASSWORD", 'test'),
    'database' : os.getenv("TEST_MYSQL_DATABASE", 'test'),
}

REDIS_CONFIG = {
    'port': int(os.getenv("TEST_REDIS_PORT", 6379)),
}

REDISCLUSTER_CONFIG = {
    'host': '127.0.0.1',
    'ports': os.getenv('TEST_REDISCLUSTER_PORTS', '7000,7001,7002,7003,7004,7005'),
}

MONGO_CONFIG = {
    'port': int(os.getenv("TEST_MONGO_PORT", 27017)),
}

MEMCACHED_CONFIG = {
    'host' : os.getenv('TEST_MEMCACHED_HOST', '127.0.0.1'),
    'port': int(os.getenv("TEST_MEMCACHED_PORT", 11211)),
}
