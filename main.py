import os

from sanic import Sanic
from sanic.exceptions import InvalidUsage
from sanic.response import json as jsonify

from gdax_client import get_products, OrderBookClient
from knapsack import knapsack

app = Sanic()


def match_product_id(base_currency: float, quote_currency: float) -> (str, bool):
    """
    This will check if the currencies provided are in the GDAX. Additionally, if the two parameters
    are reversed but in the GDAX it will provide that it is inverted in the return. If the currencies do not
    exist an error will be raised.

    :param base_currency: a currency
    :param quote_currency: a currency
    :return: the corresponding product ID and if it is inverted
    """
    if '{}-{}'.format(base_currency, quote_currency) in products:
        product_id = '{}-{}'.format(base_currency, quote_currency)
        inverted = False
    elif '{}-{}'.format(quote_currency, base_currency) in products:
        product_id = '{}-{}'.format(quote_currency, base_currency)
        inverted = True
    else:
        raise InvalidUsage('Invalid exchange!')
    return product_id, inverted


@app.route('/quote', methods=['POST'])
async def on_get_quote(request):
    json = request.json

    # Handle body matching
    def get(tag):
        if tag not in json:
            raise InvalidUsage('JSON is missing: \'{}\''.format(tag))
        return request.json[tag].strip().upper()

    base_currency, quote_currency, action = get('base_currency'), get('quote_currency'), get('action')
    amount = float(get('amount'))
    product_id, inverted = match_product_id(base_currency, quote_currency)

    # match the type of order to the type of dataset
    book = client.get_book(product_id)
    if book is None:
        raise InvalidUsage('No data available yet!')
    if action == 'BUY':
        data = book.get_asks()
    elif action == "SELL":
        data = book.get_bids()
        if inverted:
            raise InvalidUsage('Base currency and quote currency reversed for sell quote!')
    else:
        raise InvalidUsage('Unknown action type!')

    properties = products[product_id]
    weights, values = [], []
    # Find the scalar which is used to convert floats to the nearest integer for weighting
    # Precision is used in exporting result with proper number of decimals
    if inverted:
        precision = 8
        amount_scalar = properties['quote_increment']
    else:
        precision = 2
        amount_scalar = properties['base_min_size'] * properties['quote_increment']
    # Go through converting prices and sizes to weights and values
    for (price, size) in data:
        exchange_rate = (size * price)
        if inverted:
            weights.append(int(exchange_rate / amount_scalar))
            values.append(size)
        else:
            weights.append(int(size / amount_scalar))
            values.append(exchange_rate)
    # run knapsack algorithm
    total = knapsack(values[:50], weights[:50], amount / amount_scalar)

    # return pretty formatted json result
    return jsonify({
        'price': '{:.{prec}f}'.format(total / amount, prec=precision),
        'total': '{:.{prec}f}'.format(total, prec=precision),
        'currency': quote_currency
    })


def main():
    global app, client, products
    host = os.getenv('HOST', '0.0.0.0')
    print('Reading HOST environment variable as {}'.format(host))
    port = os.getenv('PORT', 8000)
    print('Reading PORT environment variable as {}'.format(port))
    products = get_products()
    print('Supported Products: {}'.format(', '.join(products.keys())))
    print('Starting...\n')
    client = OrderBookClient(products.keys(), should_print=False)
    print()
    client.start()
    app.run(host=host, port=port)


if __name__ == '__main__':
    main()
