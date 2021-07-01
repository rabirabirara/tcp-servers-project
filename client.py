import time
import asyncio
import sys
import json

async def iamat(port):
    # Try to connect to this host at this port.  A connection returns a reader-writer pair, streams which are established by the server, actually.
    reader, writer = await asyncio.open_connection('127.0.0.1', port)
    # Encode this data and write it to the server down the writer stream.
    writer.write(f"IAMAT kiwi.cs.ucla.edu +34.068930-118.445127 {time.time() - 3.0}\n".encode())
    # Read server response.
    data = await reader.readline()
    print(f"Received: {data.decode()}")
    # ALways close the writer at the end of things.
    writer.close()

async def whatsat(port):
    reader, writer = await asyncio.open_connection('127.0.0.1', port)
    writer.write("WHATSAT kiwi.cs.ucla.edu 10 6\n".encode())
    data = await reader.readline()
    print(f"Received:\n{data.decode()}", end='')
    query = await reader.readuntil(b'\n\n')
    print(query.decode())
    writer.close()


if __name__ == '__main__':
    l = len(sys.argv)
    if l > 1:
        port = sys.argv[1]
        if l > 2:
            command = sys.argv[2]
    else:
        port = 15225
        command = 'iamat'
    if command == 'iamat':
        asyncio.run(iamat(port))
    elif command == 'whatsat':
        asyncio.run(whatsat(port))
