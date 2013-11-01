'''
Created on Oct 28, 2010

@author: duncantait
'''
#This module contains the MHS Superclass

from SimPy.SimulationTrace import *
import random
import ALE, Env

class Mode(): #Can only be in 1 of these 3 modes
    CallGen = 1 #Generating calls from an Idle (Scanning) state
    InCall = 2
    TrafficGen = 3 #Generating Traffic once in a Linked state
    Receving = 4 #Receiving Traffic while in a Linked state

class Controller(Process):
    def __init__(self,ID):
        Process.__init__(self, name='MHS Controller')
        self.ID = ID
        self.Mode = Mode.CallGen
        
        self.ALE_Incoming = SimEvent(name='ALE Incoming')
        self.ALE_Linked = SimEvent(name='ALE Linked')
        self.ALE_TimedOut = SimEvent(name='ALE Timed Out')
        self.CallMade = SimEvent(name = 'Call Made')
        self.TimedOut = SimEvent(name='Finished MHS') #can be fired from either Receiving or Traffic Gen modes
        
    def execute(self):
        while True:
            #always scanning for ALE
            yield waitevent, self, [self.ALE_Incoming, self.ALE_Linked, self.ALE_TimedOut, self.TimedOut]
            if self.eventsFired[0] == self.ALE_Incoming and self.Mode == Mode.CallGen: #Valid Incoming Call
                self.Mode = Mode.InCall
                yield waitevent, self, [self.ALE_Linked, self.ALE_TimedOut]
                if self.eventsFired[0] == self.ALE_Linked:
                    self.Mode = Mode.Receving
                    linking_data = self.eventsFired[0].signalParam
                    M_Rx = Modem_Rx(self.ID, linking_data)
                    activate(M_Rx, M_Rx.execute())
                    print '***************************************************************Rx'
                elif self.eventsFired[0] == self.ALE_TimedOut:
                    self.Mode = Mode.CallGen
            elif self.eventsFired[0] == self.ALE_Linked and self.Mode == Mode.CallGen:
                #Has Linked successfully from an outgoing call 
                self.Mode = Mode.TrafficGen
                linking_data = self.eventsFired[0].signalParam
                M_Tx = Modem_Tx(self.ID, linking_data)
                activate(M_Tx, M_Tx.execute())
                print '***************************************************************Tx'
            elif self.eventsFired[0] == self.CallMade and self.Mode == Mode.CallGen:
                self.Mode = Mode.InCall
                linking_data = self.eventsFired[0].signalParam
                ALE.Controller.MHS_Incoming.signal(linking_data)
            elif self.eventsFired[0] == self.ALE_TimedOut and self.Mode == Mode.CallGen:
                self.Mode = Mode.CallGen #Quite unnecessary...
            elif self.eventsFired[0] == self.TimedOut and (self.Mode == Mode.TrafficGen or self.Mode == Mode.Receving):
                self.Mode = Mode.CallGen
                ALE.Controller.MHS_Finished.signal()
            else:
                print self.ID, 'Shouldnt be here (if we keep the passivates in the above if else clauses)', now()

class CallGen(Process):
    def __init__(self, ID):
        Process.__init__(self, name='CallGen')
        self.ID = ID 
    def execute(self):
        while True:
            yield hold, self, random.uniform(0,60)
            if Controller.Mode == Mode.CallGen and ALE.Controller.Mode == ALE.Mode.Scanning: #Check that it is still valid to send a call
                targetNodeID = random.randint(Env.G.num_nodes) #write function for this
                dataType = Env.dataType.CALL
                dataChan = -1 #Unknown at this stage - decided in ALE
                dataSize = random.uniform(15,256) #write function for this
                dataTime = -1 #Note: Size*Env.G.max_bitrate is THEORETICAL MAX and needs to be multiplied by LQA
                dataLQA = -1 #Which is also unknown at this stage, as channel is unknown!
                data = Env.dataStruct(self.ID,targetNodeID,dataType,dataChan,dataSize,dataTime,dataLQA)
                Controller.CallMade.signal(data)
            
class Modem_Rx(Process): #Can move these to new module if needed
    def __init__(self, ID, linked_data):
        Process.__init__(self)
        self.ID = ID
        self.linked_data = linked_data
    def execute(self):
        if Controller.Mode == Mode.Receving: #Check in correct Mode
            yield (get, self, Env.Environment.grid[self.linked_data.chan][self.ID]),(hold, self, Env.G.linked_timeout)
            if not self.acquired(Env.Environment.grid[self.linked_data.cha][self.ID]): #Nothing to report
                Controller.TimedOut.signal()
            else: #Received something
                linked_data = self.got[0] 
                yield hold, self, linked_data.signal_time
                if random.random() < Env.G.chance_reply:
                    M_Tx = Modem_Tx(self.ID, linked_data)
                    activate(M_Tx, M_Tx.execute())
                else:
                    Controller.TimedOut.signal()  

class Modem_Tx(Process): #Can move these to new module if needed
    def __init__(self, ID, linked_data):
        Process.__init__(self)
        self.ID = ID 
        self.linked_data = linked_data 
    'when finished, send self.TimedOut signal to Controller, then send ALE_MHS_Finished signal'
    def execute(self):
        yield hold, self, random.uniform(0,60)
        if Controller.Mode == Mode.TrafficGen: #Check it's still in the correct Mode
            message = Functions.createMessage(self.linked_data)
            for each_station in Env.Environment.grid[message.chan]: #This code is same as Linked_Rx code
                yield (put, self, each_station, [message]),(hold, self, Env.G.response_timeout)
                if not self.stored:
                    print self.ID, 'error: Linked mode: all stations should have this channel free, on station:', each_station.name, now()
            yield hold, self, message.signal_time #--------------Hold for signal_time
            for each_station in Env.Environment.grid[message.chan]:
                if each_station.nrBuffered==1:
                    yield get, self, each_station, 1
            yield hold, self, 0.0001 #-----------------Hold for nominal time to prevent SimPy tie
            if random.random() < Env.G.chance_reply:
                M_Rx = Modem_Rx(self.ID, message)
                activate(M_Rx, M_Rx.execute())
            else:
                Controller.TimedOut.signal()
    
class Functions():
    def createMessage(self, data):
        returnData = data
        returnData.origin = data.destination
        returnData.destination = data.origin
        returnData
        Env.Environment.updateLQA(returnData)
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

class _MHS():
    def __init__(self, ID):
        self.ID = ID
        self.Controller = Controller(ID)
        self.CallGen = CallGen(ID)
        
        activate(self.Controller, self.Controller.execute(), at=0.0)
        activate(self.CallGen, self.CallGen.execute(), at=0.0)

            
            
        