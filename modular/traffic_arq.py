'''
Created on Nov 18, 2010

@author: duncantait

'''

from SimPy.Simulation import *
import random
import networkx as nx
from copy import deepcopy

class G():
    graph = ''
    edges = []
    nodes = []
    
    NUM_NODES = 5
    
    TIME_BETWEEN_MSG = 10.
    ARQ_TIMEOUT = 2.
    TIME_PER_MSG_SEND = 0.1 #this needs to be associated with size, could be frame size for now
    
    SUCCESSFUL = 0
    FAILURE = 0
    
class GenerateNetwork():
    def gen(self):
        #G.graph = nx.barabasi_albert_graph(G.NUM_NODES,5)
        G.graph = nx.complete_graph(G.NUM_NODES)
        for i in G.graph.edges_iter():
            channel = Store(name=i, capacity=1)
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
                print self.ID, 'packet created:', P.origin, P.destination, P.route, now() 
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
            packet = self.got[0]
            packet.origin = self.ID
            packet = A.choose_destination(packet)
            packet = A.route(packet)
            yield put, self, self.QueueManagement.inQueue, [packet]
            
class SendARQ(Process):
    def __init__(self, ID):
        Process.__init__(self)
        self.ID = ID
        self.inQueue = Store(name='SendARQ_Queue', capacity='unbounded')
    def initComponents(self):
        self.QueueManagement = [N.QueueManagement for N in G.nodes if N.ID==self.ID][0]
    def execute(self):
        A = Algorithms()
        while True:
            yield get, self, self.inQueue, 1
            print self.ID, 'ARQSEND packet recd, swap origin and destination', now()
            packet = self.got[0]
            print self.ID, 'original:', packet.origin, packet.destination, packet.route
            destination = packet.destination
            packet.destination = packet.origin
            packet.origin = destination
            packet.ARQ = True
            packet = A.route(packet)
            print self.ID, 'now:', packet.origin, packet.destination, packet.route
            yield put, self, self.QueueManagement.inQueue, [packet]
            
    
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
            print self.ID, 'packet recd in queue', now()
            packet = self.got[0]
            if packet.ARQ:
                yield put, self, self.Send.inQueue, [packet], 10
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
            print self.ID, 'packet recd in sendqueue', now()
            packet = self.got[0]
            print self.ID, 'packet contents:', packet.origin, packet.destination, packet.route, packet.ARQ, now()
            nextEdge = packet.route[-1]
            yield waitevent, self, Net.Events[self.ID]
            print self.ID, 'TDMA slot reached', now()
            if G.edges[nextEdge].nrBuffered==0:
                if packet.origin==self.ID and packet.ARQ==False:
                    print self.ID, 'starting ARQ', now()
                    packetcopy = deepcopy(packet)
                    arq = ARQ(self.ID, packetcopy)
                    activate(arq,arq.execute())
                    
                packet.route.pop()
                yield hold,self,0.001
                
                yield (put, self, G.edges[nextEdge], [packet]),(hold, self, 0.001)
                if self.stored(G.edges[nextEdge]):
                    yield hold, self, G.TIME_PER_MSG_SEND
                yield (get, self, G.edges[nextEdge], 1, 10),(hold, self, 0.001)
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
        def filter(chan):
            for i in chan:
                if i.destination == self.ID: return [i]
        yield (get, self, G.edges[self.packet.route[0]], filter),(hold, self, G.ARQ_TIMEOUT)
        if self.acquired(G.edges[self.packet.route[0]]):
            rec = self.got[0]
            if rec.ARQ==True:
                print self.ID, 'got ARQ, success', now()
            else:
                print self.ID, 'errrrroneous', now()
                yield put,self, G.edges[self.packet.route[0]], [self.packet] #This is a big issue: if it is replaced onto channel, it will trigger other processes waiting for anything on that channel
        else: #and send it on to destination, but if we dont replace it the channel can be taken instantaneously, which will mean no collisions can possible occur. Maybe need a 'delivered' or 'read' (as in it's been read) tag that means nobody picks it up regardless of anything and it remains on channel
            print self.ID, 'ARQ failed to come, resending original packet', now()
            yield put, self, self.ReSend.inQueue, [self.packet]
            
class IncomingMon(Process):
    def __init__(self, ID, edge):
        Process.__init__(self)
        self.ID = ID
        self.edge = edge
        self.chan = -1
    def initComponents(self):
        self.SendARQ = [N.SendARQ for N in G.nodes if N.ID==self.ID][0]
        self.QueueManagement = [N.QueueManagement for N in G.nodes if N.ID==self.ID][0]
    def execute(self):
        counter=0
        for chan in G.edges:
            if chan.name==self.edge:
                self.chan=counter
                break
            counter+=1
        print self.ID, 'IncMon Init:', self.edge, self.chan
        while True:
            while True:
                yield get, self, G.edges[self.chan], 1
                if (self.got[0].origin==self.ID) or (self.got[0].destination==self.ID and self.got[0].ARQ==True):
                    yield put, self, G.edges[self.chan], self.got #BIG HACK, SimPy doesnt like multiple processes waiting on the same Store with different filter functons
                    break #so simply take it regardless and put it back if not wanted
                print self.ID, 'Incoming Packet recd, edge:', self.edge, now()
                packet = self.got[0]
                if packet.destination==self.ID:
                    yield put, self, self.SendARQ.inQueue, [packet]
                else:
                    yield put, self, self.QueueManagement.inQueue, [packet]
                
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
            edgeRoute.append((nodeRoute[i],nodeRoute[i+1]))
        for i in edgeRoute:
            a = i[0] #MAKE SURE TUPLE IS IN CORRECT ORDER. Consider making global function for this.
            b = i[1]
            if a>b:
                first = a
                a = b
                b = first
            counter=0
            for chan in G.edges:
                if chan.name==(a,b):
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
        self.SendARQ = SendARQ(ID)
        self.QueueManagement = QueueManagement(ID)
        self.Send = Send(ID)
        self.IncomingMons = []
        for node in G.graph.neighbors(ID):
            edge = 0
            if self.ID > node: edge = (node,self.ID) #as these are the names of the Stores in network, must be careful to make sure the address is the right way round
            else: edge = (self.ID, node) #always has lower value node first
            IM = IncomingMon(ID,edge)
            print self.ID, 'IncMon:', edge
            self.IncomingMons.append(IM)
    def initComponents(self):
        self.TrafficGen.initComponents()
        self.ReSend.initComponents()
        self.SendARQ.initComponents()
        self.QueueManagement.initComponents()
        for IM in self.IncomingMons:
            IM.initComponents()
    def activate(self):
        activate(self.TrafficGen,self.TrafficGen.execute(),at=0.0)
        activate(self.ReSend,self.ReSend.execute(),at=0.0)
        activate(self.SendARQ,self.SendARQ.execute(),at=0.0)
        activate(self.QueueManagement,self.QueueManagement.execute(),at=0.0)
        activate(self.Send,self.Send.execute(),at=0.0)
        for IM in self.IncomingMons:
            activate(IM,IM.execute(),at=0.0)
        
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

simulate(until=100) 
print 'done'
print 'success=', G.SUCCESSFUL, ', failure=', G.FAILURE   
        
            
            