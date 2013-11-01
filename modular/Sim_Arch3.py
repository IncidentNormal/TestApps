'''
Created on Oct 13, 2010

@author: duncantait
'''
# This architecture attempts to separate the disjoint components in ALE based HF comms
# That is; ALE linking is it's own module
# The State Machine of the Station itself is a module
# The traffic generator is a module
# Linked_Tx and Linked_Rx are independent states
# As are ALE Tx and ALE Rx

from SimPy.SimulationRT import *
import numpy as np
import random
import math
import visual as v

class G():
    """Global, simulation settings"""
    num_channels = 10
    num_stations = 5
    max_time = 1000
    
    bitrate = 392
    response_timeout = 2
    linked_timeout = 30
    percentQuitLink = 0.3
    scanning_call_timeout = num_channels*2*response_timeout
    scanning_dwell_time = 2

class Network():
    stations = []
    grid = []
    for i in range(G.num_channels):
        row = []
        for j in range(G.num_stations):
            S = Store(name = j, capacity=1)
            row.append(S)
        grid.append(row)
        
#A framework that contains other class instances that all form parts of the station
class StationContainer():
    def __init__(self,ID):
        self.ID = ID
        self.StateDriver = StateDriver(ID) #Instantiate classes that are parts of the station
        self.TrafficGenerator = TrafficGenerator(ID)
        self.ALE_Transmitting = ALE_Transmitting(ID)
        self.ALE_Receiving = ALE_Receiving(ID)
        self.Linked_Transmitting = Linked_Transmitting(ID)
        self.Linked_Receiving = Linked_Receiving(ID)
    def initComponents(self):
        self.StateDriver.initComponents() #Run various custom constructors for these classes
        self.TrafficGenerator.initComponents()
        self.ALE_Transmitting.initComponents()
        self.ALE_Receiving.initComponents()
        self.Linked_Transmitting.initComponents()
        self.Linked_Receiving.initComponents()
    def activate(self):
        activate(self.StateDriver,self.StateDriver.execute(),at=0.0) #Activate all these classes in SimPy
        activate(self.TrafficGenerator,self.TrafficGenerator.execute(),at=0.0)
        activate(self.ALE_Transmitting,self.ALE_Transmitting.execute(),at=0.0)
        activate(self.ALE_Receiving,self.ALE_Receiving.execute(),at=0.0)
        activate(self.Linked_Transmitting,self.Linked_Transmitting.execute(),at=0.0)
        activate(self.Linked_Receiving,self.Linked_Receiving.execute(),at=0.0)

class StateDriver(Process):
    def __init__(self, ID):
        Process.__init__(self)
        self.ID = ID
        self.State = sState.IDLE
        
        # Start both the LQA_Table and the Scanning channel as random:
        # The process for building the LQA_Table needs to be implemented; by overhearing other's calls.
        self.LQA_Table = np.zeros((G.num_stations, G.num_channels))
        for i in range(len(self.LQA_Table)):
            for j in range(len(self.LQA_Table[i])):
                    self.LQA_Table[i,j] = random.random()
        self.scan_chan = random.randint(0,G.num_channels-1)
        self.scan_chan_color = v.color.white
        
        self.TrafficToSend = Store(capacity='unbounded')
    
    def initComponents(self):
        self.TrafficGenerator = [N.TrafficGenerator for N in Network.stations if N.ID==self.ID][0]
        self.ALE_Transmitting = [N.ALE_Transmitting for N in Network.stations if N.ID==self.ID][0]
        self.ALE_Receiving = [N.ALE_Receiving for N in Network.stations if N.ID==self.ID][0]
        
    def execute(self):
        def forMe(chan):
            for i in chan:
                if i.destination==self.ID: return [i]
        yield hold, self, random.random() # Small wait at start to prevent clashing
        while True:
            print self.ID, 'Scanning channel:', self.scan_chan, now()
            self.scan_chan_color = Vis.grid[self.scan_chan][self.ID].color
            Vis.grid[self.scan_chan][self.ID].color = v.color.blue
            yield (get, self, Network.grid[self.scan_chan][self.ID], forMe),(hold, self, G.scanning_dwell_time)
            if not self.acquired(Network.grid[self.scan_chan][self.ID]):
                Vis.grid[self.scan_chan][self.ID].color = self.scan_chan_color
                if self.scan_chan==G.num_channels-1: self.scan_chan = 0
                else: self.scan_chan+=1
            else:
                print self.ID, 'Received addressed packet', now()
                Vis.grid[self.scan_chan][self.ID].color = v.color.green
                info = self.got[0]
                if info.type == pType.CALL:
                    yield put, self, self.ALE_Receiving.IncomingQ, [info]
                    self.ALE(2)
                    yield passivate, self
                    Vis.grid[self.scan_chan][self.ID].color = self.scan_chan_color
                else: 
                    print self.ID, 'Error 3', now()
                    Vis.grid[self.scan_chan][self.ID].color = self.scan_chan_color
            
            # Doubling as checking if any traffic to send, and a short hardware delay to switch channels
            # Note: The paradigm here is that incoming traffic has priority over outgoing.
            yield(get, self, self.TrafficToSend, 1),(hold, self, 0.0001)
            if self.acquired(self.TrafficToSend):
                info_sending = self.got[0]
                self.ALE(1)
                yield put, self, self.ALE_Transmitting.IncomingQ, [info_sending]
                yield passivate, self
                    
    # These are State changing functions, add any necessary property changes to these
    def ALE(self, Type):
        if Type == 1: self.State = sState.LINKING_Tx
        elif Type == 2: self.State = sState.LINKING_Rx
    def Linked(self, Type):
        if Type == 1: self.State = sState.LINKED_Tx
        if Type == 2: self.State = sState.LINKED_Rx
    def Idle(self):
        self.State = sState.IDLE
        reactivate(self.TrafficGenerator) #When Idle, traffic generation can perhaps occur.
        
class TrafficGenerator(Process):
    def __init__(self, ID):
        Process.__init__(self)
        self.ID = ID
        self.TTW = 30.
    def initComponents(self):
        self.StateDriver = [N.StateDriver for N in Network.stations if N.ID==self.ID][0]
    def execute(self):
        while True:
            #yield hold, self, random.uniform(self.TTW, 2*self.TTW)
            yield hold, self, random.uniform(0, 2*self.TTW)
            print self.ID, 'Generating traffic', now()
            if self.StateDriver.State == sState.IDLE:
                info_sending = self.createCallInfo()
                yield put, self, self.StateDriver.TrafficToSend, [info_sending]
                yield passivate, self
            else: 
                print self.ID, 'Not currently in Idle mode, passivating TrafficGen', now()
                yield passivate, self
                
    def createCallInfo(self):
        info = pInfo()
        while info.destination == self.ID or info.destination == -1:
            info.destination = random.randint(0,G.num_stations-1)
        info.origin = self.ID
        info.type = pType.CALL
        info.size = G.scanning_dwell_time*G.num_channels*G.bitrate
        info.signal_time = G.scanning_dwell_time*G.num_channels
        info.LQA = random.random()
        return info        
        
        
class ALE_Transmitting(Process):
    def __init__(self, ID):
        Process.__init__(self)
        self.ID = ID
        self.IncomingQ = Store(capacity='unbounded')
        self.chan = -1
    def initComponents(self):
        self.StateDriver = [N.StateDriver for N in Network.stations if N.ID==self.ID][0]
        self.Linked_Transmitting = [N.Linked_Transmitting for N in Network.stations if N.ID==self.ID][0]
    def execute(self):
        while True:
            while True:
                yield get, self, self.IncomingQ, 1
                print self.ID, 'ALE_Tx activated', now()
                info = self.got[0]
                
                chanOrder = self.ChannelOrder(info.destination)
                for channel in chanOrder:
                    if Network.grid[self.chan][self.ID].nrBuffered==0:
                        self.chan = channel
                        info.chan = channel # This is now the channel for this entire exchange
                        for each_station in Network.grid[self.chan]:
                            yield put, self, each_station, [info]
                            Vis.grid[self.chan][each_station.name].color = v.color.yellow
                            print self.ID, 'Put CALL on channel', self.chan, 'for Station', each_station.name, '[',info.destination,']', now()
                        break
                yield hold, self, info.signal_time
                print self.ID, 'Finished Scanning Call', now()
                
                for each_station in Network.grid[self.chan]:
                    if each_station.nrBuffered==1: # Should have been taken by destination
                        yield get, self, each_station, 1
                        Vis.grid[self.chan][each_station.name].color = v.color.white
                        print self.ID, 'Got CALL off channel', self.chan, 'for Station', each_station.name, now()
                        
                yield hold, self, 0.0001
                
                yield (get, self, Network.grid[self.chan][self.ID], 1),(hold, self, G.response_timeout)
                if not self.acquired(Network.grid[self.chan][self.ID]):
                    print self.ID, 'Response not acquired, back to Idle', now()
                    self.StateDriver.Idle()
                    reactivate(self.StateDriver)
                    break
                
                print self.ID, 'Got Response', now()
                info = self.got[0] # Response off channel
                yield hold, self, info.signal_time
                
                ack_info = self.createAckInfo(info) # Create ack
                
                for each_station in Network.grid[self.chan]:
                    if each_station.nrBuffered == 0:
                        yield put, self, each_station, [ack_info]
                        Vis.grid[self.chan][each_station.name].color = v.color.red
                        print self.ID, 'Put ACK on channel', self.chan, 'for Station', each_station.name, now()
                    else: print self.ID, 'Error 1', now()
                
                yield hold, self, ack_info.signal_time
                print self.ID, 'Finished ACK s Sending', now()
                
                for each_station in Network.grid[self.chan]:
                    Vis.grid[self.chan][each_station.name].color = v.color.white
                    if each_station.nrBuffered==1:
                        yield get, self, each_station, 1
                        print self.ID, 'Got ACK from channel', self.chan, 'for Station', each_station.name, now()
                        
                self.StateDriver.Linked(1)     
                yield put, self, self.Linked_Transmitting.activateQ, [info]
                print self.ID, 'Now LINKED: Passing responsibility to Linked_Tx', now()
    
    def ChannelOrder(self,station): 
        #sorts best channels best-worst in terms of LQA and returns an array
        ordered = self.StateDriver.LQA_Table[station,:].argsort()
        return ordered[::-1] #reverse order of array
    
    def createAckInfo(self,info):
        info.type = pType.ACK
        dest = info.destination
        info.destination = info.origin
        info.origin = dest
        info.LQA = Environment.LQA_Reading(self.ID, info.destination)
        info.signal_time = (info.size/G.bitrate)*(1./info.LQA)

        return info
    
class ALE_Receiving(Process):
    def __init__(self, ID):
        Process.__init__(self)
        self.ID = ID
        self.nameLen = random.randint(1,5)*3 #ALE name format is 3, 6, 9, 12 or 15 chars.
        self.IncomingQ = Store(capacity='unbounded')
        self.chan = -1
    def initComponents(self):
        self.StateDriver = [N.StateDriver for N in Network.stations if N.ID==self.ID][0]
        self.Linked_Receiving = [N.Linked_Receiving for N in Network.stations if N.ID==self.ID][0]
    def execute(self):
        while True:
            while True:
                yield get, self, self.IncomingQ, 1
                print self.ID, 'ALE Rx activated', now()
                
                info = self.got[0]
                self.chan = info.chan
                response_info = self.createResponseInfo(info)
                
                for each_station in Network.grid[self.chan]:
                        yield (put, self, each_station, [response_info]),(hold, self, G.scanning_call_timeout)
                        Vis.grid[self.chan][each_station.name].color = v.color.orange
                        print self.ID, 'Put RESPONSE on channel', self.chan, 'for Station', each_station.name, now()
                        if not self.stored:
                            print self.ID, 'Error 2', now()
                
                yield hold, self, response_info.signal_time
                print self.ID, 'Finished Response sending', now()
                
                for each_station in Network.grid[self.chan]:
                    if each_station.nrBuffered==1:
                        yield get, self, each_station, 1
                        Vis.grid[self.chan][each_station.name].color = v.color.white
                        print self.ID, 'Got RESPONSE off channel', self.chan, 'for Station', each_station.name, now()
                        # No need to read this 'Response' to check?
                yield hold, self, 0.0001
                
                yield (get, self, Network.grid[self.chan][self.ID], 1),(hold, self, G.response_timeout)
                if not self.acquired(Network.grid[self.chan][self.ID]):
                    print self.ID, 'ACK not acquired, back to Idle', now()
                    self.StateDriver.Idle()
                    reactivate(self.StateDriver)
                    break
                
                print self.ID, 'Got ACK', now()
                info = self.got[0]
                yield hold, self, info.signal_time
                
                self.StateDriver.Linked(2)
                yield put, self, self.Linked_Receiving.activateQ, [info]
                print self.ID, 'Now LINKED: Passing responsibility to Linked_Rx', now()

    def createResponseInfo(self, info):
        info.type = pType.RESPONSE
        dest = info.destination
        info.destination = info.origin
        info.origin = dest
        info.LQA = Environment.LQA_Reading(self.ID, info.destination)
        info.size = math.ceil((self.nameLen)/3)*24 
        info.signal_time = (info.size/G.bitrate)*(1./info.LQA)
        return info
    
class Linked_Transmitting(Process):
    def __init__(self, ID):
        Process.__init__(self)
        self.ID = ID
        self.activateQ = Store(capacity='unbounded')
        self.percentOdds = (0.5, 0.65, 0.8, 0.9, 1.0) #AMD, DTM_b, DTM_e, DBM_b, DBM_e
        self.chan = -1
    def initComponents(self):
        self.StateDriver = [N.StateDriver for N in Network.stations if N.ID==self.ID][0]
        self.Linked_Receiving = [N.Linked_Receiving for N in Network.stations if N.ID==self.ID][0]
        
    def execute(self):
        while True:
            while True:
                yield get, self, self.activateQ, 1
                print self.ID, 'Linked Tx activated', now()
                
                yield hold, self, random.uniform(0,10)
                
                info = self.got[0]
                self.chan = info.chan
                
                info_send = self.createTrafficInfo(info)
                
                for each_station in Network.grid[self.chan]:
                    if each_station.nrBuffered==0:
                        yield put, self, each_station, [info_send]
                        Vis.grid[self.chan][each_station.name].color = v.color.magenta
                        print self.ID, 'Put DATA on channel', self.chan, 'for Station', each_station.name, 'Time:', info_send.signal_time, now()
                    else: print self.ID, 'Error 4', now()
                    
                yield hold, self, info_send.signal_time
                print self.ID, 'Data Sent', now()
                
                for each_station in Network.grid[self.chan]:
                    Vis.grid[self.chan][each_station.name].color = v.color.white
                    if each_station.nrBuffered==1: # Should have been taken by destination
                        yield get, self, each_station, 1
                        print self.ID, 'Got DATA off channel', self.chan, 'for Station', each_station.name, now()
                
                if random.random() < G.percentQuitLink:
                    print self.ID, 'Decided to Terminate link', now()
                    self.StateDriver.Idle()
                    reactivate(self.StateDriver)
                    break
                else:
                    print self.ID, 'Decided to remain online, changing responsibility to Linked Rx', now()
                    self.StateDriver.Linked(2)
                    yield put, self, self.Linked_Receiving.activateQ, [info]

    def createTrafficInfo(self, info):
        info.type = pType.DATA
        
        r = random.random()
        if r < self.percentOdds[0]: info.size += random.randint(1,30)*24 #AMD
        elif r < self.percentOdds[1]: info.size += random.randint(1,93)*7 #DTM Basic
        elif r < self.percentOdds[2]: info.size += random.randint(3,1053)*7 +24 #DTM Extended
        elif r < self.percentOdds[3]: info.size += random.randint(1,81)*7 + 16 #DBM Basic
        elif r < self.percentOdds[4]: info.size += random.randint(82,37260)*7 + 16 + 24 #DBM Extended
        
        info.signal_time = (G.bitrate*info.size)*(1./info.LQA)
        
        dest = info.destination
        info.destination = info.origin
        info.origin = dest
        
        return info
        
class Linked_Receiving(Process):
    def __init__(self, ID):
        Process.__init__(self)
        self.ID = ID
        self.activateQ = Store(capacity='unbounded')
        self.chan = -1
    def initComponents(self):
        self.StateDriver = [N.StateDriver for N in Network.stations if N.ID==self.ID][0]
        self.Linked_Transmitting = [N.Linked_Transmitting for N in Network.stations if N.ID==self.ID][0]
        
    def execute(self):
        while True:
            while True:
                yield get, self, self.activateQ, 1
                print self.ID, 'Linked Rx activated', now()
                info = self.got[0]
                self.chan = info.chan
                
                yield (get, self, Network.grid[self.chan][self.ID], 1),(hold, self, G.linked_timeout)
                if not self.acquired(Network.grid[self.chan][self.ID]):
                    print self.ID, 'Linked mode timed out, back to Idle', now()
                    self.StateDriver.Idle()
                    reactivate(self.StateDriver)
                    break
                else:
                    print self.ID, 'Start of Data received', now()
                    info_channel = self.got[0] #info just received off channel
                    yield hold, self, info_channel.signal_time
                    print self.ID, 'End of Data received', now()
                    if random.random() < G.percentQuitLink:
                        print self.ID, 'Decided to terminate link, back to Idle', now()
                        self.StateDriver.Idle()
                        reactivate(self.StateDriver)
                        break
                    else:
                        print self.ID, 'Decided to remain online and reply, changing responsibility to Linked Rx', now()
                        self.StateDriver.Linked(1)
                        yield put, self, self.Linked_Transmitting.activateQ, [info_channel]
                        break
                        
class Environment(Process):
    def __init__(self):
        Process.__init__(self)
        self.atomsQ = 0.5
    def execute(self):
        while True:
            yield hold, self, random.uniform(1,5)
            self.atmosQ = math.sin(now())
        #sin wave with now()
    def LQA_Reading(self, selfID, destID):
        #This algorithm has potential to be highly detailed
        #Parameters needed: positions of 2 stations --> distance
        #Ionospheric conditions
        #Time of day, sunspot cycle.
        #For now, stations closer in numbers are better connected.
        #This should be in Tx as it needs to eventually interface with an Environment process
        distance = abs(selfID - destID)/G.num_stations
        LQA = random.normalvariate(100-(distance*100),4)
        if LQA > 1: LQA=1
        if LQA < 0: LQA=0
        return LQA  
    
class Vis():
    def __init__(self):      
        x = 0
        y = 0
        z = 0
        
        self.grid = []
        for i in range(G.num_channels):
            row = []
            for j in range(G.num_stations):
                square = v.box(pos=(x,y,z), length = 0.9, height = 0.9, width = 0.01)
                row.append(square)
                y += 1
            self.grid.append(row)
            y = 0
            x += 1
    
class pInfo():
    origin = -1
    destination = -1
    type = -1
    chan = -1
    size = -1
    signal_time = -1
    LQA = -1

class pType():
    CALL = 1
    RESPONSE = 2
    ACK = 3
    DATA = 4

class sState():
    IDLE = 1
    LINKING_Tx = 2
    LINKING_Rx = 3
    LINKED_Tx = 4
    LINKED_Rx = 5

initialize()

Environment = Environment()
activate(Environment,Environment.execute(),at=0.0)

Network.stations = [StationContainer(i) for i in range(G.num_stations)]
for N in Network.stations:
    N.initComponents()
    N.activate()
    
Vis = Vis()

simulate(until=G.max_time, real_time=True, rel_speed=1)
print '** Fin'
            
            