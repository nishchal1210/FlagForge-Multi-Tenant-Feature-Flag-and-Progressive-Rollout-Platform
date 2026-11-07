import time

from flagforge_sdk import FlagForgeClient


client = FlagForgeClient(
    sdk_key="ff_env_6ab9644448504efab026281c845e631d_rr8PMWWBADNJSL8QIG8TxI0DRN41i72DExM9Ee0Z9Vk",
    base_url="http://127.0.0.1:8000",
    cache_path="./cache/flagforge-production.json",
)

try:
    client.initialize()
    client.start_realtime()

    while True:
        details = client.boolean_value_details(
            flag_key="reliability_test",
            user={
                "key": "user-123",
                "country": "IN",
            },
            default=False,
        )

        print(details)
        time.sleep(2)

except KeyboardInterrupt:
    pass

finally:
    client.close()
