import logging
import binascii

from web3 import Web3, HTTPProvider
import eth_abi


logging.basicConfig()

class Contract:
    def __init__(self, web3, wallet, address):
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logging.WARNING)

        self.web3 = web3
        self.wallet = wallet
        self.address = address

    def _encode_function_call(self, fun, fun_argt, fun_argv):
        argt = "(" + ",".join(fun_argt) + ")"
        funsig = fun + argt
        sig = Web3.sha3(funsig.encode("utf-8"))
        data = "0x" + binascii.hexlify(sig[:4]).decode("utf-8") + binascii.hexlify(eth_abi.encode_single(argt, fun_argv)).decode("utf-8")
        return (data, funsig)

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
                raise RuntimeError("failed to execute function, hash: %s".format(txhashstr))

        self.logger.debug("SEND %s: %s", funsig, txhashstr)

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

        rett = "(" + ",".join(fun_rett) + ")"
        decoded = eth_abi.decode_single(rett, result)

        self.logger.debug("CALL %s: %s", funsig, str(decoded))

        # Return single value instead of tuple.
        if len(fun_rett) == 1:
            return decoded[0]

        return decoded

