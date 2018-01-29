import json
from typing import Dict, Set, List, Tuple
from time import time as get_seconds
from decimal import Decimal
from threading import Thread

import requests
from bintrees import FastRBTree as RBTree
from websocket import create_connection, WebSocketConnectionClosedException


def get_products(api_url='https://api.gdax.com', timeout=30) -> Dict[str, Dict]:
    """
    Get a list of available currency pairs for trading.

    :param api_url: gdax url
    :param timeout: connection timeout in seconds
    :return:  Info about all currency pairs. Example:
        [
            "BTC-USD": {
                "display_name": "BTC/USD",
                "base_currency": "BTC",
                "quote_currency": "USD",
                "base_min_size": "0.01",
                "base_max_size": "10000.00",
                "quote_increment": "0.01"
            }
        ]
    """
    r = requests.get(api_url.rstrip('/') + '/products', timeout=timeout)

    def fix_data(data):
        return {
            'display_name': data['display_name'],
            'base_currency': data['base_currency'],
            'quote_currency': data['quote_currency'],
            'base_min_size': Decimal(data['base_min_size']),
            'base_max_size': Decimal(data['base_max_size']),
            'quote_increment': Decimal(data['quote_increment'])
        }

    return {item['id']: fix_data(item) for item in r.json()}


class OrderBookClient(object):
    """
    An async websocket layer responsible for connecting GDAX to orderbooks
    """
    def __init__(self, products=set(), url='wss://ws-feed.gdax.com', should_print=True):
        self.url = url
        self.products = products
        self.should_print = should_print
        self._data = dict()
        self.stop = False
        self.error = None
        self.ws = None
        self.thread = None

    def start(self):
        """
        Spawns an async thread, and begins filling orderbooks
        """
        def _go():
            self._connect()
            self._listen()
            self._disconnect()

        self._data.clear()
        self.stop = False
        self.on_open()
        self.thread = Thread(target=_go, daemon=True)
        self.thread.start()

    def _connect(self):
        # Remove any trailing forward slashes
        if self.url[-1] == '/':
            self.url = self.url[:-1]

        # open connection
        self.ws = create_connection(self.url)

        # Subscribe to product_ids
        awaiting_subscription = self.products
        self.products = set()
        self.subscribe(awaiting_subscription)

    def _listen(self):
        while not self.stop:
            try:
                if int(get_seconds() % 30) == 0:
                    # Set a 30 second ping to keep connection alive
                    self.ws.ping('keepalive')
                data = self.ws.recv()
                msg = json.loads(data)
            except (Exception, ValueError) as e:
                self.on_error(e)
            else:
                self.on_message(msg)

    def subscribe(self, products: Set[str]):
        """
        Will subscribe to any product ID's that are not currently subscribed and then adds it to the master list.
        :param products: a set of product_ids
        """
        if not isinstance(products, set):
            products = set(products)
        if not self.products >= products:
            if self.should_print:
                print('subscribing to {}'.format(', '.join(products - self.products)))
            self.ws.send(json.dumps({'type': 'subscribe', 'product_ids': list(products), 'channels': ['level2']}))
            self.products |= products

    def unsubscribe(self, products: Set[str]):
        """
        Unsubscribe to all product ids listed
        :param products: a set of product ids
        """
        if not isinstance(products, set):
            products = set(products)
        if self.should_print:
            print('unsubscribing to {}'.format(', '.join(products - self.products)))
        self.ws.send(json.dumps({'type': 'unsubscribe', 'product_ids': list(products), 'channels': ['level2']}))
        self.products -= products

    def get_book(self, book_id):
        return self._data.get(book_id)

    def _disconnect(self):
        try:
            if self.ws:
                self.ws.close()
        except WebSocketConnectionClosedException:
            pass

        self.on_close()

    def close(self):
        """ Will stop the current thread """
        self.stop = True
        self.thread.join()

    def on_open(self):
        if self.should_print:
            print('-- Listening --\n')

    def on_message(self, message: Dict):
        """
        Handle websocket message data and create new orderbooks if needed.

        :param message: a json object
        """
        # Read product id in message
        product_id = message.get('product_id', None)
        if product_id is not None:
            # Create the orderbook if it does not exist
            if product_id not in self._data:
                order_book = OrderBook(product_id)
                self._data[product_id] = order_book
            else:
                order_book = self._data[product_id]
            # pass the message to the orderbook
            order_book.process_message(message)
        if self.should_print:
            print(message)

    def on_close(self):
        """
        Handle when the client is closed
        """
        if self.should_print:
            print('\n-- Socket Closed --')

    def on_error(self, e: Exception, data=None):
        """
        When the client errors

        :param e: an error
        :param data: miscellaneous data
        :return:
        """
        self.error = e
        self.stop = True
        print('{} - data: {}'.format(e, data))


class OrderBook(object):
    """
    Uses RBTrees to handle all types of orders and store them in their corresponding bucket
    """
    def __init__(self, product_id: str):
        self._asks = RBTree()
        self._bids = RBTree()
        self._product_id = product_id

    @property
    def product_id(self):
        return self._product_id

    def process_snapshot(self, message: Dict):
        """
        Process a snapshot message
        :param message: json
        """

        # If a snapshot is sent reset trees
        self._asks = RBTree()
        self._bids = RBTree()

        # Parse all asks and add them to tree
        for ask in message['asks']:
            price, size = ask
            price = Decimal(price)
            size = Decimal(size)

            self._asks.insert(price, size)

        # Parse all bids and add them to tree
        for bid in message['bids']:
            price, size = bid
            price = Decimal(price)
            size = Decimal(size)

            self._bids.insert(price, size)

    def process_update(self, message: Dict):
        """
        Process a update message
        :param message: json
        """

        # Retrieve changes
        changes = message['changes']


        for change in changes:
            side, price, size = change

            # parse numbers and keep precision
            price = Decimal(price)
            size = Decimal(size)

            if side == 'buy':
                # If it is equal to 0 (or less than) the order no longer exists
                if size <= 0:
                    self._bids.remove(price)
                else:
                    self._bids.insert(price, size)
            elif side == 'sell':
                # If it is equal to 0 (or less than) the order no longer exists
                if size <= 0:
                    self._asks.remove(price)
                else:
                    self._asks.insert(price, size)

    def process_message(self, message: Dict):
        """
        Process all messages to identify next parser location
        :param message: json
        """
        # Read type
        msg_type = message['type']

        # dropped - not same product id
        if message.get('product_id', None) != self._product_id:
            return

        if msg_type == 'snapshot':
            self.process_snapshot(message)
        elif msg_type == 'l2update':
            self.process_update(message)

    def get_asks(self) -> List[Tuple[float, float]]:
        """
        Provides a list of asks and sizes in order of best price for the buyer

        :return: a list of Tuple's corresponding to ask (price rate), and ask size
        """
        asks = []
        for ask in self._asks:
            try:
                size = self._asks[ask]
            except KeyError:
                continue
            asks.append([float(ask), float(size)])
        return asks

    def get_bids(self) -> List[Tuple[float, float]]:
        """
       Provides a list of bids and sizes in order of best price for the seller

       :return: a list of Tuple's corresponding to ask (price rate), and ask size
       """
        bids = []
        for bid in self._bids:
            try:
                size = self._bids[bid]
            except KeyError:
                continue
            # For bids the best value (for selling) is reversed so inserting at the beginning flips the order
            bids.insert(0, [float(bid), float(size)])
        return bids

    def get_orders(self) -> Dict[str, List[Tuple[float, float]]]:
        """
        Uses get_bids and get_asks to compile all orders

        :return: both bids and asks
        """
        return {'asks': self.get_asks(), 'bids': self.get_bids()}

    def get_ask(self) -> Tuple[Decimal, Decimal]:
        """
        Get the best asking price. If it does not exist it returns a size of 0

        :return: the rate, and the size
        """
        price = self._asks.min_key()

        try:
            size = self._asks[price]
        except KeyError:
            return price, Decimal(0)

        return price, size

    def get_bid(self) -> Tuple[Decimal, Decimal]:
        """
        Get the best bid price. If it does not exist it returns a size of 0

        :return: the rate, and the size
        """
        price = self._bids.max_key()

        try:
            size = self._bids[price]
        except KeyError:
            return price, Decimal(0)

        return price, size


__all__ = ['get_products', 'OrderBook', 'OrderBookClient']
