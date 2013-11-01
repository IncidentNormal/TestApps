'''
Created on Oct 28, 2010

@author: duncantait
'''
#This module contains the ALE Superclass

from SimPy.SimulationTrace import *
import random

class Mode(): #Can only be in 1 of these 3 modes
    Scanning = 1
    LinkingRx = 2
    LinkingTx = 3
    Linked = 4

class Controller(Process):
    def __init__(self,ID):
        Process.__init__(self)
        self.ID = ID
        self.Mode = Mode.Scanning
        
        self.MHS_Incoming = SimEvent(name='MHS Incoming')
        self.MHS_Finished = SimEvent(name='MHS Finished')
        self.Scanning_Call = SimEvent(name='Call Incoming')
        self.Linked = SimEvent(name='Now Linked')
        self.TimedOut = SimEvent(name='Timed Out')
        
    def execute(self):
        while True:
            #always scanning for MHS, but only interpret if in Scanning mode (ie. not Linking)
            yield waitevent, self, [self.MHS_Incoming, self.MHS_Finished, self.Scanning_Call, self.Linked, self.TimedOut]
            if self.eventsFired[0] == self.MHS_Incoming and self.Mode == Mode.Scanning:
                self.Mode = Mode.LinkingTx
                linking_data = self.eventsFired[0].signalParam
                L_Tx = Linking_Tx(self.ID, linking_data)
                activate(L_Tx, L_Tx.execute())
                '... passivate'
            elif self.eventsFired[0] == self.Scanning_Call and self.Mode == Mode.Scanning:
                self.Mode = Mode.LinkingRx
                linking_data = self.eventsFired[0].signalParam
                L_Rx = Linking_Rx(self.ID, linking_data)
                activate(L_Rx, L_Rx.execute())
                '...passivate'
            elif self.eventsFired[0] == self.Linked and (self.Mode == Mode.LinkingRx or self.Mode == Mode.LinkingTx):
                self.Mode = Mode.Linked
                'return Linked event to MHS'
                '...passivate' #This one is actually definitely needed (to prevent ALE superclass doing anything)
            elif self.eventsFired[0] == self.TimedOut and not self.Mode == Mode.Scanning:
                self.Mode = Mode.Scanning
            elif self.eventsFired[0] == self.MHS_Finished and self.Mode == Mode.Linked:
                self.Mode = Mode.Scanning
            else:
                print 'Shouldnt be here (if we keep the passivates in the above if else clauses)'
    
class Scanning(Process):
    def __init__(self,ID):
        Process.__init__(self)
        self.ID = ID
        
    def execute(self):
        while True:
            #Do Scanning stuff here, this is not a serious architectural issue - use previous
            rnd = random.randint(1,2)
            if rnd==2:
                ALE.Controller.ScanningCall.signal('some data')
            else:
                yield hold, self, 2

class Linking_Tx(Process):
    def __init__(self,ID,linking_data):
        Process.__init__(self)
        self.ID = ID
        self.linking_data = linking_data
    
    def execute(self):
        #Do Tx Handshaking here
        rnd = random.randint(1,2)
        if rnd==2:
            ALE.Controller.Linked.signal('some data')
        else:
            ALE.Controller.TimedOut.signal
            yield hold, self, 2
            
class Linking_Rx(Process):
    def __init__(self,ID,linking_data):
        Process.__init__(self)
        self.ID = ID
        self.linking_data = linking_data
    
    def execute(self):
        #Do Rx Handshaking here
        rnd = random.randint(1,2)
        if rnd==2:
            ALE.Controller.Linked.signal('some data')
        else:
            ALE.Controller.TimedOut.signal
            yield hold, self, 2

class _ALE():
    def __init__(self, ID):
        self.ID = ID
        self.Mode = Mode()
        self.Controller = Controller(ID)
        self.Scanning = Scanning(ID)
        
        #Need to activate these aswell
        
ALE = _ALE(i=-1)
            
            
        