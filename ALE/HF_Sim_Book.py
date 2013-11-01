'''
Created on Sep 15, 2010

@author: duncantait
'''
from SimPy.Simulation import *
import numpy as np
import random
import math

class G():
    #Settings for HF Stations
    num_channels = 18
    num_stations = 10
    
class Network():
    stations = []
    
class Medium():
    def __init__(self):
        self.channels = []
        for i in range(G.num_channels):
            S = Store(name=i,capacity=1)
            self.channels.append(S)
        
class StationContainer():
    def __init__(self,ID):
        self.ID = ID
        self.Operator = Operator(ID)
        self.StationSettings = StationSettings(ID)
        self.Scanning = Scanning(ID)
        self.Tx = Tx(ID)
    def initComponents(self):
        self.Operator.initCounterparts()
        self.StationSettings.initCounterparts()
        self.Scanning.initCounterparts()
        self.Tx.initCounterparts()
    def activate(self):
        activate(self.Operator,self.Operator.sendMessage(),at=0.0)
        activate(self.StationSettings,self.StationSettings.sounding(),at=0.0)
        activate(self.Scanning,self.Scanning.scan(),at=0.0)
        activate(self.Tx,self.Tx.sending(),at=0.0)

class Operator(Process):
    def __init__(self, ID):
        Process.__init__(self)
        self.ID = ID
    def initComponents(self):
        self.StationSettings = [N.StationSettings for N in Network.stations if N.ID==self.ID][0]
    def sendMessage(self):
        while True:
            #every so often operator wants to send a message: adds to queue.
            yield hold, self, random.uniform(0,1200)
            #Create a Message of type 'CALL'
            frameInfo = frameDetails(self.ID,self.decideDestination(),0,fType.CALL,False,-1,-1)
            frameInfo.channels = self.ChannelOrder(frameInfo.destination)
            yield put,self,self.Tx.sendQ,[frameInfo]
            yield hold, self, random.uniform(0,1200)
    def decideDestination(self):
        while True:
            dest = random.randint(0,G.num_channels-1)
            if dest != self.ID:
                return dest
    def ChannelOrder(self,channel=-1,station=-1):
        #sorts best channels best-worst
        if channel==-1:
            ordered = self.StationSettings.channelBER[station,:].argsort()
            return ordered[::-1] #reverse order of array
        if station==-1:
            ordered = self.StationSettings.channelBER[:,channel].argsort()
            return ordered[::-1]

class StationSettings(Process):
    def __init__(self, ID):
        Process.__init__(self)
        self.ID = ID
        self.state = sState.SCANNING #can be scanning, linking or linked.
        self.sending = False
        
        self.channelBER = np.zeros((G.num_channels,G.num_stations)) #LQA: Link Quality Analysis

        self.timeout = 2 #current timeout counter for linking/linked mode, if this hits zero, go back to scanning        
        self.Td = 2 #dwell time per channel
        self.Twce = 2 #wait for calling cycle to end
        self.Twr = 2
        self.minLQA = 0.2
        
        self.bitrate = 392
        self.hardwareTime = 20 #e.g. power up/down time, modulation/demodulation, encoding/decoding, crypto in ms.
                                #tune up/down time. Included in Twrt (wait for response and tune time)
        
    def Sounding(self):
        while True:
            yield hold, self, random.uniform(0,120)
            #Sound
            yield hold, self, 1800
    

class Scanning(Process):
    #Is HF ALWAYS scanning? No, either scanning, linking or linked
    def __init__(self, ID):
        self.ID = ID
        Process.__init__(self)
        self.currentChannel = 0
    def initComponents(self):
        self.StationSettings = [N.StationSettings for N in Network.stations if N.ID==self.ID][0]
        self.Tx = [N.Tx for N in Network.stations if N.ID==self.ID][0]
    def scan(self):
        while True:   
            #Different responses depending on mode. 
            #Rules: cannot receive while sending <-----------------
            #Otherwise, packets will be interpreted as to the mode the station is in.
            channel = Medium.channels[self.currentChannel]
            yield (get,self,channel,1),(hold,self,self.StationSettings.timeout)
            if self.acquired(channel):
                signal = self.got
                yield put, self , channel, signal
                frameInfo = self.decode(signal) #This implies picking up the signal frame by frame from the channel
                if (frameInfo.LQA > self.StationSettings.minLQA) and (frameInfo.destination==self.ID):
                    yield (put,self,channel,['PH:'+str(self.ID)]),(hold,self,self.StationSettings.Twce)
                    if self.stored(channel):
                        yield get,self,channel,1 #Yank sniffer packet back off channel.
                        if frameInfo.type== fType.CALL:
                            if self.StationSettings.state==sState.SCANNING: 
                                yield put,self,self.Tx.sendQ,[frameInfo]
                                self.StationSettings.state=sState.LINKING
                                yield waitevent,self,self.Tx.sE
                        if frameInfo.type== fType.RESPONSE:
                            if self.StationSettings.state==sState.LINKING:
                                yield put,self,self.Tx.sendQ,[frameInfo]
                                yield waitevent,self,self.Tx.sE
                        if frameInfo.type== fType.ACK:
                            if self.StationSettings.state==sState.LINKING:
                                yield put,self,self.Tx.sendQ,[frameInfo]
                                self.StationSettings.state=sState.LINKED
                                yield waitevent,self,self.Tx.sE
                        if frameInfo.type== fType.QUICK_ID:
                            if (self.StationSettings.state==sState.SCANNING or sState.LINKED) and (frameInfo.terminate==False):
                                'I dont think you can have a QUICK ID out of the blue, and it doesnt need a reply...'
                                #yield put,self,self.Tx.sendQ,[frameInfo]
                                #yield waitevent,self,self.Tx.sE
                            elif frameInfo.terminate==True:
                                self.StationSettings.state=sState.SCANNING
                        if frameInfo.type== fType.MSG:
                            if self.StationSettings.state== sState.LINKED and frameInfo.terminate==False:
                                'again, why the reply? just keep channel open...'
                            elif frameInfo.terminate==True:
                                self.StationSettings.state=sState.SCANNING
                                #yield put,self,self.Tx.sendQ,[frameInfo]
                                #yield waitevent,self,self.Tx.sE
                        else:
                            print 'Invalid Packet'
                            self.StationSettings.state=sState.SCANNING
                    else:
                        print 'Timed out'
                        self.StationSettings.state=sState.SCANNING  
                else:
                    'Frame unsuitable: Continue Scan'
                    self.StationSettings.state=sState.SCANNING
            else:
                'Channel Empty: Continue Scan'
                self.StationSettings.state=sState.SCANNING
            if self.StationSettings.state==sState.SCANNING: 
                if self.currentChannel==G.num_channels-1: 
                    self.currentChannel = 0
                else:
                    self.currentChannel+=1
                        
    def decode(self,frameInfo):
        #Return a packet useable to send straightaway. All data is known to achieve this.
        
        returnInfo = self.convertReply(frameInfo)
        returnInfo = self.responseSize(returnInfo)
        returnInfo = self.calculate_LQA(returnInfo)
        returnInfo.channels = self.currentChannel
        #Messages and Acks/Responses always have to be on the same channel as before... which is all
        #That is dealt with in 'Scanning'  

        returnInfo.terminate = False #This needs to be somewhat randomised, but for now this will do.
        return returnInfo
        #If LQA below certain amount, reject in PEM above
    
    def convertReply(self, frameInfo): #Convert incoming packet into it's appropriate output type.
        returnInfo = frameInfo
        if frameInfo.type==fType.OUT:
            returnInfo.type= fType.CALL
        if frameInfo.type==fType.CALL:
            returnInfo.origin = frameInfo.destination
            returnInfo.destination = frameInfo.origin
            returnInfo.type = fType.RESPONSE
        elif frameInfo.type == fType.RESPONSE:
            returnInfo.type = fType.ACK
            returnInfo.origin = frameInfo.destination
            returnInfo.destination = frameInfo.origin
        elif frameInfo.type == fType.ACK:
            returnInfo.type = fType.MSG
            returnInfo.origin = frameInfo.destination
            returnInfo.destination = frameInfo.origin
            returnInfo = self.decidePayload(returnInfo) #Messages get a payload.   
        return returnInfo
        
    def responseSize(self,frameInfo):
        returnInfo = frameInfo
        destination = self.get_address(frameInfo.destination)
        origin = self.get_address(frameInfo.origin)
        if returnInfo.type == fType.RESPONSE or fType.ACK:
            returnInfo.size += len(destination)*2*49 + len(origin)*49 #each word is 49bits after encoding
        return returnInfo
    
    def decidePayload(self, frameInfo):
        #Data Block Mode: Basic mode 0-572 bits, Extended 572-262820 bits (+18 each for cyclic redundancy check),
        #Extended data blocks are 588 bits (49*12 + 16 FCS) Basic are 49 bits. note 572 bits = 81 ASCII chars.
        #Other modes are AMD (auto msg display) and DTM (data text msg), but less efficient for larger data
        #Upper bound performance = 375 * (588/1176) = 187.5bps
        #Also, many many CMD words that do many things. (Important one being LQA transfer)
        
        #See pages around 231, need to add CMD and extra necessary words to these data_blocks etc.
        
        returnInfo = frameInfo
        mode = random.randint(0,10)
        if mode==0 or mode==1:
            #basic data block mode
            returnInfo.size += random.randint(1,81)*7 + 16
        elif mode==2:
            #extended data block mode (least likely)
            returnInfo.size += random.randint(82,37260)*7 + 16
        elif mode==3 or mode==4 or mode==5 or mode==6:
            #CMD message
            returnInfo.size += 24 #1 extra word
        elif mode==7 or mode==8 or mode==9 or mode==10:
            returnInfo.size += 0 #null
        return returnInfo
    
    def get_address(self, address):
        words = []
        div = math.floor(len(address)/3)
        rem = len(address)%3
        i = 0
        rep = True
        for word in range(div):
            words.append(address[i:i+3])
            if rep==False and i >= 3: words.append('DATA')
            else: words.append('REP')
            rep = not rep
            i += 3
        if rem>0:
            final_word = address[i:i+rem] + '@'*(3-rem)
            words.append(final_word)
        return words                                                
#
#Instead of 'crafting messages' and spending ages about it. Merely use the functions written already
#(for making the words etc.) to calculate the SIZE of the signal, and make this a parameter of the
#frameInfo that sits on the channel. This can then be used to say HOW LONG it stays on the channel, and
#how long the receiver must receive for (although this doesn't matter too much as the receiver is effectively
#locked in one state once it enters linking/linked mode (line 101). This solves Response/Ack problem too
#
class Tx(Process):
    def __init__(self,ID):
        self.ID = ID
        Process.__init__(self)
        self.sendQ = Store(name=ID,capacity='unbounded')
        self.sE = SimEvent(name='TxSent')
    def initComponents(self):
        self.StationSettings = [N.StationSettings for N in Network.stations if N.ID==self.ID][0]
    def sending(self):
        while True:
            yield get,self,self.sendQ,1
            frameInfo = self.got[0] #data in form frameDetails()
            signal_time = frameInfo.size*self.StationSettings.bitrate + self.StationSettings.hardwareTime
            frameInfo.LQA = self.calculate_LQA(frameInfo.destination)

            unSent = True
            for chanNum in frameInfo.channels:
                if unSent:
                    channel = Medium.channels(chanNum)
                    if channel.nrBuffered==0:
                        print 'Channel', chanNum, 'free, occupying..'
                        yield put,self,channel,[frameInfo]
                        unSent = False
                        if self.type == fType.CALL: #call cycle
                            yield hold,self,2*self.StationSettings.Td*G.num_stations
                            #THIS NEEDS ATTENTION AS IT IS DIFFERENT FROM THE REST - This could actually be ok... just needs some additions for propagation time
                            #could use 'signal_time' from 'size' but kind of backwards...
                            if self.interrupted():
                                print 'Collision occurred, station:', self.ID
                        else:
                            yield hold,self,signal_time #How long does it take to get there?!
                            if self.interrupted():
                                print 'Collision occurred, station:', self.ID
                        yield get,self,channel,1 #Message delivered.
                        #UNPASSIVATE SCANNING PEM
                        self.sE.signal(frameInfo)
                        self.StationSettings.timeout = self.StationSettings.Twr 
                        #INVESTIGATE THIS TIMEOUT VARIABLE, WHAT DOES IT ACTUALLY DO? SEEM TO REMEMBER IT BEING A GOOD IDEA.
                        
    def calculate_LQA(self, destination):
        #This algorithm has potential to be highly detailed
        #Parameters needed: positions of 2 stations --> distance
        #Ionospheric conditions
        #Time of day, sunspot cycle.
        #For now, stations closer in numbers are better connected.
        #This should be in Rx as it needs to eventually interface with an Environment process
        distance = abs(self.ID - destination)/G.num_stations
        LQA = random.normalvariate(100-(distance*100),4)
        if LQA > 1: LQA=1
        if LQA < 0: LQA=0
    
##CATER FOR IF OUTGOING FRAME FAILS AND NEEDS TO REPEAT USING A DIFFERENT CHANNEL! (extra parameter?)
#class OutgoingFrame(Process):
#    def __init__(self,ID,frameInfo,frame):
#        #channels is a list of channels, for a response or single channel call, it will only contain 1 entry
#        Process.__init__(self)
#        self.ID = ID
#        self.destination = frameInfo.destination 
#        self.channelOrder = frameInfo.channels
#        self.type = frameInfo.type
#        self.frame = frame
#    def initComponents(self):
#        self.StationSettings = [N.StationSettings for N in Network.stations if N.ID==self.ID][0]
#        self.Tx = [N.Tx for N in Network.stations if N.ID==self.ID][0]
#    def go(self):
#        unSent = True
#        for chanNum in self.channelOrder:
#            if unSent:
#                channel = Medium.channels(chanNum)
#                if channel.nrBuffered==0:
#                    print 'Channel', chanNum, 'free, occupying..'
#                    yield put,self,channel,[self.frame]
#                    unSent = False
#                    if self.type == fType.OUT: #call cycle
#                        yield hold,self,2*self.StationSettings.Td*G.num_stations
#                        if self.interrupted():
#                            print 'Collision occurred, station:', self.ID
#                    if self.type == fType.RESPONSE:
#                        yield hold,self,self.StationSettings.Twr #How long does it take to get there?!
#                        if self.interrupted():
#                            print 'Collision occurred, station:', self.ID
#                        yield get,self,channel,1 #Message delivered.
#                        #UNPASSIVATE SCANNING PEM
#                        self.StationSettings.timeout = self.StationSettings.Twr    
                
class frameDetails():
    def __init__(self,origin,destination,size,type,terminate,channels,LQA):
        self.origin = origin
        self.destination = destination
        self.size = size
        self.type = type
        self.terminate = terminate
        self.channels = channels
        self.LQA = LQA
        
class fType():
    MSG = 1
    QUICK_ID = 2
    CALL = 3
    RESPONSE = 4
    ACK = 5
    OUT = 6
    
class sState():
    SCANNING = 1
    LINKING = 2
    LINKED = 3

initialize()

Medium = Medium()

Network.stations = [StationContainer(i) for i in range(G.num_stations)]
for N in Network.stations:
    N.initComponents()
    N.activate()
simulate(until=G.max_time)
            
            