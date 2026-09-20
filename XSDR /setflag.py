import argparse
from Injector import FlagInjector

parser = argparse.ArgumentParser()

parser.add_argument("--flag", required=True)
parser.add_argument("--value", required=True)

args = parser.parse_args()

inj = FlagInjector()

try:

    inj.inject()

    result = inj.set_flag(
        args.flag,
        args.value
    )

    print("flag:", args.flag)

    print("type:", result["type"])

    print("address:", result["address"])

except Exception as e:

    print("error:", e)
