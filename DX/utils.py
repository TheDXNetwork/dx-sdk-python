import json
import decimal

import pygments
import pygments.lexers
import pygments.formatters


def prettify(obj):
    return json.dumps(obj, sort_keys=True, indent=4)

def highlight(str):
    return pygments.highlight(str, pygments.lexers.JsonLexer(), pygments.formatters.TerminalFormatter())

def draw_box(title, str, linelen=69):
    titlelen = len(title)
    linecount = int((linelen - titlelen) / 2) - 2
    ret = f"┏{'━' * linecount} {title} {'━' * (linecount + 1 if titlelen % 2 == 0 else 0)}┓\n"

    lines = str.split("\n")
    for line in lines:
        ret += f"┃ {line}{' ' * (linelen - len(line) - 4)} ┃\n"
    ret += f"┗{'━' * (linelen - 2)}┛"

    return ret

def dxn2dei(val):
    return int(val * (10 ** 18))

def dei2dxn(val):
    return decimal.Decimal(val) / (10 ** 18)

def unpack_receipt(receipt):
    addresses = []
    values = []

    for key in ["network", "sellers"]:
        if key not in receipt:
            continue

        for addr in receipt[key]:
            addresses.append(addr)
            values.append(receipt[key][addr])

    return (addresses, values)

