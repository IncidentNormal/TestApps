#Bandwidth --> affects Latency
#Latency --> affects Human Events
#Human Events --> affects Bandwidth

#Human Event --> Packet --> Bandwidth --> Collisions --> Queues --> Latency

from SimPy.Simulation import *
from SimPy.Monitor import *
from SimPy.SimPlot import *
import random


class G():
    channel_num = 3
    node_num = 15
    
    max_time = 30

class Network():
    Channels = Resource(capacity=G.channel_num, unitName='packet', monitored=True)
    Nodes = []

class NodeHead():
    def __init__(self,i):
        self.ID = i
        self.Human = Human(i)
        self.Computer = Computer(i)
        self.MacOut = MacOut(i)
        self.MacIn = MacIn(i)
    def initCounterparts(self):
        self.Human.initCounterparts()
        self.Computer.initCounterparts()
        self.MacIn.initCounterparts()
    def activate(self):
        activate(self.Human,self.Human.go(),at=0.0)
        activate(self.Computer,self.Computer.go(),at=0.0)
        activate(self.MacOut,self.MacOut.go(),at=0.0)
        activate(self.MacIn,self.MacIn.go(),at=0.0)

class Human(Process):
    def __init__(self,i):
        Process.__init__(self)
        self.ID = i
        self.humanClicks = Store(name='humanClicks'+str(self.ID), capacity=1, unitName='click') #could have more than 1 sent at a time?
    def initCounterparts(self):
        self.Computer = [N.Computer for N in Network.Nodes if N.ID==self.ID]
        if len(self.Computer) == 1: self.Computer = self.Computer[0]
        else: print 'Problem with Ordering: Computer'
        self.MacOut = [N.MacOut for N in Network.Nodes if N.ID==self.ID] #Or have a class containing all these classes? Then link to an 'admin' class that is declared last
        if len(self.MacOut) == 1: self.MacOut=self.MacOut[0]
        else: print 'Problem with Ordering: MacOut'
        self.MacIn = [N.MacIn for N in Network.Nodes if N.ID==self.ID]
        if len(self.MacIn) == 1: self.MacIn=self.MacIn[0]
        else: print 'Problem with Ordering: MacIn'
    def go(self):
        yield hold, self, random.uniform(0,10) #to prevent clash at start. Remove this to have all try send at same time.
        recipientSet = [N.ID for N in Network.Nodes if N.ID != self.ID]
        recipientID = -1
        
        while True:
            if recipientID == -1: #will only be -1 if response received and recipientID reset, otherwise retry same recipient.
                recipientID = random.sample(recipientSet, 1)[0]
            print 'Node',self.ID,': Recipient',recipientID
            yield put, self, self.humanClicks, [recipientID]
            yield hold, self, 2 #human waits for 2 seconds for response. This should be expovariate around a suitable number after debug, OR DECREASE WITH NUMBER OF PREVIOUS CLICKS w/no response.
            if len(self.Computer.ScreenResponse.theBuffer) == 0:
                print self.ID, 'Response not recieved from ',recipientID,', perform another Click'
            else:
                print self.ID, 'Response received from', recipientID, 'bufferSize=', len(self.Computer.ScreenResponse.theBuffer), 'removing 1 from buffer.'
                yield get, self, self.Computer.ScreenResponse, 1
                print self.ID, 'Packet origin:', self.got[0].origin, 'recipient:', self.got[0].recipient
                if recipientID != self.got[0].origin:
                    print 'ARQ MIX UP********************************************'
                recipientID = -1
                yield hold, self, 5 #again, expovariate

class Computer(Process):
    def __init__(self,i):
        Process.__init__(self)
        self.ID = i
        self.ScreenResponse = Store(name='screenResponse'+str(self.ID), capacity=1, unitName='response')                                   
    def initCounterparts(self):
        self.Human = [N.Human for N in Network.Nodes if N.ID==self.ID] #If the initialising doesn't work due to order of creation just use arrays. Humans[i]
        if len(self.Human) == 1: self.Human=self.Human[0]
        else: print 'Problem with Ordering: Human'
        self.MacOut = [N.MacOut for N in Network.Nodes if N.ID==self.ID] #Or have a class containing all these classes? Then link to an 'admin' class that is declared last
        if len(self.MacOut) == 1: self.MacOut=self.MacOut[0]
        else: print 'Problem with Ordering: MacOut'
        self.MacIn = [N.MacIn for N in Network.Nodes if N.ID==self.ID]
        if len(self.MacIn) == 1: self.MacIn=self.MacIn[0]
        else: print 'Problem with Ordering: MacIn'
    def go(self):
        while True:
            yield get, self, self.Human.humanClicks, 1
            P = Packet(self.got[0], self.ID, 'out')
            yield put, self, self.MacOut.macOutQueue, [P]

class MacOut(Process):
    def __init__(self,i):
        Process.__init__(self)
        self.ID = i
        self.macOutQueue = Store(name='macOutQueue'+str(self.ID),capacity='unbounded', unitName='packet')                                            
    def go(self):
        while True:
            yield get, self, self.macOutQueue, 1
            packet_recipient = self.got[0].recipient #get recipient from packet (in future could be multiple)
            recipient = [N for N in Network.Nodes if N.ID==packet_recipient] #find instance of recipient from Node list
            if len(recipient) == 1: recipient = recipient[0]
            else: print 'Problem: Packet lost from macQueue'

            #print self.ID, 'got packet_send_request for ', recipient.ID, 'requesting channel'
            yield request, self, Network.Channels #wait for Channel to open
            #print self.ID, 'got channel, holding'
            yield hold, self, 0.1 #again, expovariate (this reflects time sending packet, channel will be used during this so simulates busy) NOTE: For future sim, just model each link in network as a Resource of 1 channel!
            yield release, self, Network.Channels
            #print self.ID, 'held, putting in recipients macInQueue'
            yield put, self, recipient.MacIn.macInQueue, self.got
            #print self.ID, 'put in macInQueue SUCCESS'

        
class MacIn(Process):
    def __init__(self,i):
        Process.__init__(self)
        self.ID = i
        self.macInQueue = Store(name='macInQueue'+str(self.ID),capacity='unbounded', unitName='packet')
    def initCounterparts(self):
        self.Computer = [N.Computer for N in Network.Nodes if N.ID==self.ID]
        if len(self.Computer) == 1: self.Computer = self.Computer[0]
        else: print 'Problem with Ordering: Computer'
        self.MacOut = [N.MacOut for N in Network.Nodes if N.ID==self.ID] #Or have a class containing all these classes? Then link to an 'admin' class that is declared last
        if len(self.MacOut) == 1: self.MacOut=self.MacOut[0]
        else: print 'Problem with Ordering: MacOut'
    def go(self):
        while True:
            yield get, self, self.macInQueue, 1
            #print self.ID, 'got from macInQueue'
            if self.got[0].p_type == 'ARQ':
                #print self.ID, 'got ARQ, putting in ScreenResponse'
                yield put, self, self.Computer.ScreenResponse, self.got
                #print self.ID, 'put in screenResponse SUCCESS'
            elif self.got[0].p_type == 'out':
                #print self.ID, 'got DATA, putting ARQ in macOutQueue'
                recipient = self.got[0].origin
                P = Packet(recipient, self.ID, 'ARQ')
                yield put, self, self.MacOut.macOutQueue, [P]
                #print self.ID, 'put in macOutQueue SUCCESS'
        

class Packet():
    def __init__(self, recipient, origin, p_type):
        self.recipient = recipient
        self.origin = origin
        self.p_type = p_type


initialize()
Network.Nodes = [NodeHead(i) for i in range(G.node_num)]
for N in Network.Nodes:
    N.initCounterparts()
    N.activate()
simulate(until=G.max_time)
print 'Sim Finished, Visualising graphs...'

plt = SimPlot()
#plt.plotLine(Network.Channels.waitMon)
plt.plotLine(Network.Channels.actMon)
plt.mainloop()

    



