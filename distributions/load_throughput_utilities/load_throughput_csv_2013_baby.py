import csv
import numpy as np
import pylab as plab
            
class CSVReader():
    def __init__(self):
        self.rfid = None
        self.data_block = []
        self.tpValues = np.zeros(100)
        self.lossValues = np.zeros(100)
        self.finalTPVals = []
        self.finalLossVals = []

        self.counter = 0
        self.run_counter = -1
    def readCSVFile(self, filename):
        self.rfid = csv.reader(open(filename, 'rb'), delimiter=' ')
        for i, row in enumerate(self.rfid):
            if row != None:
                if row[0][0] == 'r':
                    self.run_counter += 1
                    print 'Run COUNTER:', self.run_counter
                else:
                    self.counter += 1
                    num_nodes = int(row[0])
                    self.tpValues[num_nodes] += float(row[1])
                    self.lossValues[num_nodes] += float(row[2])
    def printOutputValues(self):
        counter = float(self.counter)

        for tp_val in self.tpValues:
            self.finalTPVals.append(tp_val/counter)
        for loss_val in self.lossValues:
            self.finalLossVals.append(loss_val/counter)

        print 'TP Vals:', [(i, val) for i, val in enumerate(self.finalTPVals)]
        print 'Loss Vals:', [(i, val) for i, val in enumerate(self.finalLossVals)]

    def graphOutput(self):
        plab.subplot(2, 1, 1)
        plab.plot(range(100),self.finalTPVals)
        plab.title('Throughput and Loss as a function of Number of Nodes')
        plab.ylabel('Throughput')
        plab.subplot(2, 1, 2)
        plab.plot(range(100),self.finalLossVals)
        plab.ylabel('Loss')
        plab.xlabel('Num Nodes')
        plab.show()

filename = 'load_throughput_data_30102013_2006.txt'

CSVR = CSVReader()
CSVR.readCSVFile(filename)
CSVR.printOutputValues()
CSVR.graphOutput()
