import base64
import binascii

import dateutil.parser
import asn1
import eth_abi
from web3 import Web3

from .utils import unpack_receipt


def verify_datapoint(web3, metadata, value):
    seller = metadata["owner"]
    isodate = metadata["creation_date"]
    signature = metadata["signature"]

    date = dateutil.parser.parse(isodate)
    millis = int(date.timestamp() * 1000)

    enc = asn1.Encoder()
    enc.start()
    enc.enter(asn1.Numbers.Sequence)
    enc.write(seller.encode("utf-8"), asn1.Numbers.UTF8String)
    enc.write(millis, asn1.Numbers.Integer)
    enc.write(str(value).encode("utf-8"), asn1.Numbers.UTF8String)
    enc.leave()
    bytes = enc.output()
    hash = Web3.sha3(bytes)

    dec = asn1.Decoder()
    dec.start(base64.b64decode(signature))
    dec.enter()
    _, v = dec.read()
    _, r = dec.read()
    _, s = dec.read()

    addr = web3.eth.account.recoverHash(hash, vrs=(v, r, s))

    return addr == seller

def sign_receipt(web3, wallet, receipt):
    (addresses, values) = unpack_receipt(receipt)

    addrlen = len(addresses)
    if addrlen != len(values):
        raise RuntimeError("failed to sign receipt, invalid length")

    # Even though the arrays are dynamic, use static arrays to emulate abi.encodePacked behaviour.
    encoded = eth_abi.encode_single(f"(address[{addrlen}],uint256[{addrlen}])", [addresses, values])
    hash = Web3.sha3(encoded)
    sig = web3.eth.account.signHash(hash, private_key=wallet.privkey)

    return sig["signature"].hex()

