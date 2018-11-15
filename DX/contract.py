import logging
import binascii
import time

from web3 import Web3
import eth_abi


logging.basicConfig()

class Contract:
    def __init__(self, web3, wallet, address):
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logging.WARNING)

        self.web3 = web3
        self.wallet = wallet
        self.address = address

    def _build_types(self, args):
        return f"({','.join(args)})"

    def _encode_function_call(self, fun, fun_argt, fun_argv):
        argt = self._build_types(fun_argt)
        funsig = fun + argt
        sig = Web3.sha3(funsig.encode("utf-8"))

        data = "0x" + binascii.hexlify(sig[:4]).decode("utf-8") + binascii.hexlify(eth_abi.encode_single(argt, fun_argv)).decode("utf-8")

        return data, funsig

    def send_function(self, fun, fun_argt, fun_argv, verify=False):
        (data, funsig) = self._encode_function_call(fun, fun_argt, fun_argv)
        nonce = self.web3.eth.getTransactionCount(self.wallet.checksum_address, "pending")

        tx = {
            "nonce": nonce,
            "from": self.wallet.checksum_address,
            "to": self.address,
            "data": data
        }

        gasprice = self.web3.eth.gasPrice
        gas = self.web3.eth.estimateGas(tx)
        tx["gasPrice"] = gasprice
        tx["gas"] = gas

        signed_tx = self.web3.eth.account.signTransaction(tx, self.wallet.privkey)
        txhash = self.web3.eth.sendRawTransaction(signed_tx.rawTransaction)

        txhashstr = binascii.hexlify(txhash).decode("utf-8")

        # Check if transaction executed successfully.
        if verify:
            receipt = self.web3.eth.waitForTransactionReceipt(txhash)
            if receipt.status == 0:
                raise RuntimeError(f"failed to execute function, hash: {txhashstr}")

        self.logger.debug(f"SEND {funsig}: {txhashstr}")

        return txhashstr

    def call_function(self, fun, fun_argt, fun_argv, fun_rett):
        (data, funsig) = self._encode_function_call(fun, fun_argt, fun_argv)

        tx = {
            "from": self.wallet.checksum_address,
            "to": self.address,
            "data": data
        }

        gasprice = self.web3.eth.gasPrice
        gas = self.web3.eth.estimateGas(tx)
        tx["gasPrice"] = gasprice
        tx["gas"] = gas

        result = self.web3.eth.call(tx)

        decoded = eth_abi.decode_single(self._build_types(fun_rett), result)

        self.logger.debug(f"CALL {funsig}: {decoded}")

        # Return single value instead of tuple.
        if len(fun_rett) == 1:
            return decoded[0]

        return decoded

    def wait_for_event(self, ev, ev_argt, ev_argt_indexed=None, ev_argv_indexed=None, ev_rett=None, ev_callback=None):
        evsig = ev + self._build_types(ev_argt)
        sig = "0x" + binascii.hexlify(Web3.sha3(evsig.encode("utf-8"))).decode("utf-8")

        topics=[sig]
        if ev_argt_indexed is not None and ev_argv_indexed is not None and len(ev_argv_indexed) == len(ev_argt_indexed):
            for i in range(0, len(ev_argt_indexed)):
                topics.append("0x" + binascii.hexlify(eth_abi.encode_single(ev_argt_indexed[i], ev_argv_indexed[i])).decode("utf-8"))

        event_filter = self.web3.eth.filter({
            "address": self.address,
            "topics": topics
        })

        max_retries = 60 # 2 minutes timeout
        retries = 0

        while retries <= max_retries:
            for event in event_filter.get_new_entries():
                if ev_rett is not None:
                    ret = eth_abi.decode_single(self._build_types(ev_rett), binascii.unhexlify(event["data"][2:]))
                    if ev_callback and ev_callback(ret):
                        return ret
                else:
                    return True

            retries += 1
            time.sleep(2)

        raise RuntimeError(f"event timeout: {ev}")