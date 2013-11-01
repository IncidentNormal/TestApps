#Bandwidth --> affects Latency
#Latency --> affects Human Events
#Human Events --> affects Bandwidth

#Human Event --> Packet --> Bandwidth --> Collisions --> Queues --> Latency

#NEED ROUTING FOR THIS TO BE WORTH ITS SALT
#Basically, if there's 1 channel between every node and they're only talking to nodes they're attached to,
#The only way a collision can occur is if 2 nodes try to talk to each other at exactly the same time
#Do the routing thing, then compare results to just using Shared Channels - might find the results are quite similar!


class G():
    vis_on = True
    print_on = False
    
    node_num = 100
    edge_x = 3

    human_wait_response = 1.0 #average time human waits for response before trying again
    human_wait_next = 3.0 #average time human waits between tasks
    channel_busy = 0.05 #average time sending a packet will busy up channel
    
    max_time = 20  

from SimPy.Simulation import *
from SimPy.Monitor import *
if not G.vis_on: from SimPy.SimPlot import *
import random
import math
import networkx as nx
#import matplotlib.pyplot as plt
if G.vis_on: import visual as v            

class Network():
    def __init__(self):
        self.graph_plan_1 = nx.barabasi_albert_graph(G.node_num,G.edge_x)
        #self.graph_plan_1 = nx.random_regular_graph(G.edge_x, G.node_num)
        self.graph_plan = nx.empty_graph()
        self.Chans = []
        self.ChansIndex = []

        self.waitQMon = Monitor(name='waitQ')
        self.activeQMon = Monitor(name='activeQ')
        
        counter = 0
        for E in self.graph_plan_1.edges():
            self.graph_plan.add_edge(E[0], E[1], {'ID':counter})
            self.Chans.append([counter, Resource(capacity=1, unitName='packet', monitored=True)])
            self.ChansIndex.append([counter,E])
            counter += 1
        self.Chans = dict(self.Chans)
        self.ChansIndex = dict(self.ChansIndex)
        self.Nodes = [NodeHead(N) for N in self.graph_plan]
        print 'Number of Nodes:', len(self.Nodes)
        print 'Number of Channels:', len(self.ChansIndex)
        
    def overallBufferSize(self): #For monitoring
        waitQ = 0
        activeQ = 0
        for i in Net.Chans:
            waitQ += len(self.Chans[i].waitQ)
            activeQ += len(self.Chans[i].activeQ)
        self.waitQMon.observe(waitQ)
        self.activeQMon.observe(activeQ)

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
        self.Computer = [N.Computer for N in Net.Nodes if N.ID==self.ID][0]
        self.MacOut = [N.MacOut for N in Net.Nodes if N.ID==self.ID][0] 
        self.MacIn = [N.MacIn for N in Net.Nodes if N.ID==self.ID][0]
    def go(self):
        yield hold, self, random.uniform(0,1) #to prevent clash at start. Remove this to have all try send at same time.
        #recipientSet = [N.ID for N in Net.Nodes if N.ID != self.ID and self.connected(N.ID)]
        recipientSet = [N for N in Net.graph_plan[self.ID]]
        recipientID = -1
        
        while True:
            if recipientID == -1: #will only be -1 if response received and recipientID reset, otherwise retry same recipient.
                recipientID = random.sample(recipientSet, 1)[0]
            if G.print_on: print 'Node',self.ID,': Recipient',recipientID
            yield put, self, self.humanClicks, [recipientID]
            yield hold, self, random.expovariate(1.0/G.human_wait_response) #DECREASE WITH NUMBER OF PREVIOUS CLICKS w/no response.
            if len(self.Computer.ScreenResponse.theBuffer) == 0:
                if G.print_on: print self.ID, 'Response not recieved from ',recipientID,', perform another Click'
            else:
                if G.print_on: print self.ID, 'Response received from', recipientID, 'bufferSize=', len(self.Computer.ScreenResponse.theBuffer), 'removing 1 from buffer.'
                yield get, self, self.Computer.ScreenResponse, 1
                if G.print_on: print self.ID, 'Packet:: origin:', self.got[0].origin, 'recipient:', self.got[0].recipient
                if recipientID == self.got[0].origin:
                    recipientID = -1
                    yield hold, self, random.expovariate(1.0/G.human_wait_next)
                else:
                    if G.print_on: print '**Old duplicated ARQ packet: discard this.'
                    
    def connected(self, NodeID):
        if NodeID in Net.graph_plan[self.ID]:
            return True
        else:
            return False
                  

class Computer(Process):
    def __init__(self,i):
        Process.__init__(self)
        self.ID = i
        self.ScreenResponse = Store(name='screenResponse'+str(self.ID), capacity=1, unitName='response')                                   
    def initCounterparts(self):
        self.Human = [N.Human for N in Net.Nodes if N.ID==self.ID][0]
        self.MacOut = [N.MacOut for N in Net.Nodes if N.ID==self.ID][0]
        self.MacIn = [N.MacIn for N in Net.Nodes if N.ID==self.ID][0]
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
            recipient = [N for N in Net.Nodes if N.ID==packet_recipient] #find instance of recipient from Node list
            if len(recipient) == 1: recipient = recipient[0] #Should have a length of one, in which case the ID becomes the variable 'recipient'
            else: print 'Problem: Packet lost from macQueue' #else it has been lost somewhere. 

            chanID = self.get_chan_ID(recipient.ID)
            yield request, self, Net.Chans[chanID] #wait for Channel to open
            Net.overallBufferSize()
            if G.vis_on: V.channelOn(chanID)
            yield hold, self, random.expovariate(1.0/G.channel_busy) #again, expovariate (this reflects time sending packet, channel will be used during this so simulates busy) NOTE: For future sim, just model each link in network as a Resource of 1 channel!
            yield release, self, Net.Chans[chanID]
            Net.overallBufferSize()
            if G.vis_on: V.channelOff(chanID)
            yield put, self, recipient.MacIn.macInQueue, self.got
            
    def get_chan_ID(self, recipient):
        if recipient in Net.graph_plan[self.ID]:
            return Net.graph_plan[self.ID][recipient]['ID']
        else:
            print 'Somethings going wrong'
            return -1
    
        
class MacIn(Process):
    def __init__(self,i):
        Process.__init__(self)
        self.ID = i
        self.macInQueue = Store(name='macInQueue'+str(self.ID),capacity='unbounded', unitName='packet')
    def initCounterparts(self):
        self.Computer = [N.Computer for N in Net.Nodes if N.ID==self.ID][0]
        self.MacOut = [N.MacOut for N in Net.Nodes if N.ID==self.ID][0]
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
        self.p_type = p_type #ARQ or Data ('out')


class Vis():
    def __init__(self):
    
        self.NodeList = []
        self.EdgeList = []

        r = 1.0
        delta_theta = (2.0*math.pi) / len(Net.Nodes)
        theta = 0
        
        for N in Net.Nodes:
            node = [N.ID, v.sphere(pos=v.vector(r*math.cos(theta),r*math.sin(theta),0), radius=0.01, color=v.color.white)]
            theta += delta_theta
            self.NodeList.append(node)
        self.NodeList = dict(self.NodeList)
        
        for ind in Net.ChansIndex:
            pos1 = self.NodeList[Net.ChansIndex[ind][0]].pos
            pos2 = self.NodeList[Net.ChansIndex[ind][1]].pos
            ID  = ind
            rod = v.cylinder(pos=pos1, axis=(pos2-pos1), radius=0.0025, color=v.color.green)
            edge = [ind, rod]
            self.EdgeList.append(edge)

        self.EdgeList = dict(self.EdgeList)

    def channelOn(self, chn):
        self.EdgeList[chn].color=v.color.red
    def channelOff(self,chn):
        self.EdgeList[chn].color=v.color.green


initialize()
Net = Network()
if G.vis_on: V = Vis()
for N in Net.Nodes:
    N.initCounterparts()
    N.activate()
simulate(until=G.max_time)
print 'Sim Finished, Visualising graphs...'

if not G.vis_on:
    plt = SimPlot()
    plt2 = SimPlot()
    plt2.plotLine(Net.waitQMon)
    plt.plotLine(Net.activeQMon)
    plt.mainloop()

#nx.draw(Net.graph_plan)
#plt.show()



    



