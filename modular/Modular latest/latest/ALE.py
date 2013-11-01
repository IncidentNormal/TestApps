'''
Created on Oct 28, 2010

@author: duncantait
'''
#This module contains the ALE Superclass

from SimPy.SimulationTrace import *
import random
import MHS, Env

class Mode(): #Can only be in 1 of these 3 modes
    Scanning = 1
    LinkingRx = 2
    LinkingTx = 3
    Linked = 4  

class Controller(Process):
    def __init__(self,ID):
        Process.__init__(self, name='ALE Controller')
        self.ID = ID
        self.Mode = Mode.Scanning
        
        self.LQA_Table = [] #A table of dimensions nodes/channels to store personal last recorded LQA values
        for i in range(Env.G.num_nodes):
            row = []
            for j in range(Env.G.num_chans):
                row.append(random.random())
            self.LQA_Table.append(row)
        
        self.MHS_Incoming = SimEvent(name='MHS Incoming')
        self.MHS_Finished = SimEvent(name='MHS Finished')
        self.Scanning_Call = SimEvent(name='Call Incoming')
        self.Linked = SimEvent(name='Now Linked')
        self.TimedOut = SimEvent(name='Timed Out')
    
    def initComponents(self):
        self.Scanning = [N.Scanning for N in Env.Env.Environment.ALE_nodes if N.ID==self.ID][0]
        self.MHS_Controller = [N.Controller for N in Env.Env.Environment.MHS_nodes if N.ID==self.ID][0]
        
    def execute(self):
        while True:
            #always scanning for MHS, but only interpret if in Scanning mode (ie. not Linking)
            yield waitevent, self, [self.MHS_Incoming, self.MHS_Finished, self.Scanning_Call, self.Linked, self.TimedOut]
            if self.eventsFired[0] == self.MHS_Incoming and self.Mode == Mode.Scanning:
                self.Mode = Mode.LinkingTx
                linking_data = self.eventsFired[0].signalParam
                L_Tx = Linking_Tx(self.ID, linking_data)
                activate(L_Tx, L_Tx.execute())
            elif self.eventsFired[0] == self.Scanning_Call and self.Mode == Mode.Scanning:
                self.Mode = Mode.LinkingRx
                linking_data = self.eventsFired[0].signalParam
                self.MHS_Controller.ALE_Incoming.signal(linking_data)
                L_Rx = Linking_Rx(self.ID, linking_data)
                activate(L_Rx, L_Rx.execute())
            elif self.eventsFired[0] == self.Linked and (self.Mode == Mode.LinkingRx or self.Mode == Mode.LinkingTx):
                self.Mode = Mode.Linked
                linked_data = self.eventsFired[0].signalParam
                self.MHS_Controller.ALE_Linked.signal(linked_data)
                '...passivate' #This one is actually definitely needed (to prevent ALE superclass doing anything)
            elif self.eventsFired[0] == self.TimedOut and not self.Mode == Mode.Scanning:
                self.Mode = Mode.Scanning
                reactivate(self.Scanning)
            elif self.eventsFired[0] == self.MHS_Finished and self.Mode == Mode.Linked:
                self.Mode = Mode.Scanning
                reactivate(self.Scanning)
            else:
                print 'Shouldnt be here (if we keep the passivates in the above if/else clauses)'
    
class Scanning(Process):
    def __init__(self,ID):
        Process.__init__(self, name='Scanning')
        self.ID = ID
        self.current_channel = random.randint(0,Env.G.num_chans-1)
        
    def initComponents(self):
        self.Controller = [N.Controller for N in Env.Env.Environment.ALE_nodes if N.ID==self.ID][0]
        
    def execute(self):
        def forMe(chan): #Filter function for Stores (channels).
            for i in chan:
                if i.destination==self.ID: return [i]
        while True:
            yield (get, self, Env.Env.Environment.grid[self.current_channel][self.ID], forMe),(hold, self, Env.G.dwell_time)
            if not self.acquired(Env.Env.Environment.grid[self.current_channel][self.ID]): #Nothing to report
                if self.current_channel==Env.Env.G.num_chans-1: self.current_channel = 0 #Increment channel or set to 0 if at end of cycle
                else: self.current_channel+=1
            else: #Received something
                info = self.got[0]
                if info.type == Env.dataType.CALL and Controller.Mode == Mode.Scanning: #Check it hasn't changed mode since start of dwell time
                    self.Controller.ScanningCall.signal(info)
                    yield passivate, self
                else:
                    pass 
            if self.Controller.Mode != Mode.Scanning: #At end of channel scan, check if still in Scanning mode
                yield passivate, self

class Linking_Tx(Process):
    def __init__(self,ID,linking_data):
        Process.__init__(self)
        self.ID = ID
        self.linking_data = linking_data
        
        self.Controller = [N.Controller for N in Env.Env.Environment.ALE_nodes if N.ID==self.ID][0]
        
    def execute(self):
        call = self.linking_data
        chanOrder = self.channelOrder(self.linking_data.destination) #choose best channels in order of LQA
        for channel in chanOrder: #try each one in turn
            if Env.Env.Environment.grid[channel][self.ID].nrBuffered==0:
                call.chan = channel
                call = Functions.updateLQA(call)
                for each_station in Env.Env.Environment.grid[call.chan]: #filling channel with call
                    yield put, self, each_station, [call]
                break
        yield hold, self, call.signal_time
        for each_station in Env.Env.Environment.grid[call.chan]:
            if each_station.nrBuffered==1: # Should have been taken by destination
                yield get, self, each_station, 1
        yield hold, self, 0.0001
        yield (get, self, Env.Env.Environment.grid[call.chan][self.ID], 1),(hold, self, Env.G.response_timeout)
        if not self.acquired(Env.Env.Environment.grid[call.chan][self.ID]):
            self.Controller.TimedOut.signal()
        else:
            linking_data = self.got[0] # Response from channel
            yield hold, self, linking_data.signal_time
            ack_data = Functions.ackResponseSwap(linking_data) 
            for each_station in Env.Env.Environment.grid[ack_data.chan]:
                if each_station.nrBuffered == 0:
                    yield put, self, each_station, [ack_data]
                else: pass #Shouldn't really be here
            yield hold, self, ack_data.signal_time
            for each_station in Env.Env.Environment.grid[ack_data.chan]:
                if each_station.nrBuffered==1:
                    yield get, self, each_station, 1              
            self.Controller.Linked.signal(ack_data)
        
    def channelOrder(self,node): 
        #sorts best channels best-worst in terms of LQA and returns an array
        ordered = self.Controller.LQA_Table[node,:].argsort()
        return ordered[::-1] #reverse order of array
            
class Linking_Rx(Process):
    def __init__(self,ID,linking_data):
        Process.__init__(self)
        self.ID = ID
        self.linking_data = linking_data
        
        self.Controller = [N.Controller for N in Env.Env.Environment.ALE_nodes if N.ID==self.ID][0]
        
    def execute(self):
        #Do Rx Handshaking here
        response = Functions.ackResponseSwap(self.linking_data) 
        for each_station in Env.Env.Environment.grid[self.linking_data.chan]:
            yield (put, self, each_station, [response]),(hold, self, Env.G.scanning_call_timeout)
            if not self.stored:
                pass #But shouldn't really be here?
        yield hold, self, response.signal_time #--------------Hold for signal_time
        for each_station in Env.Env.Environment.grid[self.chan]:
            if each_station.nrBuffered==1:
                yield get, self, each_station, 1
        yield hold, self, 0.0001 #-----------------Hold for nominal time to prevent SimPy tie
        yield (get, self, Env.Env.Environment.grid[self.linking_data.chan][self.ID], 1),(hold, self, Env.G.response_timeout)
        if not self.acquired(Env.Env.Environment.grid[self.linking_data.chan][self.ID]): #Did not receive ACK
            self.Controller.TimedOut.signal()
        else: #Received ACK
            linking_data = self.got[0]
            yield hold, self, linking_data.signal_time
            self.Controller.Linked.signal(linking_data)
            
class Functions():
    def ackResponseSwap(self,data):
        returnData = data
        returnData.origin = data.destination
        returnData.destination = data.origin
        Env.Environment.updateLQA(returnData)
        return returnData      
#    def updateLQA(self,data):
#        returnData = data    
#        returnData.LQA = Env.Environment.LQA_grid[ALE.Controller.ID][returnData.chan][returnData.destination]
#        returnData.signal_time = returnData.size*Env.G.max_bitrate*(1./returnData.LQA)
#        return returnData

class Instantiate():
    def __init__(self, ID):
        self.ID = ID
        self.Controller = Controller(ID)
        self.Scanning = Scanning(ID)
        self.Mode = Mode()
    def initComponents(self):
        self.Controller.initComponents()
        self.Scanning.initComponents()
    def activate(self):
        activate(self.Controller, self.Controller.execute(), at=0.0)
        activate(self.Scanning, self.Scanning.execute(), at=0.0)