'''
Created on Oct 28, 2010

@author: duncantait
'''

#Environment (super)class - interfaces to all Tx and provides data as the physical Medium
#Doubles as the Simulation environment - providing Global variables and Global data structures

from SimPy.SimulationTrace import *
import random
import math

class G(): #Global variables for simulation
    num_chans = 5
    num_nodes = 3
    max_bitrate = 398
    
    dwell_time = 2 #Scanning dwell time
    scanning_call_timeout = 20 #Arb value
    response_timeout = 2 #Arb value
    linked_timeout = 30 #Arb value
    
    chance_reply = 0.6 #probability of replying in linked mode

class Environment(Process):
    def __init__(self):
        Process.__init__(self)
        self.ALE_nodes = []
        self.MHS_nodes = []
        self.grid = []
        self.LQA_grid = []
        
        for i in range(G.num_chans):
            row = []
            for j in range(G.num_nodes):
                S = Store(name = j, capacity=1)
                row.append(S)
            self.grid.append(row)
                
        for i in range(G.num_nodes):
            row1 = []
            for j in range(G.num_chans):
                row2 = []
                for h in range(G.num_nodes):
                    lqa_value = random.random()
                    row2.append(lqa_value)
                row1.append(row2)
            self.LQA_grid.append(row1)
    # This is a 3 dimensional grid of Nodes:Channels:Nodes, so each Node has an LQA value for
    # each other Node, and for each channel. e.g. self.LQA_grid[4][1][5] would be the LQA value
    # for Node 4 -> Node 5 on Channel 2
    # THIS GRID NEEDS TO BE SYMMETRICAL !! I.e. a->b == b->a
    # Consider making it a matrix and then looking @ complex networks theory (adjacency matrix)
            
    def execute(self):
        while True:
            yield hold, self, random.uniform(1,10)
            for i in range(len(self.LQA_grid)):
                for j in range(len(self.LQA_grid[i])):
                    for h in range(len(self.LQA_grid[i][j])):
                        self.LQA_grid[i][j][h] = random.random()
    
    #So whenever a signal is sent, it accesses the LQA on the 3D grid for that particular transaction, and then
    #copies it to it's own LQA table (future step...)
    #Obviously, this changing over time algorithm needs to be a bit better! Look at the sin wave examples 
    #from Grapher, so long-term, mid-term and short term changes (frequency), with low-magnitude noise throughout 
    #x = now()
    #y=0.5*(0.85*math.sin(0.1*x) + 0.1*math.sin(x) + 0.05*math.sin(12*x))+0.5
    
    def updateLQA(self, data):
        returnData = data    
        returnData.LQA = self.Environment.LQA_grid[returnData.origin][returnData.chan][returnData.destination]
        returnData.signal_time = returnData.size*G.max_bitrate*(1./returnData.LQA)
        return returnData 


class dataStruct():
    def __init__(self, origin=-1, destination=-1, type=-1, chan=-1, size=-1, signal_time=-1, LQA=-1):  
        self.origin = origin
        self.destination = destination
        self.type = type
        self.chan = chan
        self.size = size
        self.signal_time = signal_time
        self.LQA = LQA
        
class dataType():
    CALL = 1
    RESPONSE = 2
    ACK = 3
    DATA = 4
 
class _Env():
    def __init__(self):
        self.G = G()
        self.Environment = Environment()
        activate(self.Environment, self.Environment.execute(), at=0.0)
        
Env = _Env() 


        
        