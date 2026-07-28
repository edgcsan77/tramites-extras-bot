from redis import Redis
from rq import Queue
from app.config import settings

redis_conn = Redis.from_url(settings.REDIS_URL, decode_responses=True, socket_connect_timeout=5, socket_timeout=10)
cfe_queue = Queue('extras_cfe', connection=redis_conn, default_timeout=300)
renapo_queue = Queue('extras_renapo', connection=redis_conn, default_timeout=300)
