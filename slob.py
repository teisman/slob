import uuid

class Event(list):
    def __call__(self, *args, **kwargs):
        for f in self:
            f(*args, **kwargs)

    def __repr__(self):
        return "Event(%s)" % list.__repr__(self)


class Order(object):
    def __init__(self, limit, quantity, buy):
        self.cb_cancel = Event()
        self.cb_reduce = Event()
        self.cb_fill = Event()
        self.id = uuid.uuid4().hex
        self.limit = limit
        self.quantity = quantity
        self.buy = buy
        self.next = None
        self.prev = None

    @property
    def sell(self):
        return not self.buy

    def _eliminate(self):
        if self.quantity == 0:
            if self.next:
                self.next.prev = self.prev
            if self.prev:
                self.prev.next = self.next

    def cancel(self):
        self.cb_cancel(self)
        self.quantity = 0
        self._eliminate()

    def reduce(self, amount):
        if amount > self.quantity:
            raise Exception("Reduce amount can not exceed order quantity")
        self.cb_reduce(self, amount)
        self.quantity -= amount
        self._eliminate()

    def fill(self, amount):
        if amount > self.quantity:
            raise Exception("Fill amount can not exceed order quantity")
        self.cb_fill(self, amount)
        self.quantity -= amount
        self._eliminate()


class PriceLevel(object):
    def __init__(self, price):
        self.cb_eliminate = Event()
        self.price = price
        self.volume = 0
        self.head = None
        self.tail = None

    def add(self, order):
        self.volume += order.quantity
        order.cb_cancel.append(self._cancel)
        order.cb_reduce.append(self._reduce)
        order.cb_fill.append(self._fill)
        if self.head is None:
            self.head = order
            self.tail = order
        else:
            self.tail.next = order
            order.prev = self.tail
            self.tail = order

    def remove(self, order):
        if self.head == order:
            self.head = order.next
        if self.head is None:
            self.eliminate()

    def _cancel(self, order):
        self.volume -= order.quantity
        self.remove(order)

    def _reduce(self, order, amount):
        self.volume -= amount
        if order.quantity == amount:
            self.remove(order)

    def _fill(self, order, amount):
        self.volume -= amount
        if order.quantity == amount:
            self.remove(order)

    def eliminate(self):
        self.cb_eliminate(self)


class OrderContainer(object):
    def __init__(self, asc):
        self.asc = asc
        self.prices = []
        self.price_levels = {}

    def _new_price(self, price):
        self.prices.append(price)
        self.prices.sort(reverse=self.asc)

    def add(self, order):
        price = order.limit
        if price in self.prices:
            self.price_levels.get(price).add(order)
        else:
            self._new_price(price)
            price_level = PriceLevel(price)
            price_level.cb_eliminate.append(self._eliminate)
            price_level.add(order)
            self.price_levels.update({price: price_level})

    def market_price_level(self):
        market_price = self.prices[0]
        return market_price, self.price_levels[market_price]

    def depth(self):
        depth = {}
        for price, price_level in self.price_levels.items():
            depth.update({price: price_level.volume})
        return depth

    def _eliminate(self, pricelevel):
        price = pricelevel.price
        self.prices.remove(price)
        del self.price_levels[price]


class OrderBook(object):
    def __init__(self):
        self.orders = {}
        self.bids = OrderContainer(asc=True)
        self.asks = OrderContainer(asc=False)

    def add_order(self, order):
        self.orders.update({order.id: order})
        if order.buy:
            if not match(order, self.asks):
                self.bids.add(order)
        elif order.sell:
            if not match(order, self.bids):
                self.asks.add(order)

    def get_order(self, orderid):
        return self.orders.get(orderid)

    def depth(self):
        return {"bids": self.bids.depth(), "asks": self.asks.depth()}

def match(self, order, container):
    while True:
        try:
            price, level = container.market_price_level()
        except IndexError:
            # no market price level
            return False
        if (order.buy and order.limit < price) or \
           (order.sell and order.limit > price):
            # market price not good enough
            return False
        while level.head is not None:
            if order.quantity == 0:
                return True
            match_orders(order, level.head)

def match_orders(order1, order2):
    quantity = min(order1.quantity, order2.quantity)
    order1.fill(quantity)
    order2.fill(quantity)
    return quantity
