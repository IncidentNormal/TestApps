#Bandwidth --> affects Latency
#Latency --> affects Human Events
#Human Events --> affects Bandwidth

#Human Event --> Packet --> Bandwidth --> Collisions --> Queues --> Latency

from SimPy.Simulation import *
from SimPy.Monitor import *
#from SimPy.SimPlot import *
import visual as v
import random


class G():
    channel_num = 10
    node_num = 20

    human_wait_response = 2.0 #average time human waits for response before trying again
    human_wait_next = 5.0 #average time human waits between tasks
    channel_busy = 0.05 #average time sending a packet will busy up channel
    
    max_time = 90

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
        self.humanClicks = Store(name='humanClicks'+str(self.ID), capacity=1, unitName='click') 
    def initCounterparts(self):
        self.Computer = [N.Computer for N in Network.Nodes if N.ID==self.ID][0]
        self.MacOut = [N.MacOut for N in Network.Nodes if N.ID==self.ID][0] 
        self.MacIn = [N.MacIn for N in Network.Nodes if N.ID==self.ID][0]
    def go(self):
        yield hold, self, random.uniform(0,1) #to prevent clash at start. Remove this to have all try send at same time.
        recipientSet = [N.ID for N in Network.Nodes if N.ID != self.ID]
        recipientID = -1
        
        while True:
            if recipientID == -1: #will only be -1 if response received and recipientID reset, otherwise retry same recipient.
                recipientID = random.sample(recipientSet, 1)[0]
            print 'Node',self.ID,': Recipient',recipientID
            yield put, self, self.humanClicks, [recipientID]
            yield hold, self, random.expovariate(1.0/G.human_wait_response) #DECREASE WITH NUMBER OF PREVIOUS CLICKS w/no response.
            if len(self.Computer.ScreenResponse.theBuffer) == 0:
                print self.ID, 'Response not recieved from ',recipientID,', perform another Click'
            else:
                print self.ID, 'Response received from', recipientID, 'bufferSize=', len(self.Computer.ScreenResponse.theBuffer), 'removing 1 from buffer.'
                yield get, self, self.Computer.ScreenResponse, 1
                print self.ID, 'Packet:: origin:', self.got[0].origin, 'recipient:', self.got[0].recipient
                if recipientID == self.got[0].origin:
                    recipientID = -1
                    yield hold, self, random.expovariate(1.0/G.human_wait_next)
                else:
                    print '**Old duplicated ARQ packet: discard this.'
                    

class Computer(Process):
    def __init__(self,i):
        Process.__init__(self)
        self.ID = i
        self.ScreenResponse = Store(name='screenResponse'+str(self.ID), capacity=1, unitName='response')                                   
    def initCounterparts(self):
        self.Human = [N.Human for N in Network.Nodes if N.ID==self.ID][0]
        self.MacOut = [N.MacOut for N in Network.Nodes if N.ID==self.ID][0]
        self.MacIn = [N.MacIn for N in Network.Nodes if N.ID==self.ID][0]
    def go(self):
        while True:
            yield get, self, self.Human.humanClicks, 1
            P = Packet(self.got[0], self.ID, 'out')
            yield put, self, self.MacOut.macOutQueue, [P]
            Vis.AddToQueue(self.ID,True)

class MacOut(Process):
    def __init__(self,i):
        Process.__init__(self)
        self.ID = i
        self.macOutQueue = Store(name='macOutQueue'+str(self.ID),capacity='unbounded', unitName='packet')                                            
    def go(self):
        while True:
            yield get, self, self.macOutQueue, 1
            Vis.AddToQueue(self.ID,False)
            packet_recipient = self.got[0].recipient #get recipient from packet (in future could be multiple)
            recipient = [N for N in Network.Nodes if N.ID==packet_recipient] #find instance of recipient from Node list
            if len(recipient) == 1: recipient = recipient[0]
            else: print 'Problem: Packet lost from macQueue'

            Vis.channelChange()
            yield request, self, Network.Channels #wait for Channel to open
            Vis.channelChange()
            yield hold, self, random.expovariate(1.0/G.channel_busy) #again, expovariate (this reflects time sending packet, channel will be used during this so simulates busy) NOTE: For future sim, just model each link in network as a Resource of 1 channel!
            Vis.channelChange()
            yield release, self, Network.Channels
            Vis.channelChange()
            yield put, self, recipient.MacIn.macInQueue, self.got

        
class MacIn(Process):
    def __init__(self,i):
        Process.__init__(self)
        self.ID = i
        self.macInQueue = Store(name='macInQueue'+str(self.ID),capacity='unbounded', unitName='packet')
    def initCounterparts(self):
        self.Computer = [N.Computer for N in Network.Nodes if N.ID==self.ID][0]
        self.MacOut = [N.MacOut for N in Network.Nodes if N.ID==self.ID][0]
    def go(self):
        while True:
            yield get, self, self.macInQueue, 1
            if self.got[0].p_type == 'ARQ':
                yield put, self, self.Computer.ScreenResponse, self.got
            elif self.got[0].p_type == 'out':
                recipient = self.got[0].origin
                P = Packet(recipient, self.ID, 'ARQ')
                yield put, self, self.MacOut.macOutQueue, [P]
        

class Packet():
    def __init__(self, recipient, origin, p_type):
        self.recipient = recipient
        self.origin = origin
        self.p_type = p_type

class Visualise():
    def __init__(self):
        self.ChannelList = []
        self.NodeList = []
        print 'Start visualising'
        self.ChnLabel = v.label(pos=(0,0,0), color=v.color.green)

        for i in range(len(Network.Nodes)):
            MacInQueue = []
            MacOutQueue = []
            self.NodeList.append([MacInQueue, MacOutQueue])

    def AddToQueue(self, ID, In):
        InOut = 1
        if In == True: InOut = 0
        priorSquare = 0
        if len(self.NodeList[ID][InOut]) > 0:
            priorSquare = self.NodeList[ID][InOut][-1].pos[1]
        newY = priorSquare + 1
        if In==1: box = v.box(pos=(ID*2+InOut, newY, 0), Length=0.25, Width=0.25, Height=0.25, color=v.color.green)
        else: box = v.box(pos=(ID*2+InOut, newY, 0), Length=0.25, Width=0.25, Height=0.25, color=v.color.red)
        self.NodeList[ID][InOut].append(box)

    def RemoveFromQueue(self, ID, In):
        InOut = 1
        if In == True: InOut = 0
        if len(self.NodeList[ID][InOut]) > 0:
            self.NodeList[ID][InOut].pop()
            
    def channelChange(self):
        self.ChnLabel.text=str(len(Network.Channels.activeQ))
        

initialize()
Network.Nodes = [NodeHead(i) for i in range(G.node_num)]
for N in Network.Nodes:
    N.initCounterparts()
    N.activate()
Vis = Visualise()
simulate(until=G.max_time)
print 'Sim Finished, Visualising graphs...'

##plt = SimPlot()
##plt.plotLine(Network.Channels.waitMon)
##plt.plotLine(Network.Channels.actMon)
##plt.mainloop()

    



