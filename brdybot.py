#used to access the config ini file
import configparser
#this is used for accessing the app/api
import requests
#this imports the information schema, sqlalchemy, and more
from schema import *
import json
#this is for connecting to IRC
import socket
#this is for connecting to the postgres database
import psycopg2
#this is for doing cute equations
import math
#sys for exiting threads?
import sys
#for multithreading for additional channels
import threading
#traceback is for error handling/printing so i can figure out what went wrong
import traceback
#sleep is so the bot won't overload during listening
from time import sleep
from datetime import datetime
from sqlalchemy.orm import aliased
import re
from sqlalchemy.dialects.postgresql import INTERVAL
from app import getCommands, getTwitchID,insert,update,delete,Session,func
from datetime import datetime

dbschema= 'pokemon,bot'
config = configparser.ConfigParser()
file = "C:/Users/Administrator/brdybot/chatbot.ini"
config.read(file)
host = config['database']['host']
database = config['database']['database']
user = config['database']['user']
password = config['database']['password']
botname = 'brdybot'
engine = create_engine('postgresql+psycopg2://'+user+':'+password+'@'+host+':5432/'+database,connect_args={'options': '-csearch_path={}'.format(dbschema)})
Base = declarative_base(engine)

Base.metadata.create_all(engine)

lock = threading.Lock()


def main():
    commanddict = Setup.getCommandDict() ### Make global?
    conn, token, readbuffer, server = Setup.getConnectionVariables() ### Make global?
    twitchusers = Setup.getChannels()
    #Setup.updateTwitchNames()
    #twitchusers = [(1236810,),]
    twitchusers.insert(0,(687207983,))
    for twitchuserid in twitchusers:
        twitchuserid = twitchuserid[0]
        #operators = {'brdy':1236810}
        operators = Setup.getOperants(twitchuserid)
        #create a listening thread
        #print("create listening thread")
        channel = Bot.getTwitchUserName(twitchuserid)
        threading.Thread(target=Bot.ircListen, name=channel, args=(conn, token, server, readbuffer, channel, twitchuserid, operators, commanddict)).start()
        sleep(2.2)

class Bot():
    def ircListen(conn, token, server, readbuffer, channel, twitchuserid, operators, commandDict):
        try:
            listenFlag = True
            # channel = 'brdy'
            #joining the channel
            if channel:
                server = socket.socket()
                server.connect(conn)
                server.send(bytes('PASS ' + token + '\r\n', 'utf-8'))
                server.send(bytes('NICK ' + botname + '\r\n', 'utf-8'))
                server.send(bytes('JOIN #' + channel + '\r\n', 'utf-8'))
                messageTime = datetime(1990,1,1)
                message = None
                #listening loop
                while listenFlag:
                    try:
                        commandlist = '|'.join(commandDict)
                        regexpression = r'^:[a-zA-Z0-9_]{3,25}![a-zA-Z0-9_]{3,25}@([a-zA-Z0-9_]{3,25})\.tmi\.twitch\.tv\s+PRIVMSG\s+#[a-zA-Z0-9_]{3,25}\s+:!('+commandlist+')\s(.*?)$'
                        pattern = re.compile(regexpression, re.M)
                        response = server.recv(2048).decode('utf-8')
                        if len(response) == 0:
                            continue
                        if "PING" in str(response):
                            server.send(bytes('PONG :tmi.twitch.tv\r\n', 'utf-8'))
                        elif ":!" in str(response):
                            for requestername,command,userMessage in map(lambda x: x.groups(), pattern.finditer(response)):
                                try:
                                    userMessage = re.sub(' +',' ',userMessage)
                                    parameters = userMessage.replace("\U000e0000","").replace("\U000e0002","").replace("\U000e001f","").strip().split(" ")
                                    permissions = (command != 'join' and ((requestername in operators.values()) or (requestername in [channel,'brdy']))) or (channel == botname) or (command == "botinfo")
                                    if (permissions):
                                        message,returnid,commandid,commandtype = Bot.doCommand(command,commandDict,twitchuserid,requestername,parameters)
                                        timeDiff = datetime.now() - messageTime
                                        timeDiff = timeDiff.total_seconds()
                                        if not (timeDiff <= 2 and message == lastMessage):
                                            Bot.chatMessage(message,channel,server)
                                            lastMessage = message
                                            messageTime = datetime.now()
                                        ccrid = Bot.logCommand(commandid,twitchuserid,requestername,message,parameters,commandtype,returnid)
                                        operators = Setup.getOperants(twitchuserid)
                                        commandDict = Setup.getCommandDict()
                                except:
                                    traceback.print_exc()
                                sleep(1)
                    except ConnectionResetError:
                        errortype = "ConnectionResetError"
                        listenFlag = False
                    except ConnectionAbortedError:
                        errortype = "ConnectionAbortedError"
                        listenFlag = False
                    except ConnectionRefusedError:
                        errortype = "ConnectionRefusedError"
                        listenFlag = False
                    except TimeoutError:
                        errortype = "TimeoutError"
                        listenFlag = False
                    except IndexError:
                        errortype = "IndexError"
                        listenFlag = False
                    except KeyError:
                        errortype = "KeyError"
                        listenFlag = False
                    except RuntimeError:
                        errortype = "RuntimeError"
                        listenFlag = False
                    except SystemExit:
                        errortype = "SystemExit"
                        listenFlag = False
                    except ValueError:
                        errortype = "ValueError"
                        listenFlag = False
                    except BrokenPipeError:
                        errortype = "BrokenPipeError"
                        listenFlag = False
                    except FileNotFoundError:
                        errortype = "FileNotFoundError"
                        listenFlag = False
                    except Exception:
                        errortype = "OtherError"
                        listenFlag = False
                    finally:
                        if not listenFlag:
                            print(channel)
                            print(errortype)
                            print('-------------------')
                            Bot.logException(errortype,twitchuserid)
                            commanddict = Setup.getCommandDict()
                            threading.Thread(target=Bot.ircListen, name=channel, args=(conn, token, user, server, readbuffer, channel, 'brdybot', twitchuserid, operators, commanddict)).start()
        except:
            traceback.print_exc()

    def chatMessage(messageString, channel, server):
        x = 1
        if len(messageString) > 299:
            if ' // ' in messageString:
                messagelist = messageString.split('//')
                for message in messagelist:
                    server.send(bytes('PRIVMSG #'+ channel + ' :'+message.replace("//","")+' \r\n', 'utf-8'))
            
            else:
                messagecount = len(messageString)/299
                for x in range(0,math.ceil(messagecount)):
                    splitmsg = messageString[x*299:(x+1)*299]
                    server.send(bytes('PRIVMSG #'+ channel + ' :'+splitmsg.replace("//","")+' \r\n', 'utf-8'))
        else:
            server.send(bytes('PRIVMSG #'+ channel + ' :'+messageString.replace("//","")+' \r\n', 'utf-8'))  

    def logException(errortype,twitchuserid):
        now = datetime.now()
        channel = Bot.getTwitchUserName(twitchuserid)
        lock.acquire()
        with open('C:/Users/Administrator/brdybot/errorlog.txt', 'a') as f:
            f.write(str(now)+' | '+errortype+' | '+str(twitchuserid)+' | '+str(channel)+'\r\n')
        lock.release()
        # conn, token, user, readbuffer, server, token = Setup.getConnectionVariables()
        # operators = Setup.getOperants(twitchuserid)
        # commanddict = Setup.getCommandDict()

    def logCommand(commandid,twitchuserid,requestername,message,parameters=None,commandtype=None,returnid=None):
        session = Session(engine)
        operanttwitchuserid = getTwitchID(requestername)
        #operanttwitchuserid = 1236810
        # print("logging...")
        if commandtype != 'game':
            gameid = session.query(Channel.gameid).filter(Channel.twitchuserid==twitchuserid).first()[0]
        try:
            values = {'commandid':commandid,'channeltwitchuserid':twitchuserid,'operanttwitchuserid':operanttwitchuserid,'channelcommandrequestreturn':message}
            if commandtype != 'game':
                values['gameid'] = gameid
            if returnid:
               values[commandtype+'id'] = returnid
            stmt = insert(ChannelCommandRequest).values(values)
            ccridr = session.execute(stmt).inserted_primary_key
            for ccridi in ccridr:
                ccrid = ccridi
            session.commit()
        except:
            session.rollback()
            traceback.print_exc()
        finally:
            session.close()
        if parameters:
            values = []
            for parameter in parameters:
                values.append({'channelcommandrequestid':ccrid,'channelcommandrequestparameter':parameter})
            try:
                stmt = insert(ChannelCommandRequestParameter).values(values)
                session.execute(stmt)
                session.commit()
            except:
                session.rollback()
                traceback.print_exc()
            finally:
                session.close()
        # print(ccrid)
        return ccrid

    def doCommand(command,commandDict,twitchuserid,requestername,parameters=None):
        minparam = commandDict[command]['minimum']
        maxparam = commandDict[command]['maximum']
        commandtype = commandDict[command]['type']
        commandid = commandDict[command]['commandid']
        if minparam > 0:
            try:
                parametercount = len(parameters)
            except:
                traceback.print_exc()
                parametercount = 0
            finally:
                if parametercount > (maxparam if maxparam is not None else 999) or parametercount < minparam:
                    # helpmsg = requests.get("http://127.0.0.1:5000/api/v2.0//api/v2.0/help/"+command,params=params)
                    message = "The "+command+" command requires "
                    if minparam is not None:
                        message += "at least "+str(minparam).lower()
                        if maxparam is not None:
                            message += " and "
                    if maxparam is not None:
                        message += "at max "+str(maxparam).lower()
                    if minparam is None and maxparam is None:
                        message += "no"
                    message += " parameters. Use '!help "+command+"' for more help."
                    return message,None,commandid,commandtype
        params = {  'twitchuserid':twitchuserid,
                    'requestername':requestername
                    }
        url = "http://127.0.0.1:5000/api/v2.0/"+command+"/"
        if parameters:
            url += ' '.join(parameters)
        # print(twitchuserid)
        # print(requestername)
        if command == 'join' and twitchuserid == 687207983:
            try:
                message = Bot.addClient(requestername)
                returnid = None
            except:
                message = "There was an error joining your channel. Sorry."
        elif command == 'brdybotleave' and twitchuserid == getTwitchID(requestername):
            message,returnid = Bot.removeChannel(twitchuserid)
        else:
            try:
                response = requests.get(url,params=params)
                jsonpackage = json.loads(response.text)
                message = jsonpackage['message']
                returnid = jsonpackage['returnid']
                # print(message)
            except:
                message = "There was an error executing the "+command+" command with the given parameters. Check your parameters and try again. Use '!help "+command+"' for more help."
                returnid = None
                traceback.print_exc()
        return message,returnid,commandid,commandtype

    def getTwitchUserName(twitchuserid):
        session = Session(engine)
        try:
            twitchusername = session.query(TwitchUser.twitchusername).filter(TwitchUser.twitchuserid == twitchuserid).first()
        except:
            session.rollback()
            traceback.print_exc()
        finally:
            session.close()
        # print(twitchusername)
        try:
            return twitchusername[0]
        except:
            return None

    def addClient(requestername):
        session = Session(engine)
        ## Default successflag to false
        successflag = False
        ## fetch twitch userid from twitch api based on requester name
        try:
            twitchuserid = int(requests.get("http://127.0.0.1:5000/api/resource/twitchid/"+requestername).text)
        except:
            return "Error fetching userid for "+requestername+". "+str(traceback.format_exc()).replace('\r',' ').replace('\n',' ').split('Error:')[1]
        #########
        try:
            inserttwitchid = insert(TwitchUser).values(twitchuserid=twitchuserid,twitchusername=requestername.lower())
            insertedtwitchuseridr = session.execute(inserttwitchid).inserted_primary_key
            session.commit()
        except:
            # print("error inserting twitchuser")
            session.rollback()
        finally:
            session.close()
        ## try to add the twitchuserid to the Channel table
        try:
            insertchannelid = insert(Channel).values(twitchuserid=twitchuserid,gameid=10)
            channelidr = session.execute(insertchannelid).inserted_primary_key
            session.commit()
            successflag = True
        except:
            # print("error inserting channel")
            session.rollback()
        finally:
            session.close()
        try:
            insertoperant = insert(ChannelOperant).values(channeltwitchuserid=twitchuserid,operanttwitchuserid=twitchuserid,operanttypeid=1)
            channeloperantidr = session.execute(insertoperant).inserted_primary_key
            session.commit()
        except:
            # print("error inserting operant")
            session.rollback()
        finally:
            session.close()
        try:
            stmt = delete(ChannelDeletion).where(ChannelDeletion.twitchuserid == twitchuserid)
            session.execute(stmt)
            session.commit()
        except:
            # print("error deleting channeldeletion record")
            session.rollback()
        finally:
            session.close()
        ## By this point, the user should have a record in the TwitchUser table and the Channel table and NO record in the ChannelDeletion table.
        ## Let's create a new thread
        try:
            if successflag:
                conn, token, readbuffer, server = Setup.getConnectionVariables()
                commanddict = Setup.getCommandDict()
                operantDict = Setup.getOperants(twitchuserid)
                threading.Thread(target=Bot.ircListen, name=requestername, args=(conn, token, server, readbuffer, requestername, twitchuserid, operantDict, commanddict)).start()
                message = '@'+requestername+" UserID: "+str(twitchuserid)+" - Successfully added you to the userlist. Game was set to FireRed. Note that I store usage data, but I only report on it anonymized or aggregated form."
            else:
                message = '@'+requestername+" UserID: "+str(twitchuserid)+" - Something went wrong or I am in your channel already. If I'm still not there, be sure no words I use (like PP) are banned, and if your channel is set to followers only, please give Mod or VIP privileges."
            return message
        except:
            return "Could not join the channel due to an error on my end. User ID = "+str(twitchuserid)

    def removeChannel(twitchuserid):
        session = Session(engine)
        try:
            stmt = (insert(ChannelDeletion).values(twitchuserid=twitchuserid))
            session.execute(stmt)
        except:
            session.rollback()
            traceback.print_exc()
        finally:
            session.close()
        return {'message':'Successfully removed you from the channel list.','returnid':None}

class Setup():
    def getCommandDict():
        session = Session(engine)
        commands = session.query(Command.commandid,Command.commandname,CommandType.commandtypename,Command.commandminimumparameters,Command.commandmaximumparameters).\
            join(CommandType,Command.commandtypeid == CommandType.commandtypeid,isouter=True).order_by(Command.commandname).all()
        commanddict = {}
        for command in commands:
            commandid,commandname,commandtype,commandmin,commandmax = command
            commanddict[commandname] = {'commandid':commandid,
                                    'type':commandtype,
                                    'minimum':commandmin,
                                    'maximum':commandmax}
        # print(commanddict)
        return commanddict

    def getOperants(twitchuserid):
        # print("getting operants")
        session = Session(engine)
        ChannelTwitch = aliased(TwitchUser)
        OperantTwitch = aliased(TwitchUser)
        # print(twitchuserid)
        try:
            channelusers = session.query(ChannelTwitch.twitchusername,OperantTwitch.twitchusername,OperantTwitch.twitchuserid).\
                            select_from(ChannelOperant).\
                            join(ChannelTwitch,ChannelOperant.channeltwitchuserid == ChannelTwitch.twitchuserid).\
                            join(OperantTwitch,ChannelOperant.operanttwitchuserid == OperantTwitch.twitchuserid).\
                            filter(ChannelTwitch.twitchuserid == twitchuserid).distinct().all()
        except:
            session.rollback()
            traceback.print_exc()
        finally:
            session.close()
        # print(channelusers)
        twitchusername = Bot.getTwitchUserName(twitchuserid)
        operantdict = {twitchuserid:twitchusername}
        for channelname,username,userid in channelusers:
            operantdict[userid] = username.lower()
        # print(operantdict)
        return operantdict

    def getChannels():
        session = Session(engine)
        try:
            deletedchannels = session.query(ChannelDeletion.twitchuserid)
            twitchusers = session.query(Channel.twitchuserid).filter(Channel.twitchuserid.notin_(deletedchannels),Channel.twitchuserid.notin_([687207983])).order_by(Channel.twitchuserid).all()
        except:
            session.rollback()
            traceback.print_exc()
        finally:
            session.close()
        twitchusers = list(twitchusers)
        # print(twitchusers)
        return twitchusers

    def getTwitchIDs():
        session = Session(engine)
        try:
            twitchids = session.query(TwitchUser.twitchuserid).all()
        except:
            traceback.print_exc()
        finally:
            session.close()
        # Setup.updateTwitchNames(twitchids)
        return twitchids

    def updateTwitchNames():
        session = Session(engine)
        # print("Updating twitch ids...")
        secret = config['idfetch']['secret']
        clientid = config['idfetch']['clientid']
        AutParams = {'client_id': clientid,
                'client_secret': secret,
                'grant_type': 'client_credentials'
                }
        authURL = 'https://id.twitch.tv/oauth2/token'
        AutCall = requests.post(url=authURL, params=AutParams) 
        access_token = AutCall.json()['access_token']
        twitchids = session.query(TwitchUser.twitchuserid).all()
        for twitchid in twitchids:
            try:
                url = 'https://api.twitch.tv/helix/users?id='+str(twitchid[0])
                headers = {
                    'Authorization':"Bearer " + access_token,
                    'Client-Id':clientid
                }
                response = requests.get(url,headers=headers)
                twitchusername = response.json()['data'][0]['login']
                # print("Updating "+str(twitchid)+" to "+twitchusername)
                stmt = (update(TwitchUser).where(TwitchUser.twitchuserid == twitchid[0]).values(twitchusername=twitchusername.lower()))
                session.execute(stmt)
            except:
                print("Could not update channelname with twitchid "+str(twitchid))
                traceback.print_exc()
                session.rollback()
            finally:
                session.commit()
        session.close()

    def getConnectionVariables():
        #parameters for twitch irc server
        connection_data = ('irc.chat.twitch.tv', 6667)
        config = configparser.ConfigParser()
        file = "C:/Users/Administrator/brdybot/chatbot.ini"
        config.read(file)
        token = config['chatbot']['token']
        readbuffer = ''
        server = socket.socket()
        return connection_data, token, readbuffer, server
    
if __name__ == "__main__":
    main()