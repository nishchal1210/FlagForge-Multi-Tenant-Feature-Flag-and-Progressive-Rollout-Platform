from flagforge_sdk import FlagForgeClient


client = FlagForgeClient(
    sdk_key="PASTE_YOUR_ACTUAL_SDK_KEY_HERE",
    base_url="http://127.0.0.1:8000",
    cache_path="./cache/flagforge-production.json",
)

try:
    client.initialize()

    enabled = client.boolean_value(
        flag_key="new_checkout",
        user={
            "key": "user-123",
            "country": "IN",
        },
        default=False,
    )

    print("Flag value:", enabled)

    details = client.boolean_value_details(
        flag_key="new_checkout",
        user={
            "key": "user-123",
            "country": "IN",
        },
        default=False,
    )

    print("Evaluation details:", details)

finally:
    client.close()