import binascii
import json
import time

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
        print("Opening channel, please wait... It might take a few minutes depending on network conditions.")

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
        self.contracts["token"].send_function(
            fun="approve",
            fun_argt=["address", "uint256"],
            fun_argv=[self.addresses["channel"], self.deposit],
            verify=True
        )

        self.contracts["token"].wait_for_event(
            ev="Approval",
            ev_argt=["address", "address", "uint256"],
            ev_argt_indexed=["address", "address"],
            ev_argv_indexed=[self.wallet.checksum_address, self.addresses["channel"]]
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
        self.contracts["channel"].send_function(
            fun="openChannel",
            fun_argt=["address", "uint256"],
            fun_argv=[self.addresses["node"], self.deposit],
            verify=True
        )

        # TODO: Modify ChannelOpened to use indexed arguments for the addresses.
        self.contracts["channel"].wait_for_event(
            ev="ChannelOpened",
            ev_argt=["address", "address", "uint256", "uint64"],
            ev_rett=["address", "address", "uint256", "uint64"],
            ev_callback=lambda ev: ev[0] == self.addresses["node"].lower() and ev[1] == self.wallet.address
        )

        # Allow the node to sync the event as well.
        node_syncing = True
        while node_syncing:
            r = requests.get(f"{self.node}/semantic/status",
                headers = { Channel.API_ADDRESS_HEADER: self.wallet.checksum_address }
            )

            if r.status_code == requests.codes.ok:
                node_syncing = False

            time.sleep(2)

        self.open = True

    def _open_existing_channel(self):
        # Fetch latest balance.
        r = requests.get(f"{self.node}/channel/receipt",
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
        r = requests.get(f"{self.node}/channel/metadata")
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

    def query(self, endpoint, params=None, model ="techindustry", metadata=False, verify=False):
        if params is None:
            params = {}

        if not self.open:
            return None

        headers = { Channel.API_ADDRESS_HEADER: self.wallet.checksum_address }
        if self.receipt:
            headers[Channel.API_SIGNATURE_HEADER] = sign_receipt(self.web3, self.wallet, self.receipt)

        r = requests.get(f"{self.node}/{endpoint}",
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
            str += f"    {key.capitalize()}\n"
            for addr, amount in self.receipt[key].items():
                str += f"        DXN {dei2dxn(amount):<6} → {addr}\n"
        str += f"Total:  DXN {dei2dxn(self.balance()):<6}"

        print(draw_box("The DX Network", str))

    def print_state(self):
        if self.open:
            str = f"Channel opened for {self.wallet.checksum_address}\nDeposit amount: DXN {dei2dxn(self.deposit):<6}"
        else:
            str = f"Channel is closed\nTX hash is 0x{self.hash}"

        print(draw_box("The DX Network", str, 81))

    def settle(self):
        if not self.open:
            raise RuntimeError('channel is not open')

        headers = { Channel.API_ADDRESS_HEADER: self.wallet.checksum_address }
        if self.receipt:
            headers[Channel.API_SIGNATURE_HEADER] = sign_receipt(self.web3, self.wallet, self.receipt)

        # Request closing signature from node.
        r = requests.get(f"{self.node}/channel/close", headers=headers)
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

def open(wallet, node, deposit, provider="https://ropsten.dx.network/json-rpc"):
    return Channel(wallet, node, dxn2dei(deposit), provider)

