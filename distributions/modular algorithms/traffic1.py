'''
Created on Nov 18, 2010

@author: duncantait

This version has an ARQ class which is NOT USED
So it is merely a 1 way sending of a packet over a network, and is a channel is busy it was going to use, then it discards the packet
'''
from SimPy.Simulation import *
import random
import networkx as nx

class G():
    graph = ''
    edges = []
    nodes = []
    
    NUM_NODES = 10
    
    TIME_BETWEEN_MSG = 3.
    ARQ_TIMEOUT = 1.
    TIME_PER_MSG_SEND = 0.1 #this needs to be associated with size, could be frame size for now
    
    SUCCESSFUL = 0
    FAILURE = 0
    
class GenerateNetwork():
    def gen(self):
        #G.graph = nx.barabasi_albert_graph(G.NUM_NODES,5)
        G.graph = nx.complete_graph(G.NUM_NODES)
        for i in G.graph.edges_iter():
            channel = Store(name=i)
            G.edges.append(channel)
    
class NetworkProtocol(Process):
    #TDMA
    def __init__(self):
        Process.__init__(self)
        self.Events = []
        self.TDMA_slot_time = 0.5
        self.currentSlot = 0
        for n in range(G.NUM_NODES):
            sE = SimEvent(name=str(n))
            self.Events.append(sE)
    def execute(self):
        while True:
            self.Events[self.currentSlot].signal()
            if self.currentSlot==(G.NUM_NODES-1):
                self.currentSlot = 0
            else:
                self.currentSlot += 1
            yield hold, self, self.TDMA_slot_time

class Packet():
    origin = -1
    destination = -1
    route = []
    ARQ = False
    
class TrafficGen(Process):
    def __init__(self, ID):
        Process.__init__(self)
        self.ID = ID
    def initComponents(self):
        self.QueueManagement = [N.QueueManagement for N in G.nodes if N.ID==self.ID][0]
    def execute(self):
        A = Algorithms()
        while True:
            yield hold, self, random.expovariate(1/G.TIME_BETWEEN_MSG)
            P = Packet()
            P.origin = self.ID
            P = A.choose_destination(P)
            P = A.route(P)
            if len(P.route) > 0: 
                yield put, self, self.QueueManagement.inQueue, [P]
    
class ReSend(Process):
    def __init__(self, ID):
        Process.__init__(self)
        self.ID = ID
        self.inQueue = Store(name='RS_Queue', capacity='unbounded')
    def initComponents(self):
        self.QueueManagement = [N.QueueManagement for N in G.nodes if N.ID==self.ID][0]
    def execute(self):
        A = Algorithms()
        while True:
            yield get, self, self.inQueue, 1
            packet = self.got
            P.origin = self.ID
            P = A.choose_destination(P)
            P = A.route(P)
            yield put, self, self.QueueManagement.inQueue, [P]
    
class QueueManagement(Process):
    def __init__(self, ID):
        Process.__init__(self)
        self.ID = ID
        self.inQueue = Store(name='QM_Queue',capacity='unbounded')
    def initComponents(self):
        self.Send = [N.Send for N in G.nodes if N.ID==self.ID][0]
    def execute(self):
        while True:
            yield get, self, self.inQueue, 1
            packet = self.got[0]
            if packet.ARQ:
                yield put, self, self.inQueue, [packet], 10
            else:
                yield put, self, self.Send.inQueue, [packet], 1

class Send(Process):
    def __init__(self, ID):
        Process.__init__(self)
        self.ID = ID
        self.inQueue = Store(name='Send_Queue', capacity='unbounded')
    def execute(self):
        while True:
            yield get, self, self.inQueue, 1
            packet = self.got[0]
            nextEdge = packet.route[-1]
            yield waitevent, self, Net.Events[self.ID]
            if G.edges[nextEdge].nrBuffered==0:
                packet.route.pop()
                yield put, self, G.edges[nextEdge], [packet]
                yield hold, self, G.TIME_PER_MSG_SEND
                yield get, self, G.edges[nextEdge], 1
                if len(packet.route)==0:
                    G.SUCCESSFUL += 1
            else:
                print self.ID, 'channel busy, discard packet'
                G.FAILURE += 1
            
class ARQ(Process):
    def __init__(self, ID, packet):
        Process.__init__(self)
        self.ID = ID
        self.packet = packet
        self.ReSend = [N.ReSend for N in G.nodes if N.ID==self.ID][0]
    def execute(self):
        def filter():
            if self.packet.destination == self.ID:
                return True
        yield (get, self, self.packet.route[0], filter)(hold, self, G.ARQ_TIMEOUT)
        if self.acquired(self.packet.route[0]):
            print self.ID, 'got ARQ, success', now()
            yield put,self, packet.route[0], [self.packet]
        else:
            print self.ID, 'ARQ failed resending packet', now()
            yield put, self, self.ReSend.inQueue, [self.packet] 

class Algorithms():
    def choose_destination(self, packet):
        returnPacket = packet
        while returnPacket.destination==returnPacket.origin or returnPacket.destination==-1:
            returnPacket.destination = random.randint(0, G.NUM_NODES-1)
        return returnPacket
    def route(self, packet):
        #djikstra's shortest path
        #A* algorithm
        returnPacket = packet
        nodeRoute = nx.shortest_path(G.graph, packet.origin, packet.destination)
        edgeRoute = []
        chanRoute = []
        for i in range(len(nodeRoute)-1):
            edgeRoute.append((i,i+1))
        for i in edgeRoute:
            counter=0
            for chan in G.edges:
                if chan.name==i:
                    chanRoute.append(counter)
                    break
                counter+=1
        chanRoute = chanRoute[::-1] #reverse order
        returnPacket.route = chanRoute
        return returnPacket
    
class NodeContainer():
    def __init__(self, ID):
        self.ID = ID
        self.TrafficGen = TrafficGen(ID)
        self.ReSend = ReSend(ID)
        self.QueueManagement = QueueManagement(ID)
        self.Send = Send(ID)
    def initComponents(self):
        self.TrafficGen.initComponents()
        self.ReSend.initComponents()
        self.QueueManagement.initComponents()
    def activate(self):
        activate(self.TrafficGen,self.TrafficGen.execute(),at=0.0)
        activate(self.ReSend,self.ReSend.execute(),at=0.0)
        activate(self.QueueManagement,self.QueueManagement.execute(),at=0.0)
        activate(self.Send,self.Send.execute(),at=0.0)
        
initialize()

Gen = GenerateNetwork()
Gen.gen()
Net = NetworkProtocol()
activate(Net,Net.execute(),at=0.0)

for i in range(G.NUM_NODES):
    Node = NodeContainer(i)
    G.nodes.append(Node)
for i in range(G.NUM_NODES):
    G.nodes[i].initComponents()
for i in range(G.NUM_NODES):
    G.nodes[i].activate()

simulate(until=1000) 
print 'done'
print 'success=', G.SUCCESSFUL, ', failure=', G.FAILURE   
        
            
            