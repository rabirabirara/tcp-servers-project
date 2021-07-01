# TCP is between each server on the same router.
import asyncio
# HTTP is access to far servers through http protocol
import aiohttp

import sys
import time
import json
import re
from pprint import pprint
from enum import Enum


# This design is really messy, but it's just a prototype.


# Take a string representing coordinates and split into latitude and longitude strings.
def extract_coords(location):
    coords = re.split(r'[+-]', location)
    coords = [x for x in coords if x != '']
    signs = re.findall(r'[+-]', location)
    signs = [x for x in signs if x != '']
    lat_str = "{}{}".format(signs[0], coords[0])
    lon_str = "{}{}".format(signs[1], coords[1])
    return (lat_str, lon_str)


# Assigned ports 15225..15229
class Servers(Enum):
    # server := (port-number, [contacted-ports])
    Riley    = (15225, [15226, 15227])
    Jaquez   = (15226, [15225, 15229])
    Juzang   = (15227, [15225, 15228, 15229])
    Campbell = (15228, [15227, 15229])
    Bernard  = (15229, [15226, 15227, 15228])

    # The first ten characters are those describing the event kind and the '|'.
    # Unused for now. Expensive anyway.
    def already_logged(string, cmdkind):
        server_log.seek(0)
        if cmdkind == Commands.PROPAGATE:
            for line in server_log.readlines():
                ln = line.split('|')
                if len(ln) == 3 and ln[2].strip() == string.strip():
                    return True
        else:
            for line in server_log.readlines():
                if line[10:].rstrip() == string.rstrip():
                    return True
        return False

    @classmethod
    def names(cls):
        lst = []
        for server in cls:
            lst.append(server.name)
        return lst

    @classmethod
    def ports(cls):
        lst = []
        for server in cls:
            lst.append(server.value[0])
        return lst

    # In any logging case, don't force write to disk; only flush.
    # And don't forget the newlines!
    def log_input(string):
        server_log.write(f"In  <-  | {string.rstrip()}\n")
        server_log.flush()

    def log_output(string):
        server_log.write(f"Out  -> | {string.rstrip()}\n")
        server_log.flush()

    def log_output_query(string):
        server_log.write(f"Queried | {string.rstrip()}\n")
        server_log.flush()

    @classmethod
    def log_opened_connection(cls, to_port):
        server_log.write(f"Connect | {cls.into_name(to_port)} {to_port} {time.time()}\n")
        server_log.flush()

    @classmethod
    def log_received_connection(cls, from_port):
        server_log.write(f"Receive | {cls.into_name(from_port)} {from_port} {time.time()}\n")
        server_log.flush()

    @classmethod
    def log_failed_connection(cls, port):
        server_log.write(f"Failed  | {cls.into_name(port)} {port} {time.time()}\n")
        server_log.flush()

    @classmethod
    def log_closed_connection(cls, port):
        server_log.write(f"Closed  | {cls.into_name(port)} {port} {time.time()}\n")
        server_log.flush()

    @classmethod
    def is_valid(cls, name):
        for member in cls:
            if name == member.name:
                return True
        return False

    @classmethod
    def from_name(cls, name):
        for member in cls:
            if name == member.name:
                return member
        return None

    @classmethod
    def from_port(cls, port):
        for member in cls:
            if port == member.value[0]:
                return member
        return None

    @classmethod
    def into_name(cls, port):
        for member in cls:
            if port == member.value[0]:
                return member.name
        return None

    @classmethod
    def into_port(cls, name):
        for member in cls:
            if name == member.name:
                return member.value[0]
        return None

    @classmethod
    def ports_to_names(cls, ports):
        return [cls.into_name(x) for x in ports]

    @classmethod
    def names_to_ports(cls, names):
        return [cls.into_port(x) for x in names]


# If only there was pattern matching on enum variants. Can't wait for Python 3.10.
class Commands(Enum):
    PROPAGATE = 0
    AT = 1
    IAMAT = 2
    WHATSAT = 3

    def form_invalid(cmdtype, fields):
        return f"? {cmdtype}{fields}\n"

    def form_at(name, received_gap, clientid, coords, timesent):
        return "AT {} {:+f} {} {} {}\n".format(name, received_gap, clientid, coords, timesent)

    def form_propagate(command, visited):
        return f"PROPAGATE {visited} | {command}"

    def form_places_get(location, radius):
        lat, lon = extract_coords(location)
        return f"https://maps.googleapis.com/maps/api/place/nearbysearch/json?key={api_key}&location={lat},{lon}&radius={radius * 1000}"

    # Failed connection usually take 2-3 seconds to timeout.
    # We can use asyncio.wait_for() to enforce a shorter timeout.
    # Here, we choose not to just in case.
    async def send_propagate(contact_port, propagate_cmd):
        try:
            reader, writer = await asyncio.open_connection(current_host, contact_port)
            Servers.log_opened_connection(contact_port)
            writer.write(f"{propagate_cmd}\n".encode())
            # Don't wait for a response - the server could be down.
            writer.close()
            Servers.log_closed_connection(contact_port)
        except Exception as e:
            Servers.log_failed_connection(contact_port)

    # Remember to log connection establishments.
    # Takes a command to propagate and a list of visited server names.
    @classmethod
    async def propagate(cls, command, old_visited):
        server = Servers.from_name(server_name)
        contacts = server.value[1]
        contact_names = Servers.ports_to_names(contacts)

        if old_visited is not None:
            new_visited = old_visited.copy()
            # Add each new contact to the list if it isn't already in the list.
            if server_name not in old_visited:
                new_visited.append(server_name)
            for name in contact_names:
                if name not in old_visited:
                    new_visited.append(name)
            # Produce list of ports that haven't been visited yet.
            unvisited_contact_names = [x for x in contact_names if x not in old_visited]
            unvisited_contacts = Servers.names_to_ports(unvisited_contact_names)
        else:
            new_visited = contact_names
            new_visited.append(server_name)
            unvisited_contacts = contacts

        new_visited.sort()
        new_visited_str = '='.join(new_visited)
        propagate_cmd = cls.form_propagate(command, new_visited_str)
        # Don't use create_task()! Calling an async function already creates a coroutine.
        # Tasks are actually appendages to the event loop indicating you want the coroutine executed when possible.
        connect_routines = [cls.send_propagate(contact_port, propagate_cmd) for contact_port in unvisited_contacts]
        await asyncio.gather(*connect_routines)

    @classmethod
    async def send_places_query(cls, clientid, location, radius, info):
        lat, lon = extract_coords(location)
        async with session.get(cls.form_places_get(location, radius)) as resp:
            res = await resp.text()
            decode = json.loads(res)
            # Give as many places as info supports.
            results = decode['results']
            del results[info:]
            decode['results'] = results

            # Re-encode, send.
            encode = json.dumps(decode, sort_keys=True, indent=4)
            return json.dumps(decode, sort_keys=True, indent=4)

    # Some other server has already vetted this as a valid, storable command.
    # Then, store it and continue propagating.
    # Extract visited servers and then propagate message.
    # WARNING: there is no checking for invalid propagation.
    @classmethod
    async def handle_propagate(cls, fields):
        cmdtype = Commands.PROPAGATE.name
        visited = fields[0].split('=')
        visited_ports = Servers.names_to_ports(visited)
        # '|' is fields[1]
        command = ' '.join(fields[2:])
        await cls.propagate(command, visited)

        # clientid of AT is the 6th element of fields.
        clientid = fields[5]
        coords = fields[6]
        # Don't worry if redundant rewrites have corrupted data for now. It's just a prototype!
        client_data[clientid] = (command, coords)

    @classmethod
    async def handle_iamat(cls, fields):
        cmdtype = Commands.IAMAT.name
        if len(fields) != 3:
            return cls.form_invalid(cmdtype, fields)
        clientid = fields[0]
        if clientid.isspace():
            return cls.form_invalid(cmdtype, fields)
        coords = fields[1]
        try:
            timesent = float(fields[2])
        except ValueError:
            # The time given is not a float.
            return cls.form_invalid(cmdtype, fields)
        received_gap = time.time() - timesent
        command = cls.form_at(server_name, received_gap, clientid, coords, timesent)
        await cls.propagate(command, None)

        client_data[clientid] = (command, coords)
        Servers.log_output(command)
        return command

    @classmethod
    async def handle_whatsat(cls, fields):
        cmdtype = Commands.WHATSAT.name
        if len(fields) != 3:
            return cls.form_invalid(cmdtype, fields)
        clientid = fields[0]
        if clientid.isspace():
            return cls.form_invalid(cmdtype, fields)
        try:
            radius = int(fields[1])
            if radius > 50:
                return cls.form_invalid(cmdtype, fields)
        except:
            return cls.form_invalid(cmdtype, fields)
        try:
            info = int(fields[2])
            if info > 20:
                return cls.form_invalid(cmdtype, fields)
        except:
            return cls.form_invalid(cmdtype, fields)
        try:
            most_recent_at = client_data[clientid][0]  # includes newline
            location = client_data[clientid][1]
        except KeyError:
            return cls.form_invalid(cmdtype, fields)
        places_query = await cls.send_places_query(clientid, location, radius, info)
        response = most_recent_at + places_query + '\n\n'

        # Yes, this means we log literally the entirety of the query.  Not a problem.
        Servers.log_output_query(cls.form_places_get(location, radius))
        Servers.log_output(response)
        return response

    # Unused for now.  Possible extensions to the API that involve directly sending AT commands to the servers
    # may someday arise - e.g. servers hosted on different hosts, not just on different ports.
    # @classmethod
    # async def handle_at(cls, fields):
    #     cmdtype = Commands.AT.name
    #     contact_point = fields[0]
    #     if not Servers.is_valid(contact_point):
    #         return cls.form_invalid(cmdtype, fields)
    #     try:
    #         received_gap = float(fields[1])
    #     except:
    #         return cls.form_invalid(cmdtype, fields)
    #     clientid = fields[2]
    #     if clientid.isspace():
    #         return cls.form_invalid(cmdtype, fields)
    #     coords = fields[3]
    #     try:
    #         timesent = float(fields[4])
    #     except:
    #         return cls.form_invalid(cmdtype, fields)
    #     command = cls.form_at(contact_point, received_gap, clientid, coords, timesent)
    #     return (command, False)


async def handle_message(command, msg):
    if command == Commands.IAMAT.name:
        return await Commands.handle_iamat(msg)
    elif command == Commands.WHATSAT.name:
        return await Commands.handle_whatsat(msg)
    # Unused for now.
    # elif command == Commands.AT.name:
    #     return await Commands.handle_at(msg)
    else:
        return (Commands.form_invalid(command, msg), True)


# reader and writer are streams of data.  A reader stream yields encoded data to you; you must decode it to read it properly.
# A writer stream is for you to send decoded data down.  drain() is like flushing the stream.
async def handle_connection(reader, writer):
    (ip_address, port) = writer.get_extra_info('sockname')
    data = await reader.readline()
    string = data.decode()

    msg = string.split()
    command = msg.pop(0)

    # This means this could be inter-server communication.
    if command == Commands.PROPAGATE.name:
        Servers.log_received_connection(port)
        inner_info = string.split('|')[1]
        # * We can choose to not log redundantly.  But this might be slow, as it involves reseeking the entire file. 
        # * Besides, the log is about storing communication history, not about storing data.
        # if not Servers.already_logged(inner_info, Commands.PROPAGATE):
        #     Servers.log_input(string)
        Servers.log_input(string)
        await Commands.handle_propagate(msg)
    else:
        Servers.log_input(string)
        response = await handle_message(command, msg)
        writer.write(response.encode())
        await writer.drain()
    writer.close()


async def serve(server_repr):
    # Start a server at host 'localhost' at port '12345', with the job 'handle_connection' whenever a connection is received.
    server = await asyncio.start_server(handle_connection, host=current_host, port=server_repr.value[0])
    # Activate the server forever.
    await server.serve_forever()

async def close():
    await session.close()


async def main():
    if len(sys.argv) != 2:
        sys.exit("Please pass in the name of the server.  Exiting...")

    global server_name
    server_name = sys.argv[1]
    server = Servers.from_name(server_name)
    if server is None:
        sys.exit("Please pass in a correct server name! These names (unfortunately) had to be hardcoded in. Exiting...")

    # Open a file handle to a logfile for writing files.
    global server_log
    server_log = open(f"{server_name}.log", 'a+')

    global current_host
    current_host = '127.0.0.1'

    # FILL IN THE API KEY HERE
    global api_key
    api_key = ''

    # Map client IDs to the most recent AT command about them.
    global client_data
    client_data = {}

    global session
    session = aiohttp.ClientSession()

    server_log.write("Starting: {}\n".format(time.time()))
    server_log.flush()
    await serve(server)


if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    try:
        loop.run_until_complete(main())
    except KeyboardInterrupt:
        pass
    finally:
        loop.run_until_complete(close())
        try:
            server_log.write("Shutdown: {}\n".format(time.time()))
            server_log.close()
        except NameError:
            pass

