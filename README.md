# mesh


create a mesh network of esp32 that scales citywide in svendborg

the network aims to facilitate :
* sneakernet and file sharing (albeit on a very slow connection, so files are rather small)
* website hosting in the network
* realtime communications with chat in text and audio using l[yra codec](https://github.com/neuvideo/lyra-js)
* data communications for apps on the mesh network and exchange of sensor informations etc


the esp32's also expose a wifi accesspoint themselves where you can use a html/js webapp to access the mesh network for filesharing/chat/calls etc

if you want to interface the esp32 to an existing network you have to piggybag the esp32 with another esp32 that acts as a wifi bridge from your network to the network of the esp32.

* use https://github.com/thinger-io/Protoson for message format

* use [zhnetwork](https://github.com/aZholtikov/zh_network) as mesh transport layer
* ideally everything is a message
  * messages can have tags signifying their type
  * messages have titles, if a message has a tag=="file" then the title is the "filename" including ending
  * 
* use https://github.com/siara-cc/esp32_arduino_sqlite3_lib as db
* when sending messages
  ```
  messages[
  int id
  from references origin_mac_adresses(id)
  to references origin_mac_adresses(id)
  txt title var char 150
  datetime created
  int tries default 10
  ]
  tags [
  int message_id references messages(id)
  enum tag ("file", "message")
  ]
  message_chunk [
  int file references messages(id)
  int id
  blob data # max 150 bytes
  ]
   origin_mac_adresses [
    txt mac-adress
    int id
    ]

  ```
  when you wanna send a message:
  1. create a message with all its chunks in the db
  2. a loop runs through all messages (recent first) that have a "to" that is not the nodes own adress and a "tries" that is larger than 0
  4. the loop tries to transmit a message by looping through all its chunks and transmitting them, if it suceeds transmitting all chunks then it will set the "tries" to -1 signifying "transmission of message succeeded"
  5. if the loop has a failure during message transmission it will decrese the "tries"
  6. a message with "tries" == 0 is a failed transmission and isnt retransmitted ever again
* when storing files:
  * chunk them into chunks of size 150 bytes
  * give each chunk a name: [mac-adress of origin node].[uuid] by doing this we avoid filename collisions across the mesh network
  * keep a mapping like this:
    ```
    files [
    txt filename
    int id
    int mac_adress refer all es origin_mac_adresses(id)
    ]
    origin_mac_adresses [
    mac-adress
    int id
    ]
    chunks [
    int file references files(id)
    int id
    blob data # max 150 bytes
    ]
    ```
    
