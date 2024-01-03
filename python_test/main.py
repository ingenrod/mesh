import sqlite3
import base64
from uuid import uuid4
import fifo
import sys
import logging
import curses
import datetime
import time
import collections

logging.basicConfig(level=logging.INFO)
log = logging.info

def create_uuid():
    return base64.urlsafe_b64encode(uuid4().bytes).decode("ascii").strip("=")[0:22]


class Mesh:
    def __init__(self, name):
        self.name = name
        self.connection = sqlite3.connect(f"{name}.mesh.db")
        self.cursor = self.connection.cursor()


        for table_stmt in [
            """
            create table if not exists mac_addresses(
                address text primary key,
                last_interaction datetime default CURRENT_TIMESTAMP
            );
            """,
            """
            create table if not exists messages (
                id integer  primary key autoincrement,
                file_uuid text,
                sender text,
                receiver text,
                created_at datetime default CURRENT_TIMESTAMP,
                delivered_at datetime,
                delivered bool default false,
                foreign key (file_uuid) references files(uuid),
                foreign key (sender) references mac_addresses(address),
                foreign key (receiver) references mac_addresses(address)
            );
            """,
            """
            create table if not exists files (
                uuid text primary key,
                name text not null
            );
            """,
            """
            create table if not exists file_to_tags (
                file_uuid text,
                tag text,
                primary key(file_uuid, tag),
                foreign key(file_uuid) references files(uuid)
            );
            """,
            """
            create table if not exists file_to_chunks (
                file_uuid text,
                chunk_index int not null,
                data text,
                primary key (file_uuid, chunk_index),
                foreign key (file_uuid) references files(uuid)
            );
            """,
        ]:
            self.cursor.execute(table_stmt)
            self.connection.commit()

    def create_file(self, name, data,*tags):
        chunk_length=10

        uuid = create_uuid()
        stmt = f"""insert into files (uuid, name) values ('{uuid}', '{name}');"""

        self.cursor.execute(stmt)
        

        encoded_data = base64.b64encode(data).decode("ascii")
        values = ",".join([f"('{uuid}', {index}, '{encoded_data[offset:offset+chunk_length]}')"
                        for index, offset in enumerate(range(0, len(encoded_data), chunk_length))] )
        stmt = f"""
        insert into file_to_chunks(file_uuid, chunk_index, data)
        values {values} ;
        """

        self.cursor.execute(stmt)
        
        values = ",".join([f"('{uuid}','{tag}')" for tag in tags])
        stmt = f"""
        insert or ignore into file_to_tags (file_uuid, tag)
        values {values} ;
        """
        self.cursor.execute(stmt)
        self.connection.commit()

        
        return uuid


    def create_message(self, sender, receiver, file_uuid):
        stmt = f"""
        insert or replace into mac_addresses (address, last_interaction)
        values ('{sender}', CURRENT_TIMESTAMP), ('{receiver}', CURRENT_TIMESTAMP);
        """
        self.cursor.execute(stmt)
    
        stmt = f"""
        insert into messages(sender, receiver, file_uuid) 
        values ('{sender}', '{receiver}', '{file_uuid}')
        """
        self.cursor.execute(stmt)
        self.connection.commit()

    
    def create_simple_message(self, sender, receiver, title, contents):
        file_uuid = self.create_file(title, contents, "message")
        self.create_message(sender, receiver, file_uuid)
    
    def transmit_latest_message(self, transmit): 
        stmt = """
        select m.id, file_uuid, sender, receiver, name from messages m
        
        join files f on m.file_uuid = f.uuid
        where not(m.delivered) order by m.created_at desc limit 1
        ;
        """
        self.cursor.execute(stmt)
       
        message = self.cursor.fetchone()
        if not message:
            return
        message_id, file_uuid, sender, receiver, name = message

        transmit(f"{sender}.n.{file_uuid}.{name}", receiver)
        

        stmt = f"""
        select chunk_index, data from file_to_chunks where file_uuid = '{file_uuid}'
        """
        self.cursor.execute(stmt)
        chunks = self.cursor.fetchall()
        for chunk_index, data in chunks:
            transmit(f"{sender}.c.{file_uuid}.{chunk_index}.{data}", receiver)

        stmt = f"""
        select file_uuid, tag from file_to_tags where file_uuid = '{file_uuid}'
        """
        self.cursor.execute(stmt)
        tags = self.cursor.fetchall()
        for _,tag in tags:
            transmit(f"{sender}.t.{file_uuid}.{tag}", receiver)
        
        stmt = f"""
        update messages
        set delivered=true
        where id = {message_id};
        """
        self.cursor.execute(stmt)
        self.connection.commit()

        return message_id


    def receive_packet(self, sender, packet):
        type_of_packet, file_uuid, packet = packet.split(".", 2)
        if type_of_packet == "n":
            #name
            stmt = f"insert or ignore into files(uuid, name) values ('{file_uuid}', '{packet}')" 
            self.cursor.execute(stmt)
            stmt = f"""insert or ignore into messages(file_uuid, sender, receiver, delivered_at, delivered) 
            values ('{file_uuid}', '{sender}', '{self.name}',CURRENT_TIMESTAMP, true)"""
            self.cursor.execute(stmt)
        elif type_of_packet =="t":
            stmt = f"insert or ignore into file_to_tags(file_uuid, tag) values ('{file_uuid}', '{packet}')" 
            self.cursor.execute(stmt)
            # tag
        elif type_of_packet == "c":
            # chunk
            chunk_index, data = packet.split(".", 1)
            stmt = f"""insert or ignore into file_to_chunks(file_uuid, chunk_index, data) 
            values ('{file_uuid}', {chunk_index}, '{data}')"""
            self.cursor.execute(stmt)
        self.connection.commit()




def main():
    name = sys.argv[1]

    mesh = Mesh(name)

    stdscr = curses.initscr()
    curses.noecho()
    stdscr.nodelay(1) # set getch() non-blocking

    stdscr.addstr(0,0,"Write receipient[tab]title[tab]message, send with enter\"q\" to exit...")
    stdscr.addstr(1,0,"to: ")
    stdscr.addstr(2,0,"title: ")
    stdscr.addstr(3,0,"msg: ")
    stdscr.addstr(4,0,"status: ")
    stdscr.addstr(5,0,"linebuffer: ")


    receipient = ""
    title=""
    message = ""
    line = ""
    sending_at = None
    transmitted_messages = collections.deque(maxlen=5)
    received_messages = collections.deque(maxlen=5)
    try:
        while 1:

            if sending_at != None and sending_at < time.time():
                stdscr.addstr(4,0,"status:              ")
                sending_at = None


            c = stdscr.getch()
            if c == 3:
                raise KeyboardInterrupt
            elif c == curses.KEY_ENTER or c == 10 or c == 13:
                sending_at = time.time()+3
                stdscr.addstr(4,0,"status: sending")
                print(message)
                mesh.create_simple_message(name, receipient, title, message.encode())

            elif c == ord('q'): 
                break
            elif c in [curses.KEY_BACKSPACE,8,127]:
                line = line[:-2]
            elif 0 <= c < 128: #is ascii
            
                line += chr(c)

                try:
                    receipient, title, message = line.split("\t", 2)
                    stdscr.addstr(1,0,("to: "+receipient).ljust(50," "))
                    stdscr.addstr(2,0,("title: "+title).ljust(50," "))
                    stdscr.addstr(3,0,("msg: "+message[0:30]+"...").ljust(50, " "))
                except:
                    pass

            stdscr.addstr(7,0,("transmitted_messages: "+str(list(transmitted_messages))).ljust(50," "))
            stdscr.addstr(8,0,("received_messages: "+str(list(received_messages))).ljust(50, " "))
            stdscr.addstr(5,0,("linebuffer: "+line).ljust(50, " "))


            """
            Do more things
            """
            transmitted_message = mesh.transmit_latest_message(fifo.put)
            if transmitted_message:
                transmitted_messages.append(transmitted_message)

            received_message = fifo.get(name)
            if received_message:

                received_messages.append(received_message)
                sender, packet = received_message.split(".", 1)
                mesh.receive_packet(sender, packet)

    finally:
        curses.endwin()
        

if __name__ == "__main__":
    main()