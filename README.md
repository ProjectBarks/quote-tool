# Coinbase Quote Tool

## Goal
The goal is to create a web service that provides quotes for digital currency trades using data from the GDAX order-book.

The service will handle requests to buy or sell a particular amount of a currency (the base currency) with another currency (the quote currency). The service should use the order-book to determine the best price the user would be able to get for that request by executing trades on GDAX. Note that the quantity the user enters will rarely match a quantity in the order book exactly. 

## Running
 **This application must run on python 3 or higher!** There are two ways to run this application:
 1. Either bundle it and run it on docker.
 2. Build it and run it yourself. To build and run it yourself run this command: 
 ```bash
 pip install -r ./requirements.txt
 python setup.py install 
 python main.py
 ``` 

## Service Specifications
| Route           | POST /quote                              |
| --------------- | :--------------------------------------- |
| Request Fields  | <ul><li>action (string): Either "buy" or "sell" </li><li>base_currency (String): The currency to be bought or sold</li><li>quote_currency (String): The currency to quote the price in</li><li>amount (String): The amount of the base currency to be traded</li></ul> |
| Response Fields | <ul><li>price (String): The per-unit cost of the base currency</li><li>total (String): Total quantity of quote currency</li><li>currency (String): The quote currency</li></ul> |

### Example Request

```json
{
	"action": "BUY",
	"base_currency": "USD",
	"quote_currency": "BTC",
	"amount": "1000"
}
```

### Example Response

````json
{
    "price": "0.00008861",
    "currency": "BTC",
    "total": "0.08860991"
}
````

## Design

![diagram](https://i.imgur.com/mMqerwx.png)

### Overview

The core design behind this tool is to be constantly linked to GDAX, listening for changes in the exchange for a low latency exchange estimation. It says up to date using web-sockets and a dictionary to maintain a group of order-books. Each order-book contains a cython based RBTree for fast insertion and query time to maintain the orders with as little delay as possible. The order-book is then filtered for the top fifty exchange rates and sent to a knapsack algorithm. The weighting, and values are dependent on how the user configures their request. The knapsack algorithm has a dynamic programming approach and was written in pure cython with a python translation layer to reduce interpreter delays. Finally, the calculation the results are sent back in JSON after some minor beatifications. 

### Libraries

* [Sanic](https://github.com/channelcat/sanic) — Cython HTTP Server for a fast RESTful service
* [Websocket Client](https://github.com/websocket-client/websocket-client) — Websocket client for Level 2 GDAX communication
* [BinTrees](https://github.com/mozman/bintrees) — Cython RBTree implementation for maintaining orders
* [Cython](http://cython.org/) — Used in building knapsack algorithm
* [NumPy](http://www.numpy.org/) — Middle layer between cython and python

### Thoughts and Notes

#### Why I didn't use [GDAX Python](https://github.com/danpaquin/gdax-python)

I was originally planning on using GDAX python in my project but the library had too many limitations and was too under-developed to warrant it's usage. First, it's websocket tool used a Level 3 connecting meaning there was an excess amount of data that would have to be processed, wasting bandwidth and computation time. Second, it lacked any kind of way of subscribing to more than one orderbook which would cause 10+ connections to the endpoint and a lot of redundant post-processing. ***However, I 100% took parts of the code and re-purposed it to fit the project specs.*** 

#### What could I do better?

I felt my knapsack algorithm was pretty good but for providing quotes it became difficult to describe what was "good enough". For instance, at what precision level do you stop weighting a bitcoin? A dollar? A cent? It all felt very relative and that it could be optimized based off context, if it a bid is over 1000$ stop considering cents, and so forth. *(I am very interested to hear how Coinbase handles this)* Second, if I had the time I would redo my communication pipeline between the GDAX Websocket Client and Sanic endpoint as there was a lack of respect for threading. 

#### Why python?

I felt python was a very versatile language and with the usage of cython in the parts required I could easily switch between interpreted and compiled code. With a balance between speed and understandability I felt it perfectly suited the project requirements. 