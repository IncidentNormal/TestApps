'''
Created on Oct 28, 2010

@author: duncantait
'''
#This module contains (what were previously) the ALE, MHS and Environment modules
#Due to importing issues between modules (circular dependencies!) it is much simpler and easier to debug
#if all these classes are held in the same module. 
#Conscious effort should be made to keep these 3 parts separate.

from SimPy.SimulationTrace import *
import random
import numpy as np

##########################     ALE     ###############################

class ALE_Mode(): #Can only be in 1 of these 4 modes
    Scan = 1
    LinkingRx = 2
    LinkingTx = 3
    Linked = 4  

class ALE_Controller(Process):
    def __init__(self,ID):
        Process.__init__(self, name=str(ID)+':ALE Controller')
        self.ID = ID
        self.Mode = ALE_Mode.Scan
        
        self.LQA_Table = np.zeros((G.num_nodes, G.num_chans))
        
#        self.LQA_Table = [] #A table of dimensions nodes/channels to store personal last recorded LQA values
#        for i in range(Env.G.num_nodes):
#            row = []
#            for j in range(Env.G.num_chans):
#                row.append(random.random())
#            self.LQA_Table.append(row)
        
        self.MHS_Incoming = SimEvent(name='MHS Incoming')
        self.MHS_Finished = SimEvent(name='MHS Finished')
        self.Scanning_Call = SimEvent(name='Call Incoming')
        self.Linked = SimEvent(name='Now Linked')
        self.TimedOut = SimEvent(name='Timed Out')
    
    def connectNode(self):
        self.Scanning = [N.Scanning for N in Environment.nodes if N.ID==self.ID][0]
        self.MHS_Controller = [N.MHS_Controller for N in Environment.nodes if N.ID==self.ID][0]
        
    def execute(self):
        while True:
            #always scanning for MHS, but only interpret if in Scanning mode (ie. not Linking)
            yield waitevent, self, [self.MHS_Incoming, self.MHS_Finished, self.Scanning_Call, self.Linked, self.TimedOut]
            if self.eventsFired[0] == self.MHS_Incoming and self.Mode == ALE_Mode.Scan:
                print self.ID, '[ALE] rec. msg to send from MHS: change ALE Mode Scanning->LinkingTx, create Linking Tx Process'
                self.Mode = ALE_Mode.LinkingTx
                linking_data = self.eventsFired[0].signalparam
                L_Tx = Linking_Tx(self.ID, linking_data)
                activate(L_Tx, L_Tx.execute())
            elif self.eventsFired[0] == self.Scanning_Call and self.Mode == ALE_Mode.Scan:
                print self.ID, '[ALE] rec. inc. call from Scanning: change ALE Mode Scanning->LinkingRx, create Linking Rx Process'
                self.Mode = ALE_Mode.LinkingRx
                linking_data = self.eventsFired[0].signalparam
                self.MHS_Controller.ALE_Incoming.signal(linking_data)
                L_Rx = Linking_Rx(self.ID, linking_data)
                activate(L_Rx, L_Rx.execute())
            elif self.eventsFired[0] == self.Linked and (self.Mode == ALE_Mode.LinkingRx or self.Mode == ALE_Mode.LinkingTx):
                print self.ID, '[ALE] rec. ALE linked signal: change ALE Mode LinkingRx/Tx->Linked, send linked signal to MHS'
                self.Mode = ALE_Mode.Linked
                linked_data = self.eventsFired[0].signalparam
                self.MHS_Controller.ALE_Linked.signal(linked_data)
                '...passivate' #This one is actually definitely needed (to prevent ALE superclass doing anything)
            elif self.eventsFired[0] == self.TimedOut and not self.Mode == ALE_Mode.Scan:
                print self.ID, '[ALE] rec. ALE TimedOut signal: change ALE Mode', self.Mode,'->Scanning, reactivate Scanning process'
                self.Mode = ALE_Mode.Scan
                reactivate(self.Scanning)
            elif self.eventsFired[0] == self.MHS_Finished and self.Mode == ALE_Mode.Linked:
                print self.ID, '[ALE] reset ALE Mode to Scan, reactivate Scanning process'
                self.Mode = ALE_Mode.Scan
                reactivate(self.Scanning)
            else:
                print '[ALE] Shouldnt be here (if we keep the passivates in the above if/else clauses)'
    
class Scanning(Process):
    def __init__(self,ID):
        Process.__init__(self, name=str(ID)+':Scanning')
        self.ID = ID
        self.current_channel = random.randint(0,G.num_chans-1)
        
    def connectNode(self):
        self.ALE_Controller = [N.ALE_Controller for N in Environment.nodes if N.ID==self.ID][0]

    def execute(self):
        def forMe(chan): #Filter function for Stores (channels).
            for i in chan:
                if i.destination==self.ID: return [i]
        yield hold, self, random.random() #Make sure all Scans don't start at exactly the same time to prevent ties
        while True:
            yield (get, self, Environment.grid[self.current_channel][self.ID], forMe),(hold, self, G.dwell_time)
            if not self.acquired(Environment.grid[self.current_channel][self.ID]): #Nothing to report
                if self.current_channel==G.num_chans-1: self.current_channel = 0 #Increment channel or set to 0 if at end of cycle
                else: self.current_channel+=1
            else: #Received something
                info = self.got[0]
                if info.type == dataType.CALL and self.ALE_Controller.Mode == ALE_Mode.Scan: #Check it hasn't changed mode since start of dwell time
                    self.ALE_Controller.Scanning_Call.signal(info)
                    yield passivate, self
                else:
                    pass
            if self.ALE_Controller.Mode != ALE_Mode.Scan: #At end of channel scan, check if still in Scanning mode
                yield passivate, self

class Linking_Tx(Process):
    def __init__(self,ID,linking_data):
        Process.__init__(self, name=str(ID)+':Linking Tx')
        self.ID = ID
        self.linking_data = linking_data
        
        self.ALE_Controller = [N.ALE_Controller for N in Environment.nodes if N.ID==self.ID][0]
        
    def execute(self):
        call = self.linking_data
        chanOrder = self.channelOrder(self.linking_data.destination) #choose best channels in order of LQA
        for channel in chanOrder: #try each one in turn
            if Environment.grid[channel][self.ID].nrBuffered==0:
                call.chan = channel
                print self.ID, '[ALE L_Tx] Linking process activated to', call.destination
                call = Environment.updateLQA(call)
                for each_station in Environment.grid[call.chan]: #filling channel with call
                    yield put, self, each_station, [call]
                break
        yield hold, self, call.signal_time
        for each_station in Environment.grid[call.chan]:
            if each_station.nrBuffered==1: # Should have been taken by destination
                yield get, self, each_station, 1
        yield hold, self, 0.0001
        yield (get, self, Environment.grid[call.chan][self.ID], 1),(hold, self, G.response_timeout)
        if not self.acquired(Environment.grid[call.chan][self.ID]):
            self.ALE_Controller.TimedOut.signal()
        else:
            linking_data = self.got[0] # Response from channel
            yield hold, self, linking_data.signal_time
            F = ALE_Functions()
            ack_data = F.ackResponseSwap(linking_data) 
            for each_station in Environment.grid[ack_data.chan]:
                if each_station.nrBuffered == 0:
                    yield put, self, each_station, [ack_data]
                else: pass #Shouldn't really be here
            yield hold, self, ack_data.signal_time
            for each_station in Environment.grid[ack_data.chan]:
                if each_station.nrBuffered==1:
                    yield get, self, each_station, 1              
            self.ALE_Controller.Linked.signal(ack_data)
        
    def channelOrder(self,node): 
        #sorts best channels best-worst in terms of LQA and returns an array
        ordered = self.ALE_Controller.LQA_Table[node,:].argsort()
        return ordered[::-1] #reverse order of array
            
class Linking_Rx(Process):
    def __init__(self,ID,linking_data):
        Process.__init__(self, name=str(ID)+':Linking Rx')
        self.ID = ID
        self.linking_data = linking_data

        self.ALE_Controller = [N.ALE_Controller for N in Environment.nodes if N.ID==self.ID][0]
        
    def execute(self):
        #Do Rx Handshaking here
        F = ALE_Functions()
        response = F.ackResponseSwap(self.linking_data)
        print self.ID, '[ALE L_Rx] Linking process activated in response to', response.destination 
        for each_station in Environment.grid[self.linking_data.chan]:
            yield (put, self, each_station, [response]),(hold, self, G.scanning_call_timeout)
            if not self.stored:
                print 'erroneous'
                pass #But shouldn't really be here?
        yield hold, self, response.signal_time #--------------Hold for signal_time
        for each_station in Environment.grid[self.linking_data.chan]:
            if each_station.nrBuffered==1:
                yield get, self, each_station, 1
        yield hold, self, 0.0001 #-----------------Hold for nominal time to prevent SimPy tie
        yield (get, self, Environment.grid[self.linking_data.chan][self.ID], 1),(hold, self, G.response_timeout)
        if not self.acquired(Environment.grid[self.linking_data.chan][self.ID]): #Did not receive ACK
            self.ALE_Controller.TimedOut.signal()
        else: #Received ACK
            linking_data = self.got[0]
            yield hold, self, linking_data.signal_time
            self.ALE_Controller.Linked.signal(linking_data)
            
class ALE_Functions():
    def ackResponseSwap(self,data):
        returnData = data
        returnData.origin = data.destination
        returnData.destination = data.origin
        Environment.updateLQA(returnData)
        return returnData      
#    def updateLQA(self,data):
#        returnData = data    
#        returnData.LQA = Env.Environment.LQA_grid[ALE.Controller.ID][returnData.chan][returnData.destination]
#        returnData.signal_time = returnData.size*Env.G.max_bitrate*(1./returnData.LQA)
#        return returnData
        
######################################################################
######################################################################
##########################     MHS     ###############################
######################################################################
######################################################################

        
class MHS_Mode(): #Can only be in 1 of these 3 modes
    CallGen = 1 #Generating calls from an Idle (Scanning) state
    InCall = 2
    TrafficGen = 3 #Generating Traffic once in a Linked state
    Receving = 4 #Receiving Traffic while in a Linked state

class MHS_Controller(Process):
    def __init__(self,ID):
        Process.__init__(self, name=str(ID)+':MHS Controller')
        self.ID = ID
        self.Mode = MHS_Mode.CallGen
        
        self.ALE_Incoming = SimEvent(name='ALE Incoming')
        self.ALE_Linked = SimEvent(name='ALE Linked')
        self.ALE_TimedOut = SimEvent(name='ALE Timed Out')
        self.CallMade = SimEvent(name = 'Call Made')
        self.TimedOut = SimEvent(name='MHS Timed Out') #can be fired from either Receiving or Traffic Gen modes

    def connectNode(self):
        self.CallGen = [N.CallGen for N in Environment.nodes if N.ID==self.ID][0]
        self.ALE_Controller = [N.ALE_Controller for N in Environment.nodes if N.ID==self.ID][0]

    def execute(self):
        while True:
            #always scanning for ALE
            yield waitevent, self, [self.ALE_Incoming, self.ALE_Linked, self.ALE_TimedOut, self.TimedOut, self.CallMade]
            
            if self.eventsFired[0] == self.ALE_Incoming and self.Mode == MHS_Mode.CallGen: #Valid Incoming Call
                print self.ID, '[MHS] rec. inc. call from ALE: change MHS Mode CallGen->InCall, wait to see if ALE links or times out'
                self.Mode = MHS_Mode.InCall
                yield waitevent, self, [self.ALE_Linked, self.ALE_TimedOut]
                if self.eventsFired[0] == self.ALE_Linked:
                    print self.ID, '[MHS] ALE link success, change MHS Mode InCall->Receiving, create Modem Rx process'
                    self.Mode = MHS_Mode.Receving
                    linking_data = self.eventsFired[0].signalparam
                    M_Rx = Modem_Rx(self.ID, linking_data)
                    activate(M_Rx, M_Rx.execute())
                    print '***************************************************************Rx'
                elif self.eventsFired[0] == self.ALE_TimedOut:
                    print self.ID, '[MHS] ALE link fail, change MHS Mode InCall->CallGen'
                    self.Mode = MHS_Mode.CallGen
            elif self.eventsFired[0] == self.ALE_Linked and self.Mode == MHS_Mode.InCall:
                print self.ID, '[MHS] rec. ALE->MHS Linked signal after making Call, change MHS Mode InCall->Linked, create Modem Tx Process'
                #Has Linked successfully from an outgoing call 
                self.Mode = MHS_Mode.TrafficGen
                linking_data = self.eventsFired[0].signalparam
                M_Tx = Modem_Tx(self.ID, linking_data)
                activate(M_Tx, M_Tx.execute())
                print '***************************************************************Tx'
            elif self.eventsFired[0] == self.CallMade and self.Mode == MHS_Mode.CallGen:
                print self.ID, '[MHS] rec. MHS CallMade signal (MHS making call), change MHS Mode CallGen->InCall'
                self.Mode = MHS_Mode.InCall
                linking_data = self.eventsFired[0].signalparam
                self.ALE_Controller.MHS_Incoming.signal(linking_data)
            elif self.eventsFired[0] == self.ALE_TimedOut and self.Mode == MHS_Mode.CallGen:
                print self.ID, '[MHS] rec. ALE->MHS TimedOut signal, change MHS Mode CallGen->CallGen'
                self.Mode = MHS_Mode.CallGen #Quite unnecessary...
            elif self.eventsFired[0] == self.TimedOut and (self.Mode == MHS_Mode.TrafficGen or self.Mode == MHS_Mode.Receving):
                print self.ID, '[MHS] rec. MHS TimedOut signal, reset MHS Mode to CallGen, send MHS_Finished to ALE'
                self.Mode = MHS_Mode.CallGen
                self.ALE_Controller.MHS_Finished.signal()
            else:
                print self.ID, '[MHS] Shouldnt be here (if we keep the passivates in the above if else clauses)', now()

class CallGen(Process):
    def __init__(self, ID):
        Process.__init__(self, name=str(ID)+':CallGen')
        self.ID = ID 
    
    def connectNode(self):
        self.MHS_Controller = [N.MHS_Controller for N in Environment.nodes if N.ID==self.ID][0]
        self.ALE_Controller = [N.ALE_Controller for N in Environment.nodes if N.ID==self.ID][0]

    def execute(self):
        while True:
            yield hold, self, random.uniform(0,60)
            print self.ID, '******************SEND CALL ATTEMPT'
            if self.MHS_Controller.Mode == MHS_Mode.CallGen and self.ALE_Controller.Mode == ALE_Mode.Scan: #Check that it is still valid to send a call
                print '**SUCCESS'
                targetNodeID = -1
                while targetNodeID == self.ID or targetNodeID == -1: #Mini function to make sure
                    targetNodeID = random.randint(0,G.num_nodes-1)  #target isn't itself
                dType = dataType.CALL
                dataChan = -1 #Unknown at this stage - decided in ALE
                dataSize = G.dwell_time*G.num_chans*G.max_bitrate #write function for this
                dataTime = -1 #Note: Size*Env.G.max_bitrate is THEORETICAL MAX and needs to be multiplied by LQA
                dataLQA = -1 #Which is also unknown at this stage, as channel is unknown!
                data = dataStruct(self.ID,targetNodeID,dType,dataChan,dataSize,dataTime,dataLQA)
                self.MHS_Controller.CallMade.signal(data)
            
class Modem_Rx(Process): #Can move these to new module if needed
    def __init__(self, ID, linked_data):
        Process.__init__(self, name=str(ID)+':Modem Rx')
        self.ID = ID
        self.linked_data = linked_data
        
        self.MHS_Controller = [N.MHS_Controller for N in Environment.nodes if N.ID==self.ID][0]

    def execute(self):
        if self.MHS_Controller.Mode == MHS_Mode.Receving: #Check in correct Mode
            yield (get, self, Environment.grid[self.linked_data.chan][self.ID]),(hold, self, G.linked_timeout)
            if not self.acquired(Environment.grid[self.linked_data.chan][self.ID]): #Nothing to report
                self.MHS_Controller.TimedOut.signal()
            else: #Received something
                linked_data = self.got[0] 
                yield hold, self, linked_data.signal_time
                if random.random() < G.chance_reply:
                    M_Tx = Modem_Tx(self.ID, linked_data)
                    activate(M_Tx, M_Tx.execute())
                else:
                    self.MHS_Controller.TimedOut.signal()  

class Modem_Tx(Process): #Can move these to new module if needed
    def __init__(self, ID, linked_data):
        Process.__init__(self, name=str(ID)+':Modem Tx')
        self.ID = ID 
        self.linked_data = linked_data 
        
        self.MHS_Controller = [N.MHS_Controller for N in Environment.nodes if N.ID==self.ID][0]
    
    def execute(self):
        F = MHS_Functions()
        yield hold, self, random.uniform(0,20)
        if self.MHS_Controller.Mode == MHS_Mode.TrafficGen: #Check it's still in the correct Mode
            message = F.createMessage(self.linked_data)
            for each_station in Environment.grid[message.chan]: #This code is same as Linked_Rx code
                yield (put, self, each_station, [message]),(hold, self, G.response_timeout)
                if not self.stored:
                    print self.ID, 'error: Linked mode: all stations should have this channel free, on station:', each_station.name, now()
            yield hold, self, message.signal_time #--------------Hold for signal_time
            for each_station in Environment.grid[message.chan]:
                if each_station.nrBuffered==1:
                    yield get, self, each_station, 1
            yield hold, self, 0.0001 #-----------------Hold for nominal time to prevent SimPy tie
            if random.random() < G.chance_reply:
                M_Rx = Modem_Rx(self.ID, message)
                activate(M_Rx, M_Rx.execute())
            else:
                self.MHS_Controller.TimedOut.signal()
    
class MHS_Functions():
    def createCall(self, data):
        G.scanning_dwell_time*G.num_channels*G.bitrate
    def createMessage(self, data):
        returnData = data
        returnData.origin = data.destination
        returnData.destination = data.origin
        returnData
        Environment.updateLQA(returnData)
        return returnData
    def messageSize(self, data): #These probability values are arbitrary (and hard coded - should be parameters)
        returnData = data
        r = random.random()
        if r < 0.5: returnData.size += random.randint(1,30)*24 #AMD
        elif r < 0.65: returnData.size += random.randint(1,93)*7 #DTM Basic
        elif r < 0.8: returnData.size += random.randint(3,1053)*7 +24 #DTM Extended
        elif r < 0.9: returnData.size += random.randint(1,81)*7 + 16 #DBM Basic
        elif r < 1.0: returnData.size += random.randint(82,37260)*7 + 16 + 24 #DBM Extended
        return returnData 
        
######################################################################
######################################################################
##########################     ENV     ###############################
######################################################################
######################################################################
        
class G(): #Global variables for simulation
    num_chans = 5
    num_nodes = 3
    max_bitrate = 398
    
    dwell_time = 2 #Scanning dwell time
    scanning_call_timeout = 20 #Arb value
    response_timeout = 2 #Arb value
    linked_timeout = 30 #Arb value
    
    chance_reply = 0.6 #probability of replying in linked mode
    
    num_connections = 0

class Environment(Process):
    def __init__(self):
        Process.__init__(self, name='Environment')
        self.nodes = []
        self.grid = []
        self.LQA_grid = []
        
        for i in range(G.num_chans):
            row = []
            for j in range(G.num_nodes):
                S = Store(name = ('node:'+str(j)+',chan:'+str(i)), capacity=1)
                row.append(S)
            self.grid.append(row)
                
        for i in range(G.num_nodes):
            row1 = []
            for j in range(G.num_chans):
                row2 = []
                for h in range(G.num_nodes):
                    lqa_value = random.random()
                    row2.append(lqa_value)
                row1.append(row2)
            self.LQA_grid.append(row1)
    # This is a 3 dimensional grid of Nodes:Channels:Nodes, so each Node has an LQA value for
    # each other Node, and for each channel. e.g. self.LQA_grid[4][1][5] would be the LQA value
    # for Node 4 -> Node 5 on Channel 2
    # THIS GRID NEEDS TO BE SYMMETRICAL !! I.e. a->b == b->a
    # Consider making it a matrix and then looking @ complex networks theory (adjacency matrix)
            
    def execute(self):
        while True:
            yield hold, self, random.uniform(1,10)
            for i in range(len(self.LQA_grid)):
                for j in range(len(self.LQA_grid[i])):
                    for h in range(len(self.LQA_grid[i][j])):
                        self.LQA_grid[i][j][h] = random.random()
    
    #So whenever a signal is sent, it accesses the LQA on the 3D grid for that particular transaction, and then
    #copies it to it's own LQA table (future step...)
    #Obviously, this changing over time algorithm needs to be a bit better! Look at the sin wave examples 
    #from Grapher, so long-term, mid-term and short term changes (frequency), with low-magnitude noise throughout 
    #x = now()
    #y=0.5*(0.85*math.sin(0.1*x) + 0.1*math.sin(x) + 0.05*math.sin(12*x))+0.5
    
    def updateLQA(self, data):
        returnData = data    
        returnData.LQA = self.LQA_grid[returnData.origin][returnData.chan][returnData.destination]
        print 'returned LQA:', returnData.LQA
        returnData.signal_time = returnData.size/G.max_bitrate*(1./returnData.LQA)
        print 'signal_time=', returnData.signal_time, 'size:', returnData.size, '*', G.max_bitrate, '* 1./', returnData.LQA
        return returnData 


class dataStruct():
    def __init__(self, origin=-1, destination=-1, type=-1, chan=-1, size=-1, signal_time=-1, LQA=-1):  
        self.origin = origin
        self.destination = destination
        self.type = type
        self.chan = chan
        self.size = size
        self.signal_time = signal_time
        self.LQA = LQA
        
class dataType():
    CALL = 1
    RESPONSE = 2
    ACK = 3
    DATA = 4
    
class Container():
    def __init__(self, ID):
        self.ID = ID
        self.ALE_Controller = ALE_Controller(ID)
        self.Scanning = Scanning(ID)
        self.MHS_Controller = MHS_Controller(ID)
        self.CallGen = CallGen(ID)
        self.ALE_Mode = ALE_Mode()
        self.MHS_Mode = MHS_Mode()
    def initComponents(self):
        self.ALE_Controller.connectNode()
        self.Scanning.connectNode()
        self.MHS_Controller.connectNode()
        self.CallGen.connectNode()
    def activate(self):
        activate(self.ALE_Controller, self.ALE_Controller.execute(), at=0.0)
        activate(self.Scanning, self.Scanning.execute(), at=0.0)
        activate(self.MHS_Controller, self.MHS_Controller.execute(), at=0.0)
        activate(self.CallGen, self.CallGen.execute(), at=0.0)
    
initialize()

Environment = Environment()
activate(Environment, Environment.execute(), at=0.0)

for i in range(G.num_nodes):
    Node = Container(i)
    Environment.nodes.append(Node)
for i in range(G.num_nodes):
    Environment.nodes[i].initComponents()
for i in range(G.num_nodes):
    Environment.nodes[i].activate()

simulate(until=1000)
print 'done'
print G.num_connections