import json
import eth_keyfile
import eth_keys


class Wallet:
    def __init__(self, privkey):
        pk = eth_keys.keys.PrivateKey(privkey)

        self.address = pk.public_key.to_address()
        self.checksum_address = pk.public_key.to_checksum_address()
        self.privkey = privkey

    def __repr__(self):
        return "<Wallet [address: {0}]>".format(self.address)


def load(filename, password):
    with open(filename) as wallet:
        privkey = eth_keyfile.decode_keyfile_json(json.load(wallet), password.encode("utf-8"))
        return Wallet(privkey)
