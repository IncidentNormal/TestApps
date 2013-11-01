'''
Created on Oct 28, 2010

@author: duncantait
'''
#This module contains the MHS Superclass

from SimPy.SimulationTrace import *
import random
import ALE, Env

class Mode(): #Can only be in 1 of these 3 modes
    CallGen = 1
    TrafficGen = 2
    Receving = 3

class Controller(Process):
    def __init__(self,ID):
        Process.__init__(self)
        self.ID = ID
        self.Mode = Mode.CallGen
        
        self.ALE_Incoming = SimEvent(name='ALE Incoming')
        self.ALE_Linked = SimEvent(name='ALE Linked')
        self.ALE_TimedOut = SimEvent(name='ALE Timed Out')
        
    def execute(self):
        while True:
            #always scanning for ALE
            yield waitevent, self, [self.ALE_Incoming, self.ALE_Linked, self.ALE_TimedOut]
            if self.eventsFired[0] == self.ALE_Incoming and self.Mode == Mode.CallGen: #Valid Incoming Call
                yield waitevent, self, [self.ALE_Linked, self.ALE_TimedOut]
                if self.eventsFired[0] == self.ALE_Linked:
                    self.Mode = Mode.Receving
                elif self.eventsFired[0] == self.ALE_TimedOut:
                    self.Mode = Mode.CallGen
            elif self.eventsFired[0] == self.Linked and self.Mode == Mode.CallGen:
                #Has Linked successfully off an outgoing call 
                self.Mode = Mode.TrafficGen
                linking_data = self.eventsFired[0].signalParam
                TG = TrafficGen(self.ID, linking_data)
                activate(TG, TG.execute())
                '...passivate'

            else:
                print 'Shouldnt be here (if we keep the passivates in the above if else clauses)'

class CallGen(Process):
    def __init__(self, ID):
        Process.__init__(self)
        self.ID = ID 
    def execute(self):
        while True:
            yield hold, self, random.uniform(0,20)
            if Controller.Mode == Mode.CallGen and ALE.Controller.Mode == ALE.Mode.Scanning: #Check that it is still valid to send a call
                'Send ALE signal MHS_Incoming'
                targetNodeID = random.randint(Env.G.num_nodes) #write function for this
                dataType = Env.dataType.CALL
                dataChan = -1 #Unknown at this stage - decided in ALE
                dataSize = random.uniform(15,256) #write function for this
                dataTime = -1 #Note: Size*Env.G.max_bitrate is THEORETICAL MAX and needs to be multiplied by LQA
                dataLQA = -1 #Which is also unknown at this stage, as channel is unknown!
                data = Env.dataStruct(self.ID,targetNodeID,dataType,dataChan,dataSize,dataTime)
                ALE.Controller.MHS_Incoming.signal('data')
            


class TrafficGen(Process):
    def __init__(self, ID):
        Process.__init__(self)
        self.ID = ID

class _MHS():
    def __init__(self, ID):
        self.ID = ID
        self.Controller = Controller(ID)
        
MHS = _MHS(i=-1)
            
            
        