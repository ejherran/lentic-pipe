from taskiq_redis import ListQueueBroker, RedisAsyncResultBackend

from src.api.config import settings

result_backend = RedisAsyncResultBackend(settings.REDIS_URL)

broker = ListQueueBroker(settings.REDIS_URL).with_result_backend(result_backend)
