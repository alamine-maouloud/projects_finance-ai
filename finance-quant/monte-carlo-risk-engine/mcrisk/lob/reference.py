"""Pure-Python price-time priority order book.

A deliberately simple implementation with the same semantics as the C++
engine (mcrisk._native.OrderBook). Tests replay random order streams through
both and require identical fills and book states (differential testing).
"""

from __future__ import annotations

from collections import deque

BID, ASK = 0, 1


class ReferenceBook:
    def __init__(self, n_ticks: int):
        self.n_ticks = n_ticks
        self.levels = ({}, {})            # side -> {price: deque[[id, qty, owner]]}
        self.where = {}                   # id -> (side, price)
        self.next_id = 1
        self.fills = []

    @property
    def best_bid(self) -> int:
        return max(self.levels[BID]) if self.levels[BID] else -1

    @property
    def best_ask(self) -> int:
        return min(self.levels[ASK]) if self.levels[ASK] else self.n_ticks

    def _new_id(self) -> int:
        i = self.next_id
        self.next_id += 1
        return i

    def _match(self, side, qty, limit, taker_id, owner):
        maker = 1 - side
        book = self.levels[maker]
        filled = 0
        while qty > 0 and book:
            p = min(book) if side == BID else max(book)
            if (side == BID and p > limit) or (side == ASK and p < limit):
                break
            q = book[p]
            while qty > 0 and q:
                o = q[0]
                x = min(qty, o[1])
                self.fills.append((o[0], taker_id, p, x, side, o[2], owner))
                o[1] -= x
                qty -= x
                filled += x
                if o[1] == 0:
                    q.popleft()
                    del self.where[o[0]]
            if not q:
                del book[p]
        return filled

    def limit(self, side, price, qty, owner=0):
        if not 0 <= price < self.n_ticks:
            raise IndexError("price outside the tick grid")
        oid = self._new_id()
        qty -= self._match(side, qty, price, oid, owner)
        if qty > 0:
            self.levels[side].setdefault(price, deque()).append([oid, qty, owner])
            self.where[oid] = (side, price)
        return oid

    def market(self, side, qty, owner=0):
        oid = self._new_id()
        return self._match(side, qty, self.n_ticks - 1 if side == BID else 0, oid, owner)

    def cancel(self, oid) -> bool:
        if oid not in self.where:
            return False
        side, price = self.where.pop(oid)
        q = self.levels[side][price]
        for k, o in enumerate(q):
            if o[0] == oid:
                del q[k]
                break
        if not q:
            del self.levels[side][price]
        return True

    def volume(self, side, price) -> int:
        return sum(o[1] for o in self.levels[side].get(price, ()))

    def count(self, side, price) -> int:
        return len(self.levels[side].get(price, ()))

    def take_fills(self):
        out, self.fills = self.fills, []
        return out
