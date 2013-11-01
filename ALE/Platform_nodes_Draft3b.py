from SimPy.Simulation import *
import visual as v
import math
from random import seed, uniform, randint

class Global():
    NUMNODES = 4
    NUMCHANNELS = 1
    Node_L_List = []
    Node_A_List = []
    Node_S_List = []
    ChannelList = [] #stores
    NodeSendQueueList = [] #stores
    maxTime = 10

class Mon():
    NumListenCollisions = 0
    NumSendingCollisions = 0

class Packet():
    def __init__(self, a_to, a_from, tx, p_type):
        self.addr_to = a_to #should be int
        self.addr_from = a_from
        self.tx = tx
        self.p_type = p_type #0=data, 1=confirm

class NodeListen(Process):
    def __init__(self,i):
        Process.__init__(self,name='NodeL'+str(i))
        self.ID = i #shared between Listen and Send processes
    def execute(self):
        while True:
            yield hold, self, 0.01
            for chn in G.ChannelList: #potential to randomise this order to prevent all Nodes searching iteratively
                if chn.nrBuffered > 0:
                    for pkt in chn.theBuffer: #this is a bit magic atm: checking packet without 'grabbing' it
                        if pkt.addr_to == self.ID and pkt.p_type == 0:
                            yield (get,self,chn,1,1),(hold,self,0.0001) #renege after very short time: if item's not there immediately then move on
                            if len(self.got)>0:
                                print 'Node',self.ID, 'got packet from Node',self.got[0].addr_from
                                #yield get,self,chn,1,1 #priority 1 (low)
                                conf_pkt = Packet(self.got[0].addr_from,self.ID,now(),1)
                                yield put,self,G.NodeSendQueueList[self.ID],[conf_pkt],5 #priority 5 (high)
                                print 'Node',self.ID, 'put CONF packet on NodeSendQueue'
                            else:
                                Mon.NumListenCollisions += 1
                                print 'Listen Collision'
                                yield get,self,chn,1,100 #priority 100 (v high) - getting colliding packet from channel
                                print self.got
                        elif pkt.addr_to == self.ID and pkt.p_type == 1:
                            print 'Node',self.ID,' received CONF packet from', pkt.addr_from, now()
                            yield get,self,chn,1,1
                            self.interrupt(G.Node_S_List[pkt.addr_from])

class NodePacketAdder(Process):
    def __init__(self,i):
        Process.__init__(self,name='NodeA'+str(i))
        self.ID = i #shared between Listen and Send and Adding processes
    def execute(self):
        while True:
            yield hold, self, uniform(1,5)
            nodeToSend = randint(0,G.NUMNODES-1)
            while nodeToSend == self.ID: #make sure not sending to itself
                nodeToSend = randint(0,G.NUMNODES-1)
                
            pkt = Packet(nodeToSend,self.ID,now(),0)
            yield put,self,G.NodeSendQueueList[self.ID],[pkt],1 #priority 1 (low)

class NodeSend(Process):
    def __init__(self,i):
        Process.__init__(self,name='NodeS'+str(i))
        self.ID = i
    def execute(self):
        yield hold, self, uniform(0,1) #so don't all start at same time
        while True:           
            sent = False
            choice = -1
            while sent==False :
                if G.NodeSendQueueList[self.ID].nrBuffered > 0:               
                    for i in range(G.NUMCHANNELS):
                        if G.ChannelList[i].nrBuffered==0:
                            choice = i
                            break
                    if choice != -1:
                        yield hold, self, 0.001 #very short wait to represent slight delay
                        if G.ChannelList[choice].nrBuffered==0:
                            if G.NodeSendQueueList[self.ID].nrBuffered > 0: 
                                yield get,self,G.NodeSendQueueList[self.ID],1,1 #priority 1 (low)
                                print 'Node',self.ID, 'read from NodeSendQueue, sending packet to:', self.got[0].addr_to, 'type:', self.got[0].p_type, 'on', chn.name
                            else:
                                print 'Something bad happened'
                            yield put,self,chn,self.got, 1 #priority 1 (low)                           
                            sent=True
                            if self.got[0].p_type==1:
                                yield hold,self,0.1 #time to recieve packet before resending
                                if self.interrupted():
                                    yield get,self,G.NodeSendQueueList[self.ID],1,100 #pop off first entry in list, else it remains on list for next loop, priority 100 (v high)
                                    self.interruptReset()
                                    print 'Interrupt success: Conf packet received'
                                else:
                                    print 'Node',self.ID, 'did not receieve conf, resending'
                            else:
                                yield hold,self,0.01
                        else:
                            Mon.NumSendingCollisions += 1
                            print 'Sending Collision'
                            yield get,self,chn,1,100 #priority 100 (v high) - getting colliding packet from channel
                            print self.got
                            yield hold, self, uniform(0,1) #backoff
                        choice = -1
                    else:
                        yield hold,self,0.01 #if no free channels
                else:
                    yield hold,self,0.01 #if nothing in buffer

class visualising():
    def __init__(self):
        self.sphereList = [] #sphere for each node
        self.rodList = [] #unused
        self.manageRodList = [] #rods connecting nodes to centre management node
        
        r = 1.0 #radius of circle that nodes are in
        delta_theta = (2.0*math.pi) / G.NUMNODES #angle between nodes
        theta = 0

        self.management = v.sphere(pos=v.vector(0,0,0), radius=0.1, colour=v.color.blue) #management node in centre
        self.label = v.label(pos=(1,1,0), text= '0') #label for amount of disparities at that point in time
        self.label_cum = v.label(pos=(-1,1,0), text= '0') #cumulative total number of above
        
        for i in range(0,G.NUMNODES):
            circ = v.sphere(pos=v.vector(r*math.cos(theta),r*math.sin(theta),0), radius=0.1, color=v.color.green)
            self.sphereList.append(circ)
            print 'circle no. ', i, ' coords ', r*math.cos(theta), ' ', r*math.sin(theta)
            theta += delta_theta
            rod = v.cylinder(pos=(0,0,0),axis=(self.sphereList[i].pos), radius=0.005, color=v.color.white)
            self.manageRodList.append(rod)

initialize()
G = Global()
Vis=visualising()

for i in range(G.NUMCHANNELS):
    chn = Store(name='Channel'+str(i),unitName='packet',capacity=1,putQType=PriorityQ,getQType=PriorityQ)
    G.ChannelList.append(chn)
for i in range(G.NUMNODES):
    nodeQueue = Store(name='NodeQueue'+str(i),unitName='packet',capacity=1,putQType=PriorityQ,getQType=PriorityQ)
    G.NodeSendQueueList.append(nodeQueue)
    node_l = NodeListen(i)
    node_a = NodePacketAdder(i)
    node_s = NodeSend(i)
    G.Node_L_List.append(node_l)
    G.Node_A_List.append(node_a)
    G.Node_S_List.append(node_s)
    activate(G.Node_L_List[i],G.Node_L_List[i].execute(),at=0.0)
    activate(G.Node_A_List[i],G.Node_A_List[i].execute(),at=0.0)
    activate(G.Node_S_List[i],G.Node_S_List[i].execute(),at=0.0)

simulate(until=G.maxTime)
