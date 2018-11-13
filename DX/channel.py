import binascii
import json
import requests
from web3 import Web3, HTTPProvider

from .result import Result
from .contract import Contract
from .crypto import sign_receipt, verify_datapoint
from .utils import draw_box, dxn2dei, dei2dxn, unpack_receipt


class Channel:
    API_RECEIPT_HEADER = "X-DX-PleasePay"
    API_ADDRESS_HEADER = "X-DX-Address"
    API_SIGNATURE_HEADER = "X-DX-Signature"

    def _open_new_channel(self):
        # Channel is not open, check for sufficient balance.
        balance = self.contracts["token"].call_function(
            fun="balanceOf",
            fun_argt=["address"],
            fun_argv=[self.wallet.address],
            fun_rett=["uint256"]
        )

        if balance < self.deposit:
            raise RuntimeError("failed to open channel: deposit greater than balance")

        # Approve allowance for channel manager contract.
        # TODO Listen for Approval and ChannelOpened events.
        self.contracts["token"].send_function(
            fun="approve",
            fun_argt=["address", "uint256"],
            fun_argv=[self.addresses["channel"], self.deposit],
            verify=True
        )

        # Confirm allowance.
        allowance = self.contracts["token"].call_function(
            fun="allowance",
            fun_argt=["address", "address"],
            fun_argv=[self.wallet.checksum_address, self.addresses["channel"]],
            fun_rett=["uint256"]
        )

        if self.deposit > allowance:
            raise RuntimeError("failed to open channel: deposit greater than allowance")

        # Open channel.
        tx = self.contracts["channel"].send_function(
            fun="openChannel",
            fun_argt=["address", "uint256"],
            fun_argv=[self.addresses["node"], self.deposit],
            verify=True
        )

        self.open = True

    def _open_existing_channel(self):
        # Fetch latest balance.
        r = requests.get(self.node + "/channel/receipt",
            headers = { Channel.API_ADDRESS_HEADER: self.wallet.checksum_address }
        )
        if r.status_code != requests.codes.ok:
            raise RuntimeError("failed to open channel: unable to fetch existing receipt from node")

        if r.content:
            self.receipt = r.json()

        self.open = True

    def __init__(self, wallet, node, deposit, provider):
        self.web3 = Web3(HTTPProvider(provider))
        self.wallet = wallet
        self.node = node
        self.deposit = deposit
        self.open = False
        self.receipt = {}

        # Get addresses from node.
        # FIXME Unsafe, temporary way to avoid updating contract addresses manually in SDK.
        r = requests.get(self.node + "/channel/metadata")
        if r.status_code != requests.codes.ok:
            raise RuntimeError("failed to open channel: unable to fetch metadata from node")

        res = r.json()
        self.addresses = {
            "node": res["node_address"],
            "token": res["token_address"],
            "channel": res["channel_manager_address"]
        }
        self.fees = {
            "network": res["network_fee"]
        }
        self.contracts = {
            "token": Contract(self.web3, wallet, self.addresses["token"]),
            "channel": Contract(self.web3, wallet, self.addresses["channel"])
        }

        # Check if channel already exists.
        channel = self.contracts["channel"].call_function(
            fun="getChannel",
            fun_argt=["address"],
            fun_argv=[self.addresses["node"]],
            fun_rett=["uint64", "uint256"]
        )

        if channel[0] > 0:
            self._open_existing_channel()
        else:
            self._open_new_channel()

    def query(self, endpoint, params = {}, model = "techindustry", metadata=False, verify=False):
        if not self.open:
            return None

        headers = { Channel.API_ADDRESS_HEADER: self.wallet.checksum_address }
        if self.receipt:
            headers[Channel.API_SIGNATURE_HEADER] = sign_receipt(self.web3, self.wallet, self.receipt)

        r = requests.get(self.node + "/" + endpoint,
                headers=headers,
                params={"model": model, **params}
        )

        if r.status_code != requests.codes.ok:
            print(r.text)
            return None

        if Channel.API_RECEIPT_HEADER not in r.headers:
            return None

        self.receipt = json.loads(r.headers[Channel.API_RECEIPT_HEADER])

        res = r.json()
        for datum in res["data"]:
            for rec in datum:
                if "metadata" in rec:
                    if not metadata:
                        del rec["metadata"]
                    elif verify:
                        valid = verify_datapoint(self.web3, rec["metadata"], rec["value"])
                        rec["metadata"]["is_signature_valid"] = valid

        return Result(res)

    def balance(self):
        return sum(map(lambda x: sum(x.values()), self.receipt.values()))

    def print_balance(self):
        str = ""
        if self.receipt: str += "Latest balance:\n"
        for key in self.receipt:
            str += "    " + key.capitalize() + "\n"
            for addr, amount in self.receipt[key].items():
                str += "        DXN {0:<6} → {1}\n".format(dei2dxn(amount), addr)
        str += "Total:  DXN {0:<6}".format(dei2dxn(self.balance()))

        print(draw_box("The DX Network", str))

    def print_state(self):
        if self.open:
            str = "Channel opened for {0}\nDeposit amount: DXN {1:<6}".format(self.wallet.checksum_address, dei2dxn(self.deposit))
        else:
            str = "Channel is closed\nTX hash is 0x{0}".format(self.hash)

        print(draw_box("The DX Network", str, 81))

    def settle(self):
        if not self.open:
            raise RuntimeError('channel is not open')

        headers = { Channel.API_ADDRESS_HEADER: self.wallet.checksum_address }
        if self.receipt:
            headers[Channel.API_SIGNATURE_HEADER] = sign_receipt(self.web3, self.wallet, self.receipt)

        # Request closing signature from node.
        r = requests.get(self.node + "/channel/close", headers=headers)
        if r.status_code != requests.codes.ok:
            print(r.text)
            return

        signature = binascii.unhexlify(r.text)

        # Channel has not been used, expect the node to send a signature for the channel closing fee.
        if not self.receipt:
            self.receipt["network"] = { self.addresses["node"]: self.fees["network"] }

        (addresses, values) = unpack_receipt(self.receipt)

        # Settle the channel.
        self.hash = self.contracts["channel"].send_function(
            fun="settleChannel",
            fun_argt=["address", "address[]", "uint256[]", "bytes"],
            fun_argv=[self.addresses["node"], addresses, values, signature],
            verify=True
        )

        self.open = False

def open(wallet, node, deposit, provider="http://127.0.0.1:8565"):
    return Channel(wallet, node, dxn2dei(deposit), provider)

