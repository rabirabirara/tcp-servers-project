# tcp-servers-project
School project for prototyping a herd of TCP servers that make HTTP requests and share information.


# Motivation

We were tasked to determine the effectiveness of Python's `asyncio` and `aiohttp` libraries.  Along the way we learned to write basic functionality in the `async/await` paradigm.
This project sets up a small prototype of an application server herd, which can take a small set of commands.  It operates using access to Google Maps through the Google API.
It can send location data (JSON) to clients that query the server; it can retrieve location data from Google Maps using HTTP requests; it propagates queries to other servers
to provide redundant logging.
