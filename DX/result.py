from .utils import prettify, highlight


class Result:
    def __init__(self, data):
        self.data = data

    def __repr__(self):
        return highlight(prettify(self.data))

    def json(self):
        return self.data
